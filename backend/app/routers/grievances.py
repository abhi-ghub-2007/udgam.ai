"""grievances.py -- the Grievance & Accountability Center.

WHAT THIS IS FOR
----------------
Everything else on UDGAM assumes the transaction goes well. This is the part
that assumes it does not. A farmer whose produce was collected late, a buyer
who received 380 kg against an order of 420, a transporter sent to an address
that does not exist -- each needs somewhere to say so, on the record, with the
other side obliged to answer.

WHAT THE CLIENT MAY AND MAY NOT SEND
------------------------------------
The client sends an ACTION ("acknowledge", "resolve"), never a status. There is
no field anywhere in this module that accepts `{"status": "RESOLVED"}`, so that
whole class of attack has nothing to aim at. Which actions are legal for whom,
from where, lives in services/grievance.py and nowhere else.

Context is derived here, not accepted. When a case is opened from an order, the
respondent, the shipment, and the order's status at that moment are read from
the database -- the client tells us WHICH order, and nothing more. A client
that could name its own respondent could file a complaint against a stranger.

THE SERVICE ROLE, AND WHERE IT IS NOT USED
------------------------------------------
Status changes, case creation, evidence rows and timeline events are written
with the service role, because `grievances` deliberately has no client write
policy (db/SCHEMA.sql section 16) -- the same footing as notifications (A-12),
and always AFTER this router has authorised the action.

Messages are the exception and are written through the sender's own JWT-bound
client, so Postgres itself checks that they are on the case. Where RLS can do
the work, it does.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field

from ..db.admin_client import admin_client
from ..deps import CurrentUserDep
from ..errors import Forbidden, NotFound, ValidationFailed
from ..services import grievance as gs
from .notifications import notify

log = logging.getLogger("udgam.grievances")

router = APIRouter(prefix="/api/grievances", tags=["grievances"])

EVIDENCE_BUCKET = "grievance-evidence"

# How long a signed evidence link stays usable. Long enough to open the image,
# short enough that a copied URL in a chat log is worthless by the time anyone
# else sees it.
EVIDENCE_URL_TTL_SECONDS = 300


# --------------------------------------------------------------- schemas
class GrievanceCreateIn(BaseModel):
    category: str = Field(min_length=2, max_length=40)
    subcategory: str = Field(min_length=2, max_length=40)
    description: str = Field(min_length=1, max_length=gs.MAX_DESCRIPTION)
    # Context. WHICH order -- never who is on the hook for it.
    related_order_id: str | None = None
    related_product_id: str | None = None
    related_request_id: str | None = None


class MessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=gs.MAX_MESSAGE)


class ActionIn(BaseModel):
    """An action, deliberately not a status.

    `resolution` is the structured outcome code that accompanies `resolve` and
    `propose_resolution`; it is ignored for every other action.
    """
    action: str = Field(min_length=2, max_length=32)
    resolution: str | None = None
    note: str | None = Field(default=None, max_length=gs.MAX_MESSAGE)


# --------------------------------------------------------------- helpers
def _event(admin, grievance_id: str, actor_id: str | None, actor_party: str | None,
           event_type: str, *, from_status=None, to_status=None, metadata=None):
    """Append to the timeline. Never raises: losing the audit line must not
    undo the thing it was recording."""
    try:
        admin.table("grievance_events").insert({
            "grievance_id": grievance_id,
            "actor_id": actor_id,
            "actor_party": actor_party,
            "event_type": event_type,
            "from_status": from_status,
            "to_status": to_status,
            "metadata": metadata or {},
        }).execute()
    except Exception:  # noqa: BLE001
        log.warning("could not record grievance event %s", event_type, exc_info=True)


def _load(user, grievance_id: str) -> dict:
    """Fetch a case the caller is allowed to see.

    Read through the caller's own client, so RLS -- not this function -- is
    what decides whether the row exists for them. A case belonging to two
    strangers is simply not there.
    """
    rows = (user.db.table("grievances").select("*")
            .eq("id", grievance_id).limit(1).execute()).data or []
    if not rows:
        raise NotFound("That case does not exist, or is not yours.")
    return rows[0]


def _derive_context(user, body: GrievanceCreateIn) -> dict:
    """Work out who this case is against and what it is about.

    All of it read server-side. The one thing the client chooses is which of
    ITS OWN orders to attach -- and even that is verified by reading the order
    back through the caller's RLS-scoped client, so naming a stranger's order
    finds nothing.
    """
    ctx: dict = {
        "respondent_id": None,
        "related_order_id": None,
        "related_shipment_id": None,
        "related_product_id": body.related_product_id,
        "related_request_id": body.related_request_id,
        "context_snapshot": {},
    }

    if body.category in gs.PLATFORM_ONLY_CATEGORIES:
        # Account and verification problems are ours. Nobody else answers them.
        return ctx

    if not body.related_order_id:
        return ctx

    orders = (user.db.table("orders")
              .select("id, order_no, status, buyer_id, farmer_id, "
                      "logistics_arranged_by, placed_at, delivered_at")
              .eq("id", body.related_order_id).limit(1).execute()).data or []
    if not orders:
        raise ValidationFailed("That order is not one of yours.",
                               field="related_order_id")
    order = orders[0]
    ctx["related_order_id"] = order["id"]

    ship = (user.db.table("shipments")
            .select("id, transporter_id, status")
            .eq("order_id", order["id"]).limit(1).execute()).data or []
    shipment = ship[0] if ship else None
    if shipment:
        ctx["related_shipment_id"] = shipment["id"]

    # Who should answer. Transport and pickup/delivery complaints belong to
    # whoever is actually carrying the goods -- routing them to the farmer
    # because they happen to be the counterparty would be useless to everyone.
    respondent = None
    if body.category in ("transport", "pickup_delivery") and shipment:
        respondent = shipment.get("transporter_id")
    if not respondent:
        respondent = (order["farmer_id"] if str(order["buyer_id"]) == str(user.id)
                      else order["buyer_id"])
    # A transporter complaining about the order itself answers to whoever
    # arranged it; if that resolves to themselves, leave it unassigned rather
    # than creating a case somebody files against their own account.
    if respondent and str(respondent) == str(user.id):
        respondent = None
    ctx["respondent_id"] = respondent

    # The order moves on. The complaint is about how it was at this moment.
    ctx["context_snapshot"] = {
        "order_no": order.get("order_no"),
        "order_status": order.get("status"),
        "logistics_arranged_by": order.get("logistics_arranged_by"),
        "shipment_status": (shipment or {}).get("status"),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    return ctx


def _names(admin, ids: set[str]) -> dict[str, str]:
    """Display names for the people on a case. Names only -- a dispute does
    not entitle either side to the other's contact details."""
    ids = {str(i) for i in ids if i}
    if not ids:
        return {}
    rows = (admin.table("profiles").select("id, full_name")
            .in_("id", list(ids)).execute()).data or []
    return {str(r["id"]): r.get("full_name") or "" for r in rows}


def _notify_counterpart(case: dict, actor_id: str, event: str):
    """Tell the other side something happened. Best-effort by design."""
    other = (case.get("respondent_id")
             if str(case.get("created_by")) == str(actor_id)
             else case.get("created_by"))
    if not other or str(other) == str(actor_id):
        return
    notify(str(other), "grievance",
           f"notif.grv_{event}_title", f"notif.grv_{event}_body",
           {"case_number": case.get("case_number")},
           entity_type="grievance", entity_id=str(case["id"]))


# ------------------------------------------------------------- taxonomy
@router.get("/taxonomy")
async def taxonomy(user: CurrentUserDep):
    """What may be reported, and what outcomes exist.

    Served from the backend so the two never disagree: a category the client
    could offer but the server would reject is a dead end the user walks into.
    """
    return {
        "categories": {c: list(subs) for c, subs in gs.CATEGORIES.items()},
        "resolutions": list(gs.RESOLUTIONS),
        "platform_only": list(gs.PLATFORM_ONLY_CATEGORIES),
    }


# ------------------------------------------------------------------ list
@router.get("")
async def list_grievances(user: CurrentUserDep):
    """Every case the caller is a party to, either side.

    RLS scopes this: the query asks for all grievances and Postgres returns
    only the ones this user is on.
    """
    rows = (user.db.table("grievances").select("*")
            .order("created_at", desc=True).limit(100).execute()).data or []

    admin = admin_client()
    names = _names(admin, {r.get("created_by") for r in rows}
                   | {r.get("respondent_id") for r in rows})

    cases = []
    for r in rows:
        role = gs.party(r, user.id)
        other = (r.get("respondent_id") if role == "complainant"
                 else r.get("created_by"))
        cases.append({
            "id": r["id"],
            "case_number": r["case_number"],
            "category": r["category"],
            "subcategory": r["subcategory"],
            "status": r["status"],
            "my_party": role,
            "counterparty_name": names.get(str(other)) if other else None,
            "order_no": (r.get("context_snapshot") or {}).get("order_no"),
            "related_order_id": r.get("related_order_id"),
            "created_at": r["created_at"],
            "updated_at": r.get("updated_at"),
        })

    return {"cases": cases, "summary": gs.summarise(rows)}


# ---------------------------------------------------------------- create
@router.post("", status_code=201)
async def create_grievance(body: GrievanceCreateIn, user: CurrentUserDep):
    """Open a case.

    Validation happens before anything is written, so a rejected submission
    leaves no half-created case behind.
    """
    problem = gs.validate_category(body.category, body.subcategory)
    if problem:
        raise ValidationFailed(problem, field="subcategory")
    problem = gs.validate_description(body.description)
    if problem:
        raise ValidationFailed(problem, field="description")

    ctx = _derive_context(user, body)

    admin = admin_client()
    payload = {
        "created_by": user.id,
        "created_role": user.role,
        "category": body.category,
        "subcategory": body.subcategory,
        "description": body.description.strip(),
        "status": gs.OPEN,
        **ctx,
    }
    res = admin.table("grievances").insert(payload).execute()
    if not res.data:
        raise ValidationFailed("Could not open the case. Please try again.")
    case = res.data[0]

    _event(admin, case["id"], user.id, "complainant", "submitted",
           to_status=gs.OPEN,
           metadata={"category": body.category, "subcategory": body.subcategory})
    _notify_counterpart(case, user.id, "opened")

    return {"case": case}


# ---------------------------------------------------------------- detail
@router.get("/{grievance_id}")
async def get_grievance(grievance_id: str, user: CurrentUserDep):
    """The full case: timeline, messages, evidence, and what the caller may do.

    `available_actions` drives which buttons appear. It is NOT what authorises
    them -- POST /actions re-derives the same answer from the same function, so
    a caller who forges a button gets 403 rather than a state change.
    """
    case = _load(user, grievance_id)

    timeline = (user.db.table("grievance_events").select("*")
                .eq("grievance_id", grievance_id)
                .order("created_at").execute()).data or []
    messages = (user.db.table("grievance_messages").select("*")
                .eq("grievance_id", grievance_id)
                .order("created_at").execute()).data or []
    evidence = (user.db.table("grievance_evidence")
                .select("id, uploaded_by, file_type, file_size, created_at")
                .eq("grievance_id", grievance_id)
                .order("created_at").execute()).data or []

    admin = admin_client()
    participants = {case.get("created_by"), case.get("respondent_id")}
    names = _names(admin, participants | {m.get("sender_id") for m in messages})

    my_party = gs.party(case, user.id)
    other = (case.get("respondent_id") if my_party == "complainant"
             else case.get("created_by"))

    for m in messages:
        m["sender_name"] = names.get(str(m.get("sender_id")))
        m["sender_party"] = ("complainant"
                             if str(m.get("sender_id")) == str(case["created_by"])
                             else "respondent")

    return {
        "case": case,
        "my_party": my_party,
        "counterparty_name": names.get(str(other)) if other else None,
        "timeline": timeline,
        "messages": messages,
        "evidence": evidence,
        "available_actions": gs.available_actions(case, user.id),
        "resolutions": list(gs.RESOLUTIONS),
    }


# -------------------------------------------------------------- messages
@router.post("/{grievance_id}/messages", status_code=201)
async def add_message(grievance_id: str, body: MessageIn, user: CurrentUserDep):
    """Say something on the case.

    Written through the caller's own client on purpose: the RLS policy checks
    both that they are a participant and that sender_id is genuinely them, so
    nobody can put words in the other side's mouth even by talking to PostgREST
    directly.
    """
    case = _load(user, grievance_id)
    if gs.party(case, user.id) is None:
        raise Forbidden("This case is not yours.")
    if case["status"] == gs.CLOSED:
        raise ValidationFailed("This case is closed. Reopen it to add anything.")

    res = user.db.table("grievance_messages").insert({
        "grievance_id": grievance_id,
        "sender_id": user.id,
        "message": body.message.strip(),
    }).execute()
    if not res.data:
        raise ValidationFailed("Could not post that message.")

    admin = admin_client()
    _event(admin, grievance_id, user.id, gs.party(case, user.id), "message_added")
    _notify_counterpart(case, user.id, "message")
    return {"message": res.data[0]}


# --------------------------------------------------------------- actions
@router.post("/{grievance_id}/actions")
async def act(grievance_id: str, body: ActionIn, user: CurrentUserDep):
    """Move the case.

    The one write path for status, and the only authority check is
    `gs.can_act`. A respondent proposing an outcome does NOT resolve the case;
    only the complainant can do that, which is why nobody can clear themselves.
    """
    case = _load(user, grievance_id)
    action = body.action.strip()

    if action not in gs.ACTIONS:
        raise ValidationFailed("That is not something you can do on a case.")
    if not gs.can_act(case, user.id, action):
        # Deliberately one message for both "not your move" and "not from this
        # state": telling a caller which one it was maps out the state machine.
        raise Forbidden("You cannot do that on this case right now.")

    if action in ("resolve", "propose_resolution"):
        if body.resolution not in gs.RESOLUTIONS:
            raise ValidationFailed("Choose what the outcome was.", field="resolution")

    to_status = gs.next_status(action)
    now = datetime.now(timezone.utc).isoformat()
    patch: dict = {"status": to_status}

    if action == "resolve":
        patch["resolution"] = body.resolution
        patch["resolution_note"] = (body.note or "").strip() or None
        patch["resolved_at"] = now
    elif action == "propose_resolution":
        # Recorded, not applied. The complainant still has to accept it.
        patch["proposed_resolution"] = body.resolution
    elif action == "close":
        patch["closed_at"] = now
    elif action == "reopen":
        # The previous resolution stays on the record -- history is not erased,
        # it is superseded, and the timeline shows both.
        patch["resolved_at"] = None
        patch["closed_at"] = None

    admin = admin_client()
    admin.table("grievances").update(patch).eq("id", grievance_id).execute()

    _event(admin, grievance_id, user.id, gs.party(case, user.id), action,
           from_status=case["status"], to_status=to_status,
           metadata={k: v for k, v in
                     {"resolution": body.resolution,
                      "note": (body.note or "").strip() or None}.items() if v})

    if (body.note or "").strip():
        # An action's note is part of the conversation, not buried in metadata.
        try:
            user.db.table("grievance_messages").insert({
                "grievance_id": grievance_id, "sender_id": user.id,
                "message": body.note.strip(),
            }).execute()
        except Exception:  # noqa: BLE001 - the transition already happened
            log.warning("could not attach note to action %s", action, exc_info=True)

    _notify_counterpart(case, user.id, "updated")

    fresh = (admin.table("grievances").select("*")
             .eq("id", grievance_id).limit(1).execute()).data[0]
    return {"case": fresh,
            "available_actions": gs.available_actions(fresh, user.id)}


# -------------------------------------------------------------- evidence
@router.post("/{grievance_id}/evidence", status_code=201)
async def upload_evidence(grievance_id: str, user: CurrentUserDep,
                          file: UploadFile = File(...)):
    """Attach a photo or a document.

    Uploaded THROUGH the backend, exactly like listing photos: the browser
    never holds a storage credential, and the bucket stays private so an
    object path is worthless without a signed URL this server issues.

    The file type is decided by sniffing the bytes, not by trusting the
    Content-Type the browser announced.
    """
    case = _load(user, grievance_id)
    if gs.party(case, user.id) is None:
        raise Forbidden("This case is not yours.")
    if case["status"] == gs.CLOSED:
        raise ValidationFailed("This case is closed. Reopen it to add evidence.")

    admin = admin_client()
    existing = (admin.table("grievance_evidence").select("id", count="exact")
                .eq("grievance_id", grievance_id).limit(1).execute()).count or 0
    if existing >= gs.MAX_EVIDENCE_PER_CASE:
        raise ValidationFailed(
            f"A case can hold {gs.MAX_EVIDENCE_PER_CASE} files. "
            "Remove one before adding another.")

    data = await file.read()
    problem = gs.validate_evidence(data)
    if problem:
        raise ValidationFailed(problem, field="file")
    mime, ext = gs.sniff_evidence(data)  # type: ignore[misc]  # validated above

    path = f"{grievance_id}/{uuid.uuid4()}.{ext}"
    try:
        admin.storage.from_(EVIDENCE_BUCKET).upload(
            path, data, {"content-type": mime})
    except Exception as exc:  # noqa: BLE001
        # Unlike a listing photo, evidence that silently vanished would be
        # worse than an error -- somebody would believe they had filed it.
        log.warning("evidence upload failed for case %s", grievance_id, exc_info=True)
        raise ValidationFailed(
            "The file could not be stored. Please try again.") from exc

    row = admin.table("grievance_evidence").insert({
        "grievance_id": grievance_id,
        "uploaded_by": user.id,
        "storage_path": path,
        "file_type": mime,
        "file_size": len(data),
    }).execute().data[0]

    _event(admin, grievance_id, user.id, gs.party(case, user.id),
           "evidence_added", metadata={"file_type": mime})
    _notify_counterpart(case, user.id, "evidence")

    # The path never goes to the client -- only the row id it can ask about.
    return {"evidence": {k: row[k] for k in
                         ("id", "uploaded_by", "file_type", "file_size", "created_at")}}


@router.get("/{grievance_id}/evidence/{evidence_id}")
async def evidence_link(grievance_id: str, evidence_id: str, user: CurrentUserDep):
    """A short-lived link to one file.

    Two checks, both server-side: the caller can read the case (RLS), and the
    file genuinely belongs to that case. The bucket is private, so this is the
    only way to see it and the link expires in minutes.
    """
    case = _load(user, grievance_id)
    if gs.party(case, user.id) is None:
        raise Forbidden("This case is not yours.")

    rows = (user.db.table("grievance_evidence").select("id, storage_path, file_type")
            .eq("id", evidence_id).eq("grievance_id", grievance_id)
            .limit(1).execute()).data or []
    if not rows:
        raise NotFound("That file is not on this case.")

    try:
        signed = admin_client().storage.from_(EVIDENCE_BUCKET).create_signed_url(
            rows[0]["storage_path"], EVIDENCE_URL_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        log.warning("could not sign evidence url", exc_info=True)
        raise NotFound("That file could not be opened right now.") from exc

    url = signed.get("signedURL") or signed.get("signedUrl") if isinstance(signed, dict) else None
    if not url:
        raise NotFound("That file could not be opened right now.")
    return {"url": url, "expires_in": EVIDENCE_URL_TTL_SECONDS,
            "file_type": rows[0]["file_type"]}
