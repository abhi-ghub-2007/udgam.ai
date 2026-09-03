"""Phone masking (A-13).

PRD section 11: phone numbers stay masked until an order between the two
parties reaches ACCEPTED. This deliberately lives OUTSIDE RLS, because a
row-level policy cannot hide a single column - it can only hide the whole
row, and counterparty discovery needs the rest of the profile visible.
"""
from __future__ import annotations

# Statuses at or past ACCEPTED: contact details are legitimately needed to
# coordinate a real handover.
CONTACT_VISIBLE_STATUSES = (
    "ACCEPTED", "PAYMENT_HELD", "LOGISTICS_ASSIGNED",
    "PICKED_UP", "IN_TRANSIT", "DELIVERED", "CLOSED", "DISPUTED",
)


def mask_phone(phone: str | None) -> str | None:
    """'+919876543210' -> '+91 ..... 3210'. Enough to confirm a match, not
    enough to contact someone off-platform before a deal exists."""
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 4:
        return "....."
    return f"+91 ..... {digits[-4:]}"


def may_see_phone(user, other_profile_id: str) -> bool:
    """True when the caller shares an order with `other_profile_id` that has
    reached ACCEPTED or beyond."""
    if user.id == other_profile_id:
        return True

    db = user.db
    # Orders where the two are the buyer/farmer pair, either way round.
    res = (
        db.table("orders")
        .select("id, buyer_id, farmer_id, status")
        .in_("status", list(CONTACT_VISIBLE_STATUSES))
        .or_(f"buyer_id.eq.{user.id},farmer_id.eq.{user.id}")
        .execute()
    )
    for o in res.data or []:
        if other_profile_id in (o.get("buyer_id"), o.get("farmer_id")):
            return True

    # Aggregated orders: the counterparty may be a line-item farmer instead.
    order_ids = [o["id"] for o in res.data or []]
    if order_ids:
        items = (
            db.table("order_items")
            .select("order_id, farmer_id")
            .in_("order_id", order_ids)
            .eq("farmer_id", other_profile_id)
            .limit(1)
            .execute()
        )
        if items.data:
            return True

    # The assigned transporter needs both parties' numbers, and vice versa.
    ship = (
        db.table("shipments")
        .select("order_id, transporter_id")
        .or_(f"transporter_id.eq.{user.id},transporter_id.eq.{other_profile_id}")
        .execute()
    )
    ship_order_ids = {s["order_id"] for s in ship.data or []}
    return bool(ship_order_ids & set(order_ids))
