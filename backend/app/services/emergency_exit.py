"""Emergency Exit Engine (SIH26132 Feature 4) — ALGORITHMIC.

When a deal falls through, a farmer is left holding a lot and a deadline. This
finds them somewhere else to send it.

    disruption detected
      -> what quantity is actually loose?
      -> which other exits accept it?
      -> rank by the SAME net-realization model as everything else
      -> present alternatives, and wait to be told

READ-SIDE ONLY. This module computes and explains; it never cancels, never
creates a replacement order, never touches the original. routers/decisions.py
exposes it as a GET. Acting on a recommendation goes through the existing order
endpoints and the existing state machine, with the farmer's explicit
confirmation — Feature 4's stated rule.

Ranking reuses net_exit.rank(), so an emergency alternative is judged on
exactly the criteria a routine sale is. There is no separate "panic" scoring
that could quietly favour whoever is closest to hand.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Order states that leave a lot needing a new home. Drawn from the order_status
# enum in db/SCHEMA.sql; the state machine itself is untouched.
DISRUPTION_STATES = {
    "CANCELLED": "the order was cancelled",
    "DISPUTED": "the order is under dispute",
}

# A shipment that never arrived is equally a disruption.
SHIPMENT_DISRUPTIONS = {
    "cancelled": "the shipment was cancelled",
}

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"


@dataclass
class Disruption:
    """What went wrong, and how much crop it stranded."""

    kind: str
    detail: str
    order_id: str
    stranded_kg: float
    crop_id: str | None
    grade: str | None
    days_to_deadline: int | None
    severity: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "detail": self.detail,
            "order_id": self.order_id,
            "stranded_kg": self.stranded_kg,
            "crop_id": self.crop_id,
            "grade": self.grade,
            "days_to_deadline": self.days_to_deadline,
            "severity": self.severity,
        }


def classify(
    *, order: dict, items: list[dict], shipment: dict | None = None,
    shelf_life_days: int | None = None, today: date | None = None,
) -> Disruption | None:
    """Identify a disruption on one order, or None if the order is healthy.

    Stranded quantity is taken from the order's own line items, not from the
    listing — the listing may have moved on, but what this order promised is a
    fact recorded at the time.
    """
    today = today or date.today()
    status = (order.get("status") or "").upper()

    kind, detail = None, None
    if status in DISRUPTION_STATES:
        kind, detail = status.lower(), DISRUPTION_STATES[status]
    elif shipment and (shipment.get("status") or "").lower() in SHIPMENT_DISRUPTIONS:
        kind = "shipment_" + (shipment.get("status") or "").lower()
        detail = SHIPMENT_DISRUPTIONS[(shipment.get("status") or "").lower()]
    if not kind:
        return None

    stranded = round(sum(float(i.get("quantity_kg") or 0) for i in items), 3)
    grade = next((i.get("grade") for i in items if i.get("grade")), None)
    crop_id = next((str(i.get("crop_id")) for i in items if i.get("crop_id")), None)

    days = None
    deadline = order.get("delivery_deadline") or order.get("needed_by")
    if deadline:
        try:
            days = (date.fromisoformat(str(deadline)[:10]) - today).days
        except (TypeError, ValueError):
            days = None

    return Disruption(
        kind=kind, detail=detail, order_id=str(order.get("id")),
        stranded_kg=stranded, crop_id=crop_id, grade=grade,
        days_to_deadline=days,
        severity=severity_of(stranded_kg=stranded, days_to_deadline=days,
                             shelf_life_days=shelf_life_days),
    )


def severity_of(
    *, stranded_kg: float, days_to_deadline: int | None,
    shelf_life_days: int | None,
) -> str:
    """How fast does this need answering?

    Driven by perishability against the time left, not by value: a tonne of
    wheat with a month to run is a smaller emergency than 200 kg of tomatoes
    with two days of shelf life remaining.
    """
    if stranded_kg <= 0:
        return SEVERITY_LOW
    shelf = shelf_life_days if (shelf_life_days and shelf_life_days > 0) else 365
    if shelf <= 7:
        return SEVERITY_HIGH
    if days_to_deadline is not None and days_to_deadline <= 2:
        return SEVERITY_HIGH
    if shelf <= 30 or (days_to_deadline is not None and days_to_deadline <= 7):
        return SEVERITY_MEDIUM
    return SEVERITY_LOW


def summarise(disruption: Disruption, ranked: dict) -> dict:
    """The farmer-facing answer: what happened, and what to do about it."""
    best = ranked.get("best")
    alternatives = ranked.get("ranked") or []

    if best is None:
        headline = (
            f"{disruption.stranded_kg:g} kg needs a new buyer, and we could not "
            "find a costed alternative right now."
        )
        action = "no_alternative_found"
    else:
        headline = (
            f"{disruption.stranded_kg:g} kg needs a new exit. Best available: "
            f"{best.reference_name}, expected net "
            f"{(best.net_realization_paise or 0) / 100:,.2f} rupees."
        )
        action = "review_alternatives"

    return {
        "disruption": disruption.to_dict(),
        "headline": headline,
        "recommended_action": action,
        "alternatives_found": len(alternatives),
        "best": best.to_dict() if best else None,
        "alternatives": [o.to_dict() for o in alternatives],
        "excluded": [o.to_dict() for o in (ranked.get("excluded") or [])],
        "ranked_by": ranked.get("ranked_by"),
        "method": "ALGORITHMIC",
        "assumptions": ranked.get("assumptions"),
        # Stated in the payload so no caller can mistake this for an action.
        "original_order_untouched": True,
        "requires_confirmation": True,
        "next_step": ("Nothing has been changed. Choose an alternative to raise "
                      "a new order through the normal flow."),
    }
