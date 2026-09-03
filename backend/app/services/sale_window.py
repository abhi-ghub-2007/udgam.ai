"""Risk-Adjusted Sale Window (SIH26132 Feature 3) — ALGORITHMIC.

Answers "sell now, or wait?" — and answers it honestly, which means it must be
willing to say "sell now" even when the forecast price is higher later.

    risk-adjusted value
      = expected net realization at the horizon
      - risk penalty derived from that forecast's own downside band

THE RULE THIS MODULE EXISTS TO ENFORCE
--------------------------------------
A higher predicted price is not a reason to wait. Waiting costs storage, loses
weight to spoilage, and stakes the outcome on a forecast that widens the further
out it goes. So every scenario is scored net of those costs and penalised by its
own uncertainty: the wider the confidence band, the larger the penalty. A
14-day forecast on a perishable crop has to clear a high bar to beat selling
today, and usually does not.

The penalty is the forecast's *downside* — expected minus the low end of its own
confidence band — scaled by RISK_AVERSION. It is derived from data the forecast
already carries, never a free-floating fudge factor, and it is reported as a
named line so the farmer can see exactly what waiting is being charged for.

REUSE
-----
Scenarios are Opportunity records, built by the same net_exit builders the Net
Exit Optimizer uses, at different `holding_days`. Storage is priced from real
storage_listings rows. There is no second economics engine here.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import net_exit
from .opportunity import CostLine, Opportunity

# Weight on the downside half of the forecast band. 0.5 means a farmer is
# charged half of the plausible downside as the price of taking the bet —
# risk-averse without being paralysed. Declared, not hidden.
RISK_AVERSION = 0.5

# Waiting past this fraction of a crop's shelf life is refused outright rather
# than merely penalised: the lot would not survive to be sold.
MAX_SHELF_FRACTION = 0.75

DEFAULT_HORIZONS = (0, 3, 7, 14)

ASSUMPTIONS = {
    "risk_aversion": RISK_AVERSION,
    "max_shelf_fraction": MAX_SHELF_FRACTION,
    "risk_penalty_formula": (
        "RISK_AVERSION x (expected_price - confidence_low) x quantity_kg; "
        "zero for selling now, which carries no forecast uncertainty"
    ),
    "note": ("Waiting is scored on risk-adjusted value, never on the headline "
             "forecast price. A wider forecast band makes waiting less "
             "attractive, not more."),
}


@dataclass(frozen=True)
class StorageQuote:
    """Cheapest suitable storage, from a real posted listing."""

    cost_paise: int
    listing_id: str
    name: str
    storage_type: str
    rate_paise_per_kg_day: int


def quote_storage(
    listings: list[dict], *, quantity_kg: float, days: int,
) -> StorageQuote | None:
    """Cheapest active listing with room for the lot, or None if there is none.

    None means unknown, never free: the caller marks the scenario's cost basis
    incomplete so it cannot win by having an uncosted line.
    """
    if days <= 0:
        return None
    best: StorageQuote | None = None
    for site in listings:
        if (site.get("available_capacity_kg") or 0) < quantity_kg:
            continue
        rate = site.get("price_paise_per_kg_day")
        if rate is None or rate < 0:
            continue
        cost = int(round(rate * quantity_kg * days))
        if best is None or cost < best.cost_paise:
            best = StorageQuote(
                cost, str(site.get("id")), site.get("name") or "Storage",
                site.get("storage_type") or "dry", int(rate),
            )
    return best


def risk_penalty_paise(
    *, expected_unit_paise: int, confidence_low_paise: int | None,
    quantity_kg: float,
) -> tuple[int, str]:
    """Charge for the downside of a forecast, from the forecast's own band."""
    if confidence_low_paise is None or confidence_low_paise >= expected_unit_paise:
        return 0, "no downside band on this forecast"
    downside_per_kg = expected_unit_paise - confidence_low_paise
    penalty = int(round(RISK_AVERSION * downside_per_kg * quantity_kg))
    return penalty, (
        f"{RISK_AVERSION:g} x {downside_per_kg} paise/kg downside "
        f"x {quantity_kg:g} kg"
    )


def build_scenario(
    *, product: dict, crop: dict, district: str, horizon_days: int,
    price_row: dict | None, distance_km: float | None,
    capacities: list[dict], storage_listings: list[dict],
    price_provenance: dict | None = None,
) -> Opportunity:
    """One 'sell in N days' scenario, as an Opportunity.

    Built through net_exit.build_mandi_opportunity so the economics are the same
    ones the Net Exit Optimizer uses — this module only adds holding cost and
    the risk charge on top.
    """
    quantity = float(product.get("available_quantity_kg") or product.get("quantity_kg") or 0)
    shelf_life = crop.get("default_shelf_life_days") or 365

    storage = quote_storage(storage_listings, quantity_kg=quantity, days=horizon_days)

    opp = net_exit.build_mandi_opportunity(
        product=product, crop=crop, district=district, price_row=price_row,
        distance_km=distance_km, capacities=capacities,
        storage_cost_paise=storage.cost_paise if storage else 0,
        holding_days=horizon_days, price_provenance=price_provenance,
    )
    opp.reference_name = "Sell now" if horizon_days == 0 else f"Wait {horizon_days} days"
    opp.reference_id = f"h{horizon_days}"

    if not opp.feasible:
        return opp

    # --- can the lot survive the wait at all? ------------------------------
    if horizon_days > 0 and horizon_days > shelf_life * MAX_SHELF_FRACTION:
        opp.feasible = False
        opp.blockers.append(
            f"{horizon_days} days exceeds {MAX_SHELF_FRACTION:.0%} of this crop's "
            f"{shelf_life}-day shelf life; the lot would not keep"
        )
        return opp

    # --- storage must be costed if the farmer is going to hold -------------
    if horizon_days > 0 and storage is None:
        opp.cost_basis_complete = False
        opp.limitations.append(
            f"no storage listing has room for {quantity:g} kg; the cost of "
            "holding cannot be determined, so this option is not comparable"
        )
        opp.recompute_net()
        return opp
    if storage is not None:
        opp.reasons.append(
            f"stored at {storage.name} ({storage.storage_type}), "
            f"{storage.rate_paise_per_kg_day} paise/kg/day"
        )

    # --- charge the forecast's own downside --------------------------------
    if horizon_days > 0 and opp.unit_price_paise:
        penalty, basis = risk_penalty_paise(
            expected_unit_paise=opp.unit_price_paise,
            confidence_low_paise=(price_row or {}).get("confidence_low_paise"),
            quantity_kg=quantity,
        )
        # Deliberately NOT a CostLine. net_realization_paise stays the honest
        # expected economics; the risk charge sits outside it and produces
        # risk_adjusted_paise, matching the brief's RAEV formula. Folding it
        # into the breakdown would double-count it and misreport what the
        # farmer would actually bank if the forecast came true.
        opp.risk_penalty_paise = penalty
        opp.risk_notes.append(f"risk charge {penalty} paise: {basis}")
        conf = (price_provenance or {}).get("confidence")
        if conf is not None:
            opp.confidence = conf
            if conf < 0.3:
                opp.risk_notes.append(
                    f"forecast confidence is low ({conf}); waiting may increase "
                    "expected value but the uncertainty is substantial"
                )
    else:
        opp.risk_notes.append("selling now carries no forecast uncertainty")

    opp.recompute_net()
    return opp


def evaluate(
    *, product: dict, crop: dict, district: str, price_rows: dict[int, dict],
    distance_km: float | None, capacities: list[dict],
    storage_listings: list[dict], provenances: dict[int, dict] | None = None,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict:
    """Compare selling now against each waiting horizon.

    `price_rows` maps horizon -> price row (0 = latest observation). A horizon
    with no row is skipped rather than extrapolated: no price source, no
    scenario.
    """
    provenances = provenances or {}
    scenarios: list[Opportunity] = []
    for horizon in horizons:
        row = price_rows.get(horizon)
        if row is None:
            continue
        scenarios.append(build_scenario(
            product=product, crop=crop, district=district, horizon_days=horizon,
            price_row=row, distance_km=distance_km, capacities=capacities,
            storage_listings=storage_listings,
            price_provenance=provenances.get(horizon),
        ))

    ranked = net_exit.rank(scenarios, by="risk_adjusted")
    best = ranked["best"]

    recommendation = None
    if best is not None:
        sell_now = next((s for s in ranked["ranked"] if s.holding_days == 0), None)
        if best.holding_days == 0:
            recommendation = "sell_now"
        elif sell_now is not None:
            gain = (best.risk_adjusted_paise or 0) - (sell_now.risk_adjusted_paise or 0)
            recommendation = "wait"
            best.reasons.append(
                f"{gain} paise better than selling today, after storage, "
                "spoilage and the risk charge"
            )
        else:
            recommendation = "wait"

    return {
        **ranked,
        "recommendation": recommendation,
        "assumptions": {**ranked["assumptions"], **ASSUMPTIONS},
    }
