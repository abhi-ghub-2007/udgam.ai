"""reviews.py — reputation earned on completed orders (F-8).

Three reputations, not one. A person is rated for the role they actually
played: a good farmer and a slow payer can be the same account, and collapsing
those into a single number would tell a counterparty nothing useful. The
`feedback` row therefore carries `ratee_role`, and every aggregate here is
scoped by the role the reviews were left about.

The table already carried most of the safety: `unique (order_id, rater_id,
ratee_id)` makes a second review of the same counterparty on the same order
impossible, `check (rater_id <> ratee_id)` makes self-review impossible, and
feedback_insert requires BOTH sides to have been on the order. What this module
adds is the part a constraint cannot express -- that the order actually
finished -- and the aggregate that the profile card reads.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..deps import CurrentUserDep
from ..errors import NotFound, ValidationFailed, Forbidden

router = APIRouter(prefix="/api", tags=["reviews"])

log = logging.getLogger("udgam.reviews")

# Reviewing is about how a completed deal went. An order that was cancelled
# never produced the performance being judged, and one still in flight has not
# produced it yet (§19 case 5).
REVIEWABLE_STATUSES = ("DELIVERED", "CLOSED")

# Kept short on purpose (§15): four vague dimensions collect noise, a handful
# of concrete tags collect signal, and they render as chips the UI can localise.
ALLOWED_TAGS = {
    "farmer": {"as_described", "on_time", "good_packing", "poor_quality", "late"},
    "buyer": {"paid_promptly", "clear_communication", "slow_payment", "changed_order"},
    "transporter": {"on_time", "careful_handling", "good_communication",
                     "late", "damaged_goods"},
}


class FeedbackIn(BaseModel):
    ratee_id: str
    rating: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list, max_length=5)
    comment: str | None = Field(default=None, max_length=1000)


def _recompute_rating(profile_id: str) -> None:
    """Refresh a profile's headline rating from the reviews it has.

    Service-role, and this is the only writer of avg_rating/rating_count.
    profiles_update_self restricts a profile row to its owner -- correctly,
    since the alternative is letting people edit each other's profiles -- so a
    reviewer's JWT cannot update the person they just reviewed. Deriving the
    aggregate here, from the rows themselves, also means the number can never
    drift from the reviews behind it: nothing writes a rating directly.
    """
    from ..db.admin_client import admin_client

    try:
        admin = admin_client()
        rows = (admin.table("feedback").select("rating")
                .eq("ratee_id", profile_id).execute().data) or []
        count = len(rows)
        avg = round(sum(r["rating"] for r in rows) / count, 2) if count else 0
        admin.table("profiles").update(
            {"avg_rating": avg, "rating_count": count}
        ).eq("id", profile_id).execute()
    except Exception:  # noqa: BLE001 - the review itself is already stored
        log.warning("could not recompute rating for %s", profile_id, exc_info=True)


def _role_on_order(db, order: dict, person_id: str) -> str | None:
    """Which role this person actually played on this order.

    Taken from the order and its shipment, never from the request body: a
    caller must not be able to label a farmer as the transporter and have the
    review filed under the wrong reputation.
    """
    if person_id == order.get("buyer_id"):
        return "buyer"
    if person_id == order.get("farmer_id"):
        return "farmer"
    ship = (db.table("shipments").select("transporter_id")
            .eq("order_id", order["id"]).neq("status", "cancelled")
            .limit(1).execute().data)
    if ship and ship[0].get("transporter_id") == person_id:
        return "transporter"
    item = (db.table("order_items").select("farmer_id")
            .eq("order_id", order["id"]).eq("farmer_id", person_id)
            .limit(1).execute().data)
    if item:
        return "farmer"
    return None


@router.get("/orders/{order_id}/feedback")
async def order_feedback(order_id: str, user: CurrentUserDep):
    """Who the caller may review on this order, and what they already said.

    Drives the UI directly, so the review form can only ever offer real,
    still-available counterparties.
    """
    order = (user.db.table("orders")
             .select("id,status,buyer_id,farmer_id,order_no")
             .eq("id", order_id).limit(1).execute().data)
    if not order:
        raise NotFound("Order not found.")
    order = order[0]

    my_role = _role_on_order(user.db, order, user.id)
    if not my_role:
        raise Forbidden("You were not part of this order.")

    existing = (user.db.table("feedback")
                .select("id,ratee_id,ratee_role,rating,tags,comment,created_at")
                .eq("order_id", order_id).execute().data) or []
    mine = {f["ratee_id"]: f for f in existing if f.get("ratee_id")}

    counterparties = []
    for pid in (order.get("buyer_id"), order.get("farmer_id")):
        if pid and pid != user.id:
            counterparties.append(pid)
    ship = (user.db.table("shipments").select("transporter_id")
            .eq("order_id", order_id).neq("status", "cancelled")
            .limit(1).execute().data)
    if ship and ship[0].get("transporter_id") and ship[0]["transporter_id"] != user.id:
        counterparties.append(ship[0]["transporter_id"])

    people = []
    if counterparties:
        profs = (user.db.table("profiles")
                 .select("id,full_name,role,avg_rating,rating_count")
                 .in_("id", counterparties).execute().data) or []
        by_id = {p["id"]: p for p in profs}
        for pid in counterparties:
            p = by_id.get(pid, {})
            people.append({
                "profile_id": pid,
                "full_name": p.get("full_name"),
                "role_on_order": _role_on_order(user.db, order, pid),
                "avg_rating": p.get("avg_rating"),
                "rating_count": p.get("rating_count") or 0,
                "already_reviewed": pid in mine,
                "my_review": mine.get(pid),
            })

    return {
        "order_id": order_id,
        "order_status": order["status"],
        # The UI shows the reason rather than a dead button.
        "can_review": order["status"] in REVIEWABLE_STATUSES,
        "reviewable_after": list(REVIEWABLE_STATUSES),
        "my_role": my_role,
        "counterparties": people,
    }


@router.post("/orders/{order_id}/feedback", status_code=201)
async def leave_feedback(order_id: str, body: FeedbackIn, user: CurrentUserDep):
    """Review a counterparty on a completed order (§16/§17).

    Everything is re-derived server-side. The body supplies only who is being
    reviewed and what the reviewer thought; the role the review is filed under,
    and the right to file it at all, come from the order.
    """
    order = (user.db.table("orders").select("id,status,buyer_id,farmer_id,order_no")
             .eq("id", order_id).limit(1).execute().data)
    if not order:
        raise NotFound("Order not found.")
    order = order[0]

    if order["status"] not in REVIEWABLE_STATUSES:
        raise ValidationFailed(
            "You can leave a review once the order has been delivered.",
            field="order_id")

    if body.ratee_id == user.id:
        raise ValidationFailed("You cannot review yourself.", field="ratee_id")

    if not _role_on_order(user.db, order, user.id):
        raise Forbidden("You were not part of this order.")

    ratee_role = _role_on_order(user.db, order, body.ratee_id)
    if not ratee_role:
        raise ValidationFailed("That person was not part of this order.",
                               field="ratee_id")

    bad = set(body.tags) - ALLOWED_TAGS.get(ratee_role, set())
    if bad:
        raise ValidationFailed(f"Unknown tag for a {ratee_role}: {', '.join(sorted(bad))}",
                               field="tags")

    row = {
        "order_id": order_id,
        "rater_id": user.id,          # never taken from the body
        "ratee_id": body.ratee_id,
        "ratee_role": ratee_role,     # derived, not declared
        "rating": body.rating,
        "tags": body.tags,
        "comment": (body.comment or "").strip() or None,
    }
    try:
        res = user.db.table("feedback").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        text = str(exc)
        if "feedback_order_id_rater_id_ratee_id_key" in text or "duplicate key" in text:
            raise ValidationFailed(
                "You have already reviewed them for this order.") from exc
        raise

    _recompute_rating(body.ratee_id)

    from .notifications import notify
    notify(body.ratee_id, "review_received", "notif.review_received_title",
           "notif.review_received_body",
           params={"order_no": order.get("order_no") or "", "rating": body.rating},
           entity_type="order", entity_id=order_id)

    return {"feedback": res.data[0] if res.data else None}


def _performance_stats(profile_id: str, role: str | None) -> dict:
    """Counts behind the stars: completed, cancelled, and on-time delivery.

    Every figure is COUNTED from orders and shipments — nothing here is stored
    on the profile or invented (§44). A metric the data cannot answer is
    omitted rather than filled with a plausible number.

    Reads run as the service role because orders_select scopes orders to their
    participants, so a stranger weighing this counterparty cannot count their
    history under their own JWT. Only aggregate counts leave this function: no
    order, price, or counterparty identity is exposed by it.
    """
    from ..db.admin_client import admin_client

    stats: dict[str, int | None] = {}
    try:
        admin = admin_client()
        if role == "transporter":
            ships = (admin.table("shipments")
                     .select("status,delivered_at,deliver_by")
                     .eq("transporter_id", profile_id).execute().data) or []
            done = [s for s in ships if s["status"] == "delivered"]
            # Only shipments that actually carried a deadline can be judged
            # late or on time; the rest are counted as neither.
            judgeable = [s for s in done if s.get("deliver_by") and s.get("delivered_at")]
            stats["completed"] = len(done)
            stats["cancelled"] = sum(1 for s in ships if s["status"] == "cancelled")
            stats["on_time"] = sum(
                1 for s in judgeable if s["delivered_at"] <= s["deliver_by"])
            stats["on_time_of"] = len(judgeable)
        else:
            col = "farmer_id" if role == "farmer" else "buyer_id"
            orders = (admin.table("orders").select("status")
                      .eq(col, profile_id).execute().data) or []
            stats["completed"] = sum(1 for o in orders if o["status"] == "CLOSED")
            stats["cancelled"] = sum(1 for o in orders if o["status"] == "CANCELLED")
            stats["disputed"] = sum(1 for o in orders if o["status"] == "DISPUTED")
    except Exception:  # noqa: BLE001 - reputation still renders without counts
        log.warning("could not compute performance stats for %s", profile_id,
                    exc_info=True)
        return {}
    return stats


@router.get("/profiles/{profile_id}/reviews")
async def profile_reviews(profile_id: str, user: CurrentUserDep,
                           role: str | None = None, limit: int = 10):
    """Public reputation for one profile, so a counterparty can be weighed
    BEFORE agreeing to deal with them (§20).

    Reads are public by policy (feedback_select is `using (true)`) — a
    reputation nobody can see is not a reputation. The per-role split is what
    makes it honest: `role=transporter` answers "how do they haul?", not "how
    are they in general".
    """
    prof = (user.db.table("profiles")
            .select("id,full_name,role,district,avg_rating,rating_count,"
                    "verification_status,created_at")
            .eq("id", profile_id).limit(1).execute().data)
    if not prof:
        raise NotFound("Profile not found.")
    prof = prof[0]

    q = user.db.table("feedback").select(
        "id,order_id,rating,tags,comment,ratee_role,created_at")
    q = q.eq("ratee_id", profile_id)
    if role:
        q = q.eq("ratee_role", role)
    rows = (q.order("created_at", desc=True).limit(max(1, min(limit, 50)))
            .execute().data) or []

    # Aggregate over ALL of this person's reviews in the role, not just the
    # page being shown, so the headline figure does not change with paging.
    all_q = user.db.table("feedback").select("rating,ratee_role").eq("ratee_id", profile_id)
    if role:
        all_q = all_q.eq("ratee_role", role)
    all_rows = (all_q.execute().data) or []
    count = len(all_rows)
    avg = round(sum(r["rating"] for r in all_rows) / count, 2) if count else None

    by_role: dict[str, dict] = {}
    for r in (user.db.table("feedback").select("rating,ratee_role")
              .eq("ratee_id", profile_id).execute().data) or []:
        b = by_role.setdefault(r["ratee_role"], {"count": 0, "total": 0})
        b["count"] += 1
        b["total"] += r["rating"]
    for k, v in by_role.items():
        v["avg_rating"] = round(v["total"] / v["count"], 2)
        v.pop("total")

    return {
        "profile": prof,
        "role": role,
        "avg_rating": avg,
        "review_count": count,
        "by_role": by_role,
        "performance": _performance_stats(profile_id, role or prof.get("role")),
        "reviews": rows,
        # These are reviews of demo transactions on a demo project, not
        # imported from anywhere; the UI says so rather than implying
        # third-party reviews.
        "method": "REAL",
        "source": "UDGAM completed orders",
    }
