"""Dynamic Supply Aggregation (SIH26132 Feature 2) — ALGORITHMIC.

Fills a buyer requirement that no single farmer can cover, by proposing a set of
compatible nearby lots.

    Buyer needs 1000 kg Tomato
      Farmer A  350 kg   Farmer B 300 kg
      Farmer C  200 kg   Farmer D 150 kg
    = 1000 kg

THE SAFETY PROPERTY THIS MODULE EXISTS TO HOLD
----------------------------------------------
A suggestion is not a commitment. This module only ever proposes; it never
reserves, never assigns, and never mutates a listing. The lifecycle is

    suggested -> farmer consent (per line) -> buyer confirmation -> reserved

and a farmer's listing is never written at any point in it. Everything here is
pure selection over rows handed in.

DOUBLE COUNTING
---------------
Reservation is derived, not stored on the listing: a live group's own
aggregation_items rows ARE its claim. routers/aggregations.py subtracts those
claims wherever availability is computed, so the same kilo is never offered to
two buyers, and confirm() re-checks against that ledger because a suggestion
computed a minute ago is not proof of anything. products.available_quantity_kg
belongs to the farmer and stays exactly as they wrote it.

NEUTRALITY
----------
Lots are ordered by unit price ascending, then distance, then id — declared,
deterministic, and independent of farmer identity. No farmer, FPO or region is
preferred. Cheapest-first serves the buyer's requirement at the lowest cost
while still paying each farmer their asking price.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import market_data as md
from . import orchestration

METHOD = "ALGORITHMIC"

# Grade ranking shared with routers/buyer_matching.py and services/net_exit.py.
_GRADE_RANK = {"A": 3, "B": 2, "C": 1}

# A lot further than this from the delivery district is not proposed: hauling a
# small partial lot across the state rarely survives the net-realization maths.
MAX_SOURCING_DISTANCE_KM = 400.0

ASSUMPTIONS = {
    "max_sourcing_distance_km": MAX_SOURCING_DISTANCE_KM,
    "selection_order": "unit price asc, then distance asc, then product id",
    "note": ("Suggestions only. No inventory is reserved until the farmer "
             "accepts their line and the buyer confirms the group."),
}


@dataclass
class Candidate:
    """One lot considered for the group."""

    product_id: str
    farmer_id: str
    farmer_name: str | None
    district: str | None
    grade: str | None
    unit_price_paise: int
    available_kg: float          # already net of other live aggregations
    distance_km: float | None
    take_kg: float = 0.0         # how much of it this proposal would use
    reasons: list[str] = field(default_factory=list)

    @property
    def line_value_paise(self) -> int:
        return int(round(self.take_kg * self.unit_price_paise))


@dataclass
class Proposal:
    """A costed, explainable aggregation suggestion."""

    buyer_request_id: str
    crop_id: str
    required_kg: float
    covered_kg: float
    items: list[Candidate]
    rejected: list[dict]
    grade_variance_warning: bool
    combined_price_paise: int
    method: str = METHOD

    @property
    def sufficient(self) -> bool:
        return self.covered_kg >= self.required_kg

    @property
    def shortfall_kg(self) -> float:
        return max(0.0, round(self.required_kg - self.covered_kg, 3))

    def to_dict(self) -> dict:
        return {
            "buyer_request_id": self.buyer_request_id,
            "crop_id": self.crop_id,
            "required_kg": self.required_kg,
            "covered_kg": round(self.covered_kg, 3),
            "shortfall_kg": self.shortfall_kg,
            "sufficient": self.sufficient,
            "farmer_count": len({i.farmer_id for i in self.items}),
            "combined_price_paise": self.combined_price_paise,
            "grade_variance_warning": self.grade_variance_warning,
            "method": self.method,
            "assumptions": ASSUMPTIONS,
            "neutrality": orchestration.disclosure(orchestration.AGGREGATION_POLICY),
            "items": [
                {
                    "product_id": i.product_id,
                    "farmer_id": i.farmer_id,
                    "farmer_name": i.farmer_name,
                    "district": i.district,
                    "grade": i.grade,
                    "unit_price_paise": i.unit_price_paise,
                    "available_kg": i.available_kg,
                    "take_kg": round(i.take_kg, 3),
                    "line_value_paise": i.line_value_paise,
                    "distance_km": i.distance_km,
                    "reasons": i.reasons,
                }
                for i in self.items
            ],
            "rejected": self.rejected,
        }


def _eligible(
    product: dict, request: dict, *, committed_kg: float, today: date,
) -> tuple[bool, str | None, float]:
    """Can this lot take part, and how much of it is genuinely free?

    Returns (eligible, rejection reason, free kg). Every rejection carries a
    reason so the buyer sees why supply fell short rather than a bare number.
    """
    if product.get("status") != "active":
        return False, f"listing is {product.get('status')}", 0.0

    free = float(product.get("available_quantity_kg") or 0) - committed_kg
    if free <= 0:
        return False, "already committed to another aggregation", 0.0

    min_grade = request.get("min_grade")
    grade = product.get("grade")
    if min_grade and grade and _GRADE_RANK.get(grade.upper(), 0) < _GRADE_RANK.get(min_grade.upper(), 0):
        return False, f"grade {grade} below required {min_grade}", 0.0

    target = request.get("target_price_paise")
    ask = product.get("asking_price_paise") or 0
    if target and ask > target:
        return False, f"asking {ask} paise/kg exceeds target {target}", 0.0

    until = product.get("available_until")
    needed_by = request.get("needed_by")
    if until and needed_by:
        try:
            if date.fromisoformat(str(until)[:10]) < date.fromisoformat(str(needed_by)[:10]):
                return False, "listing expires before the buyer needs delivery", 0.0
        except ValueError:
            pass
    if until:
        try:
            if date.fromisoformat(str(until)[:10]) < today:
                return False, "listing has expired", 0.0
        except ValueError:
            pass

    return True, None, free


def propose(
    *, request: dict, products: list[dict], committed: dict[str, float] | None = None,
    today: date | None = None,
) -> Proposal:
    """Select the cheapest compatible set of lots that covers the requirement.

    Greedy on unit price. For this problem greedy is optimal on cost: any lot
    can be partially taken, so filling from the cheapest upward always yields the
    minimum spend for a given quantity. No lot is ever taken beyond what is free.
    """
    today = today or date.today()
    committed = committed or {}
    required = float(request.get("quantity_kg") or 0)
    delivery = request.get("delivery_district")

    candidates: list[Candidate] = []
    rejected: list[dict] = []

    for p in products:
        if str(p.get("crop_id")) != str(request.get("crop_id")):
            rejected.append({"product_id": p.get("id"), "reason": "different crop"})
            continue

        ok, why, free = _eligible(
            p, request, committed_kg=committed.get(str(p.get("id")), 0.0), today=today)
        if not ok:
            rejected.append({"product_id": p.get("id"), "reason": why})
            continue

        distance = md.district_distance_km(p.get("district"), delivery)
        if distance is not None and distance > MAX_SOURCING_DISTANCE_KM:
            rejected.append({
                "product_id": p.get("id"),
                "reason": f"{distance:.0f} km away, beyond the "
                          f"{MAX_SOURCING_DISTANCE_KM:.0f} km sourcing radius",
            })
            continue

        candidates.append(Candidate(
            product_id=str(p.get("id")), farmer_id=str(p.get("farmer_id")),
            farmer_name=p.get("farmer_name"), district=p.get("district"),
            grade=p.get("grade"), unit_price_paise=int(p.get("asking_price_paise") or 0),
            available_kg=round(free, 3), distance_km=distance,
        ))

    # Declared, identity-independent ordering.
    candidates.sort(key=lambda c: (
        c.unit_price_paise,
        c.distance_km if c.distance_km is not None else float("inf"),
        c.product_id,
    ))

    chosen: list[Candidate] = []
    remaining = required
    for c in candidates:
        if remaining <= 0:
            break
        take = min(c.available_kg, remaining)
        if take <= 0:
            continue
        c.take_kg = round(take, 3)
        c.reasons.append(f"{c.unit_price_paise} paise/kg")
        if c.distance_km is not None:
            c.reasons.append(f"{c.distance_km:.0f} km from {delivery or 'delivery point'}")
        if c.take_kg < c.available_kg:
            c.reasons.append(f"partial draw of {c.available_kg:g} kg available")
        chosen.append(c)
        remaining = round(remaining - take, 3)

    grades = {c.grade for c in chosen if c.grade}
    covered = round(sum(c.take_kg for c in chosen), 3)

    return Proposal(
        buyer_request_id=str(request.get("id")),
        crop_id=str(request.get("crop_id")),
        required_kg=required,
        covered_kg=covered,
        items=chosen,
        rejected=rejected,
        grade_variance_warning=len(grades) > 1,
        combined_price_paise=sum(c.line_value_paise for c in chosen),
    )
