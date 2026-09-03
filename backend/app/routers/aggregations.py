"""aggregations.py — Dynamic Supply Aggregation (SIH26132 Feature 2).

The lifecycle, and who may move each step:

    POST /suggest              buyer    writes 'suggested' rows only
    GET  /mine                 buyer    groups they created
    GET  /invitations          farmer   lines awaiting their answer
    POST /{id}/items/{iid}/consent
                               farmer   accept or reject THEIR OWN line
    POST /{id}/confirm         buyer    reserves inventory, accepted lines only
    POST /{id}/cancel          buyer    releases anything already reserved

Inventory moves at exactly one point: confirm(). Nothing else in this file
touches products.available_quantity_kg. A suggestion is a proposal, not a claim
on anyone's crop.

Availability is re-checked inside confirm() rather than trusted from the
suggestion, because a proposal computed minutes ago proves nothing about now —
that is the concurrency guard against two buyers confirming the same kilos.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import CurrentUserDep, require_role
from ..errors import Forbidden, InvalidStateTransition, NotFound, ValidationFailed
from ..services import aggregation as agg

router = APIRouter(prefix="/api/aggregations", tags=["aggregations"])

require_buyer = Depends(require_role("buyer"))
require_farmer = Depends(require_role("farmer"))

_LIVE_STATUSES = ("suggested", "accepted")


class SuggestIn(BaseModel):
    buyer_request_id: str
    persist: bool = Field(
        default=False,
        description="False previews without writing. True stores the group as "
                    "'suggested' so farmers can be asked to consent.",
    )


class ConsentIn(BaseModel):
    accept: bool


def _uuid_or_404(value: str, message: str) -> str:
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise NotFound(message)
    return str(value)


def _committed_quantities(db, _scope=None, *,
                          exclude_aggregation_id: str | None = None) -> dict[str, float]:
    """How much of each lot is already spoken for by live aggregations.

    This is the reservation ledger. A confirmed group holds its claim through
    its own aggregation_items rows rather than by decrementing the farmer's
    listing, so this function is what stops the same kilos being offered or
    confirmed twice. Only 'suggested' and 'accepted' groups hold a claim;
    rejected and expired ones release theirs by falling out of the filter.

    `exclude_aggregation_id` omits one group — used when checking whether that
    group's own lines are still available, so it does not count itself.
    """
    live = (db.table("aggregations").select("id, status")
            .in_("status", list(_LIVE_STATUSES)).limit(500).execute()).data or []
    ids = [a["id"] for a in live if str(a["id"]) != str(exclude_aggregation_id)]
    if not ids:
        return {}
    items = (db.table("aggregation_items")
             .select("product_id, quantity_kg, consent_status")
             .in_("aggregation_id", ids).limit(2000).execute()).data or []
    held: dict[str, float] = {}
    for it in items:
        if it.get("consent_status") == "rejected":
            continue
        pid = str(it["product_id"])
        held[pid] = held.get(pid, 0.0) + float(it.get("quantity_kg") or 0)
    return held


@router.post("/suggest", dependencies=[require_buyer])
async def suggest(body: SuggestIn, user: CurrentUserDep):
    """Propose a set of lots that together fill one of the caller's requirements.

    Insufficient supply is a legitimate answer, reported as `sufficient: false`
    with the shortfall and a reason for every lot that was passed over — never
    padded out to look complete.
    """
    db = user.db
    rid = _uuid_or_404(body.buyer_request_id, "That requirement does not exist.")

    req = (db.table("buyer_requests").select("*").eq("id", rid).limit(1).execute()).data
    if not req:
        raise NotFound("That requirement does not exist.")
    request = req[0]
    if str(request.get("buyer_id")) != str(user.id):
        raise Forbidden("That requirement belongs to another buyer.")
    if request.get("status") != "open":
        raise InvalidStateTransition(
            f"This requirement is {request.get('status')}; only open ones can be aggregated.")

    products = (db.table("products")
                .select("*, profiles!products_farmer_id_fkey(full_name)")
                .eq("crop_id", request["crop_id"]).eq("status", "active")
                .limit(200).execute()).data or []
    for p in products:
        p["farmer_name"] = (p.pop("profiles", None) or {}).get("full_name")

    proposal = agg.propose(
        request=request, products=products,
        committed=_committed_quantities(db, request["crop_id"]),
    )

    stored = None
    if body.persist and proposal.items:
        row = (db.table("aggregations").insert({
            "buyer_request_id": rid,
            "buyer_id": str(user.id),
            "status": "suggested",
            "total_quantity_kg": proposal.covered_kg,
            "combined_price_paise": proposal.combined_price_paise,
            "grade_variance_warning": proposal.grade_variance_warning,
            "method": "ALGORITHMIC",
        }).execute()).data[0]
        db.table("aggregation_items").insert([{
            "aggregation_id": row["id"],
            "product_id": i.product_id,
            "farmer_id": i.farmer_id,
            "quantity_kg": i.take_kg,
            "unit_price_paise": i.unit_price_paise,
            "consent_status": "suggested",
        } for i in proposal.items]).execute()
        stored = row["id"]

    return {
        **proposal.to_dict(),
        "persisted": stored is not None,
        "aggregation_id": stored,
        "next_step": (
            "Each farmer is asked to accept their line; confirm once enough have."
            if stored else "Preview only — nothing has been written or reserved."
        ),
    }


@router.get("/mine", dependencies=[require_buyer])
async def my_aggregations(user: CurrentUserDep):
    rows = (user.db.table("aggregations").select("*")
            .eq("buyer_id", str(user.id))
            .order("created_at", desc=True).limit(50).execute()).data or []
    for r in rows:
        items = (user.db.table("aggregation_items").select("*")
                 .eq("aggregation_id", r["id"]).execute()).data or []
        r["items"] = items
        r["accepted_kg"] = round(sum(
            float(i["quantity_kg"]) for i in items
            if i.get("consent_status") == "accepted"), 3)
        r["awaiting_consent"] = sum(
            1 for i in items if i.get("consent_status") == "suggested")
    return {"aggregations": rows}


@router.get("/invitations", dependencies=[require_farmer])
async def my_invitations(user: CurrentUserDep):
    """Aggregation lines this farmer has been invited into."""
    items = (user.db.table("aggregation_items").select("*")
             .eq("farmer_id", str(user.id)).limit(100).execute()).data or []
    return {"invitations": items}


@router.post("/{aggregation_id}/items/{item_id}/consent", dependencies=[require_farmer])
async def consent(aggregation_id: str, item_id: str, body: ConsentIn,
                  user: CurrentUserDep):
    """The farmer answers for their own line. Nothing is reserved here.

    RLS (agg_items_farmer_consent) already restricts a farmer to UPDATE of their
    own row; the ownership assertion below makes an attempt fail loudly rather
    than silently updating nothing.
    """
    db = user.db
    aid = _uuid_or_404(aggregation_id, "That aggregation does not exist.")
    iid = _uuid_or_404(item_id, "That aggregation line does not exist.")

    rows = (db.table("aggregation_items").select("*")
            .eq("id", iid).eq("aggregation_id", aid).limit(1).execute()).data
    if not rows:
        raise NotFound("That aggregation line does not exist.")
    item = rows[0]
    if str(item.get("farmer_id")) != str(user.id):
        raise Forbidden("That line belongs to another farmer.")
    if item.get("consent_status") not in ("suggested", "accepted"):
        raise InvalidStateTransition(
            f"This line is already {item.get('consent_status')}.")

    updated = (db.table("aggregation_items").update({
        "consent_status": "accepted" if body.accept else "rejected",
        "consent_at": "now()",
    }).eq("id", iid).execute()).data
    return {"item": updated[0] if updated else None,
            "reserved": False,
            "next_step": "The buyer confirms the group once enough lines are accepted."}


@router.post("/{aggregation_id}/confirm", dependencies=[require_buyer])
async def confirm(aggregation_id: str, user: CurrentUserDep):
    """Reserve the accepted lines. The only place inventory moves.

    Availability is re-read here and each decrement is guarded, so two buyers
    confirming overlapping suggestions cannot both win the same kilos: the
    second finds the quantity already gone and its line is reported as
    unavailable rather than silently over-allocating.
    """
    db = user.db
    aid = _uuid_or_404(aggregation_id, "That aggregation does not exist.")

    rows = (db.table("aggregations").select("*").eq("id", aid).limit(1).execute()).data
    if not rows:
        raise NotFound("That aggregation does not exist.")
    group = rows[0]
    if str(group.get("buyer_id")) != str(user.id):
        raise Forbidden("That aggregation belongs to another buyer.")
    if group.get("status") != "suggested":
        raise InvalidStateTransition(
            f"This aggregation is already {group.get('status')}.")

    items = (db.table("aggregation_items").select("*")
             .eq("aggregation_id", aid).execute()).data or []
    accepted = [i for i in items if i.get("consent_status") == "accepted"]
    if not accepted:
        raise ValidationFailed(
            "No farmer has accepted their line yet, so there is nothing to reserve.")

    # Reservation is DERIVED, never a write to the farmer's listing.
    #
    # products.available_quantity_kg belongs to the farmer — products_update is
    # `farmer_id = auth.uid()`, so a buyer cannot decrement it, and weakening
    # that policy to let them would hand buyers write access to crop listings.
    # Instead a confirmed group's own aggregation_items rows ARE the claim:
    # _committed_quantities() subtracts them everywhere availability is computed,
    # so the same kilos can never be offered or confirmed twice. The listing is
    # left exactly as the farmer wrote it (PRD B-7: never silently mutated).
    held_elsewhere = _committed_quantities(db, group.get("buyer_request_id"),
                                           exclude_aggregation_id=aid)
    reserved, unavailable = [], []
    for it in accepted:
        pid = str(it["product_id"])
        want = float(it["quantity_kg"])
        prod = (db.table("products").select("id, available_quantity_kg, status")
                .eq("id", pid).limit(1).execute()).data
        if not prod:
            unavailable.append({"product_id": pid, "reason": "listing no longer exists"})
            continue
        if prod[0].get("status") != "active":
            unavailable.append({"product_id": pid,
                                "reason": f"listing is now {prod[0].get('status')}"})
            continue
        free = float(prod[0].get("available_quantity_kg") or 0) - held_elsewhere.get(pid, 0.0)
        if free < want:
            unavailable.append({
                "product_id": pid,
                "reason": f"only {max(free, 0):g} kg still uncommitted, {want:g} kg needed",
            })
            continue
        reserved.append({"product_id": pid, "quantity_kg": want})

    if not reserved:
        raise InvalidStateTransition(
            "None of the accepted lines are still available; nothing was reserved.")

    db.table("aggregations").update({
        "status": "accepted",
        "total_quantity_kg": round(sum(r["quantity_kg"] for r in reserved), 3),
    }).eq("id", aid).execute()

    return {
        "aggregation_id": aid,
        "status": "accepted",
        "reserved": reserved,
        "unavailable": unavailable,
        "reserved_kg": round(sum(r["quantity_kg"] for r in reserved), 3),
        "next_step": "Create the order from this aggregation to proceed.",
    }


@router.post("/{aggregation_id}/cancel", dependencies=[require_buyer])
async def cancel(aggregation_id: str, user: CurrentUserDep):
    """Release a group. Anything reserved by confirm() is given back."""
    db = user.db
    aid = _uuid_or_404(aggregation_id, "That aggregation does not exist.")

    rows = (db.table("aggregations").select("*").eq("id", aid).limit(1).execute()).data
    if not rows:
        raise NotFound("That aggregation does not exist.")
    group = rows[0]
    if str(group.get("buyer_id")) != str(user.id):
        raise Forbidden("That aggregation belongs to another buyer.")
    if group.get("status") == "rejected":
        raise InvalidStateTransition("This aggregation is already cancelled.")

    # Releasing is the mirror of reserving: the group leaves _LIVE_STATUSES, so
    # its aggregation_items stop counting against availability. No listing is
    # written here either, because none was written on confirm.
    items = (db.table("aggregation_items").select("product_id, quantity_kg, consent_status")
             .eq("aggregation_id", aid).eq("consent_status", "accepted").execute()).data or []
    released = [{"product_id": str(i["product_id"]),
                 "quantity_kg": float(i["quantity_kg"])} for i in items]

    db.table("aggregations").update({"status": "rejected"}).eq("id", aid).execute()
    return {
        "aggregation_id": aid,
        "status": "rejected",
        "released": released,
        "released_kg": round(sum(r["quantity_kg"] for r in released), 3),
    }
