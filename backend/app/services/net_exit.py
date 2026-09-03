"""Net Exit Optimizer (SIH26132 Feature 1) — ALGORITHMIC.

Answers "which way of selling this lot actually leaves the most money with the
farmer", which is not the same question as "who is offering the highest price".

    gross sale value
      - transport      (only when the farmer bears it)
      - storage
      - platform fee / mandi commission (only the farmer's share)
      - expected spoilage loss
    = expected farmer net realization

Every term is integer paise and every term is a named CostLine carrying who
bears it, so the API can show the arithmetic rather than assert a winner.

REUSE, NOT A SECOND PRICING ENGINE
----------------------------------
The platform-sale channel calls services.pricing.compute_breakdown and takes its
`farmer_payout_paise` and `platform_fee_paise` verbatim. If the platform's fee
policy changes in pricing.py, this optimizer follows automatically. Transport is
priced from real posted transport_capacity rows, and market prices come from the
Phase 1 `prices` table. The only numbers originating here are the spoilage model
and the mandi commission rate, both declared below and surfaced in the response
as assumptions.

NEUTRALITY
----------
rank() sorts on net_realization_paise alone, descending, tie-broken by distance
then reference id. There is no per-buyer, per-market, per-transporter or
per-partner term anywhere in this module, and tests/test_net_exit.py asserts
that relabelling a counterparty cannot change the ordering.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import orchestration
from .opportunity import CostLine, Opportunity
from .pricing import PLATFORM_FEE_BPS, compute_breakdown

# --- declared modelling assumptions -----------------------------------------
# Surfaced to the caller in `assumptions` so nothing here is a hidden constant.

# Indicative APMC commission borne by the seller at a regulated mandi. A
# published-rate assumption, not an observed fee for any specific market.
MANDI_COMMISSION_BPS = 600          # 6.00%

# Spoilage model. Loss rises with time out of the ground relative to the crop's
# own shelf life (crops.default_shelf_life_days), and lower grades start closer
# to the edge. Deterministic and declared — not a learned model.
TRANSIT_KM_PER_DAY = 400.0          # a day of road transit per 400 km
MIN_TRANSIT_DAYS = 0.5
MAX_LOSS_FRACTION = 0.60            # cap; beyond this the lot is unsellable
GRADE_LOSS_MULTIPLIER = {"A": 0.8, "B": 1.0, "C": 1.3}

ASSUMPTIONS = {
    "mandi_commission_bps": MANDI_COMMISSION_BPS,
    "platform_fee_bps": PLATFORM_FEE_BPS,
    "transit_km_per_day": TRANSIT_KM_PER_DAY,
    "max_loss_fraction": MAX_LOSS_FRACTION,
    "grade_loss_multiplier": GRADE_LOSS_MULTIPLIER,
    "note": ("Deterministic modelling assumptions, not observed market fees. "
             "Platform fee and farmer payout come from services/pricing.py; "
             "transport comes from posted transport_capacity rows."),
}


@dataclass(frozen=True)
class TransportQuote:
    """A costed route, derived from a real posted capacity row."""

    cost_paise: int
    source: str
    basis: str


def transit_days(distance_km: float | None) -> float:
    if not distance_km or distance_km <= 0:
        return MIN_TRANSIT_DAYS
    return max(MIN_TRANSIT_DAYS, distance_km / TRANSIT_KM_PER_DAY)


def expected_loss_fraction(
    *, shelf_life_days: int | None, holding_days: int, distance_km: float | None,
    grade: str | None,
) -> float:
    """Fraction of the lot expected to be lost before it reaches the buyer.

    Linear in (days exposed / shelf life), scaled by grade. A crop with no
    recorded shelf life is treated as robust (365d) rather than assumed
    perishable — guessing perishable would invent a cost.
    """
    shelf = shelf_life_days if (shelf_life_days and shelf_life_days > 0) else 365
    exposed = holding_days + transit_days(distance_km)
    multiplier = GRADE_LOSS_MULTIPLIER.get((grade or "B").upper(), 1.0)
    return min(MAX_LOSS_FRACTION, max(0.0, (exposed / shelf) * multiplier))


def quote_transport(
    capacities: list[dict], *, quantity_kg: float, distance_km: float | None,
) -> TransportQuote | None:
    """Cheapest feasible posted capacity for this lot, or None if none exists.

    None means "we do not know what transport costs on this route" and the
    caller must mark the opportunity's cost basis incomplete. It never means
    free. Choosing the cheapest is an objective, disclosed criterion — no
    transporter is preferred by identity.
    """
    best: TransportQuote | None = None
    for cap in capacities:
        if (cap.get("available_capacity_kg") or 0) < quantity_kg:
            continue
        per_kg = cap.get("price_paise_per_kg") or 0
        per_km = cap.get("price_paise_per_km") or 0
        if per_kg <= 0 and per_km <= 0:
            continue
        raw = int(round(per_kg * quantity_kg + per_km * (distance_km or 0)))
        discount = float(cap.get("discount_pct") or 0)
        cost = int(round(raw * (1 - discount / 100.0)))
        if cost < 0:
            continue
        basis = f"{per_kg} paise/kg x {quantity_kg:g} kg"
        if per_km:
            basis += f" + {per_km} paise/km x {distance_km or 0:g} km"
        if discount:
            basis += f", less {discount:g}% empty-leg discount"
        if best is None or cost < best.cost_paise:
            best = TransportQuote(cost, "transport_capacity", basis)
    return best


def _loss_line(
    *, gross_paise: int, shelf_life_days: int | None, holding_days: int,
    distance_km: float | None, grade: str | None,
) -> CostLine:
    fraction = expected_loss_fraction(
        shelf_life_days=shelf_life_days, holding_days=holding_days,
        distance_km=distance_km, grade=grade,
    )
    return CostLine(
        label="Expected spoilage loss",
        amount_paise=int(round(gross_paise * fraction)),
        kind="deduction", borne_by="farmer",
        basis=(f"{fraction:.1%} of lot: {holding_days}d held + "
               f"{transit_days(distance_km):.1f}d transit against a "
               f"{shelf_life_days or 365}d shelf life, grade {grade or 'B'}"),
        source="crops.default_shelf_life_days",
    )


def build_direct_buyer_opportunity(
    *, product: dict, request: dict, crop: dict, distance_km: float | None,
    capacities: list[dict], storage_cost_paise: int = 0, holding_days: int = 0,
    payment_reliability: float | None = None,
    payment_reliability_basis: str | None = None,
    today: date | None = None,
) -> Opportunity:
    """A platform sale to a specific buyer request.

    Priced at the buyer's target price where they state one, otherwise the
    farmer's asking price. The platform fee and transport are borne by the
    buyer, exactly as services/pricing.py already defines — so they appear in
    the breakdown for transparency but do not reduce farmer net realization.
    """
    today = today or date.today()
    qty = float(product.get("available_quantity_kg") or product.get("quantity_kg") or 0)
    unit = request.get("target_price_paise") or product.get("asking_price_paise")

    opp = Opportunity(
        channel="direct_buyer",
        reference_id=str(request.get("id")) if request.get("id") else None,
        reference_name=request.get("buyer_name") or "Buyer requirement",
        crop_id=str(product.get("crop_id")),
        crop_code=crop.get("code"),
        grade=product.get("grade"),
        quantity_kg=qty,
        district=request.get("delivery_district"),
        distance_km=distance_km,
        holding_days=holding_days,
        payment_reliability=payment_reliability,
        payment_reliability_basis=payment_reliability_basis,
    )

    if qty <= 0:
        opp.feasible = False
        opp.blockers.append("no available quantity on this listing")
        return opp
    if not unit or unit <= 0:
        opp.feasible = False
        opp.blockers.append("no price available for this buyer requirement")
        return opp

    # --- feasibility, before economics ------------------------------------
    _apply_grade_fit(opp, product.get("grade"), request.get("min_grade"))
    _apply_quantity_fit(opp, qty, request.get("quantity_kg"))
    _apply_deadline(opp, request.get("needed_by"), distance_km, today)

    # --- economics: reuse the platform's own breakdown ---------------------
    transport = quote_transport(capacities, quantity_kg=qty, distance_km=distance_km)
    breakdown = compute_breakdown(
        quantity_kg=qty,
        unit_price_paise=unit,
        transport_cost_paise=transport.cost_paise if transport else 0,
    )

    opp.unit_price_paise = unit
    opp.gross_value_paise = breakdown.subtotal_paise
    opp.platform_fee_paise = breakdown.platform_fee_paise
    opp.storage_cost_paise = storage_cost_paise
    opp.transport_cost_paise = transport.cost_paise if transport else None

    opp.breakdown.append(CostLine(
        label="Gross sale value", amount_paise=breakdown.subtotal_paise,
        kind="gross", borne_by="buyer",
        basis=f"{qty:g} kg x {unit} paise/kg", source="services/pricing.py",
    ))
    opp.breakdown.append(CostLine(
        label="Platform fee", amount_paise=breakdown.platform_fee_paise,
        kind="deduction", borne_by="buyer",
        basis=f"{PLATFORM_FEE_BPS/100:g}% of gross, paid by the buyer on top",
        source="services/pricing.py",
    ))
    if transport:
        opp.breakdown.append(CostLine(
            label="Transport", amount_paise=transport.cost_paise,
            kind="deduction", borne_by="buyer",
            basis=transport.basis + " (buyer pays delivery on a platform sale)",
            source=transport.source,
        ))
    else:
        # Not a blocker: the buyer bears delivery here, so an unknown transport
        # cost does not change what the farmer takes home.
        opp.limitations.append(
            "no posted transport capacity for this route; the buyer bears "
            "delivery, so farmer net realization is unaffected"
        )
    if storage_cost_paise:
        opp.breakdown.append(CostLine(
            label="Storage", amount_paise=storage_cost_paise,
            kind="deduction", borne_by="farmer",
            basis=f"{holding_days} day(s) held before sale",
            source="storage_listings",
        ))

    loss = _loss_line(
        gross_paise=breakdown.subtotal_paise,
        shelf_life_days=crop.get("default_shelf_life_days"),
        holding_days=holding_days, distance_km=distance_km,
        grade=product.get("grade"),
    )
    opp.expected_loss_paise = loss.amount_paise
    opp.breakdown.append(loss)

    opp.reasons.append("farmer receives the full sale value; buyer pays fee and delivery")
    opp.recompute_net()
    return opp


def build_mandi_opportunity(
    *, product: dict, crop: dict, district: str, price_row: dict | None,
    distance_km: float | None, capacities: list[dict],
    storage_cost_paise: int = 0, holding_days: int = 0,
    price_provenance: dict | None = None,
) -> Opportunity:
    """A sale at a regulated mandi.

    The mirror image of a platform sale: the farmer trucks the lot there and the
    commission agent takes a cut, so both transport and commission reduce net
    realization. With no price row for this crop/market the opportunity is
    returned infeasible — a mandi price is never inferred from another market.
    """
    qty = float(product.get("available_quantity_kg") or product.get("quantity_kg") or 0)

    opp = Opportunity(
        channel="mandi",
        reference_id=district,
        reference_name=f"{district} mandi",
        crop_id=str(product.get("crop_id")),
        crop_code=crop.get("code"),
        grade=product.get("grade"),
        quantity_kg=qty,
        district=district,
        distance_km=distance_km,
        holding_days=holding_days,
        price_provenance=price_provenance,
        payment_reliability=None,
        payment_reliability_basis="not tracked for mandi sales",
    )

    if qty <= 0:
        opp.feasible = False
        opp.blockers.append("no available quantity on this listing")
        return opp

    unit = (price_row or {}).get("modal_price_paise")
    if not unit or unit <= 0:
        # The rule that keeps this honest: no price source, no opportunity.
        opp.feasible = False
        opp.blockers.append(f"no market price on record for this crop in {district}")
        return opp

    transport = quote_transport(capacities, quantity_kg=qty, distance_km=distance_km)
    gross = int(round(qty * unit))
    commission = gross * MANDI_COMMISSION_BPS // 10_000

    opp.unit_price_paise = unit
    opp.gross_value_paise = gross
    opp.commission_paise = commission
    opp.storage_cost_paise = storage_cost_paise
    opp.transport_cost_paise = transport.cost_paise if transport else None

    opp.breakdown.append(CostLine(
        label="Gross sale value", amount_paise=gross, kind="gross", borne_by="farmer",
        basis=f"{qty:g} kg x {unit} paise/kg modal price",
        source=(price_provenance or {}).get("source") or "prices",
    ))
    opp.breakdown.append(CostLine(
        label="Mandi commission", amount_paise=commission,
        kind="deduction", borne_by="farmer",
        basis=f"{MANDI_COMMISSION_BPS/100:g}% indicative APMC commission on gross",
        source="declared assumption",
    ))

    if transport:
        opp.breakdown.append(CostLine(
            label="Transport", amount_paise=transport.cost_paise,
            kind="deduction", borne_by="farmer",
            basis=transport.basis + " (farmer delivers to the mandi)",
            source=transport.source,
        ))
    else:
        # Here it genuinely matters: the farmer pays this one, so without a
        # quote the comparison would be biased in this channel's favour.
        opp.cost_basis_complete = False
        opp.limitations.append(
            f"no posted transport capacity covers {qty:g} kg to {district}; "
            "the farmer bears this cost, so net realization cannot be compared"
        )

    if storage_cost_paise:
        opp.breakdown.append(CostLine(
            label="Storage", amount_paise=storage_cost_paise,
            kind="deduction", borne_by="farmer",
            basis=f"{holding_days} day(s) held before sale", source="storage_listings",
        ))

    loss = _loss_line(
        gross_paise=gross, shelf_life_days=crop.get("default_shelf_life_days"),
        holding_days=holding_days, distance_km=distance_km, grade=product.get("grade"),
    )
    opp.expected_loss_paise = loss.amount_paise
    opp.breakdown.append(loss)

    opp.confidence = (price_provenance or {}).get("confidence")
    opp.reasons.append("farmer bears transport and commission at a mandi")
    opp.recompute_net()
    return opp


# ------------------------------------------------------------------ feasibility
_GRADE_RANK = {"A": 3, "B": 2, "C": 1}   # matches routers/buyer_matching.py


def _apply_grade_fit(opp: Opportunity, grade: str | None, min_grade: str | None) -> None:
    if not min_grade:
        return
    if grade is None:
        opp.limitations.append("lot is not graded; quality fit unverified")
        return
    if _GRADE_RANK.get(grade.upper(), 0) < _GRADE_RANK.get(min_grade.upper(), 0):
        opp.feasible = False
        opp.blockers.append(f"grade {grade} is below the required minimum {min_grade}")
    else:
        opp.reasons.append(f"grade {grade} meets the minimum {min_grade}")


def _apply_quantity_fit(opp: Opportunity, available: float, wanted: float | None) -> None:
    if not wanted:
        return
    if available < wanted:
        # Not a blocker — a partial fill is a real outcome, and Phase 4
        # aggregation exists precisely to close this gap.
        opp.limitations.append(
            f"lot covers {available:g} kg of the {wanted:g} kg wanted (partial fill)"
        )
    else:
        opp.reasons.append("lot covers the full requested quantity")


def _apply_deadline(
    opp: Opportunity, needed_by, distance_km: float | None, today: date,
) -> None:
    if not needed_by:
        return
    deadline = needed_by if isinstance(needed_by, date) else _parse_date(needed_by)
    if deadline is None:
        return
    opp.deadline = deadline.isoformat()
    days = (deadline - today).days
    opp.days_to_deadline = days
    if days < 0:
        opp.feasible = False
        opp.blockers.append("the buyer's deadline has already passed")
    elif days < transit_days(distance_km):
        opp.feasible = False
        opp.blockers.append(
            f"cannot deliver in time: {days} day(s) left, "
            f"{transit_days(distance_km):.1f} day(s) of transit needed"
        )
    else:
        opp.reasons.append(f"deliverable with {days} day(s) to spare")


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------- ranking
def rank(opportunities: list[Opportunity], *, by: str = "net") -> dict:
    """Order by farmer net realization, or by risk-adjusted value.

    `by="risk_adjusted"` is what the Sale Window uses, so waiting is never
    preferred on a higher headline forecast alone. Both keys are declared in the
    returned `ranked_by`.

    Returns ranked (comparable) and excluded (infeasible or incompletely costed)
    separately, so an option can never win by being cheaper to *estimate* than
    to actually execute. Ties break on distance then reference id — declared,
    deterministic, and independent of counterparty identity.
    """
    comparable = [
        o for o in opportunities
        if o.feasible and o.cost_basis_complete and o.net_realization_paise is not None
    ]
    excluded = [o for o in opportunities if o not in comparable]

    def _value(o: Opportunity) -> int:
        if by == "risk_adjusted":
            return o.risk_adjusted_paise if o.risk_adjusted_paise is not None else 0
        return o.net_realization_paise or 0

    comparable.sort(
        key=lambda o: (
            -_value(o),
            o.distance_km if o.distance_km is not None else float("inf"),
            str(o.reference_id or ""),
        )
    )

    for i, opp in enumerate(comparable):
        nxt = comparable[i + 1] if i + 1 < len(comparable) else None
        if nxt is not None:
            advantage = _value(opp) - _value(nxt)
            opp.reasons.append(
                f"{advantage} paise better than the next feasible option "
                f"({nxt.reference_name})" if advantage
                else f"ties with {nxt.reference_name} on net realization"
            )

    policy = (orchestration.SALE_WINDOW_POLICY if by == "risk_adjusted"
              else orchestration.NET_EXIT_POLICY)
    best = comparable[0] if comparable else None
    return {
        "best": best,
        "ranked": comparable,
        "excluded": excluded,
        "ranked_by": policy.describe(),
        "method": "ALGORITHMIC",
        "assumptions": ASSUMPTIONS,
        # Feature 5: the ordering contract travels with every ranked response,
        # so a reader can audit the neutrality claim rather than take it on faith.
        "neutrality": orchestration.disclosure(policy),
    }
