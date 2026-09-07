"""verification.py — identity and credential verification.

THE AUTHORITY BOUNDARY
----------------------
The client submits a credential. This router decides its status. Those are
different powers and they are separated here and in the database: triggers
(db/SCHEMA.sql) force any write arriving as `authenticated` back to `pending`
and strip provider/verified_at, so even a caller talking straight to PostgREST
with their own JWT cannot award themselves a badge. Verified live before the
triggers existed: a demo buyer PATCHed their own profiles.verification_status
to 'verified' and got HTTP 200.

Status changes are therefore written with the service role -- that is the
system acting, not the user, which is the same footing seed_demo.py stands on
(A-12). Nothing else about the row is trusted from the client either: the
value is re-validated and re-masked server-side, and only the mask is stored.

WHAT NEVER LEAVES THIS MODULE
-----------------------------
Raw credential values. They are validated, masked, and discarded inside the
request that carried them -- never persisted, never logged, never echoed back,
never put in an audit note.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..deps import CurrentUserDep
from ..errors import Duplicate, NotFound, ValidationFailed
from ..services import verification as vs

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/verification", tags=["verification"])

# Rate limiting (rule 39). Submissions are cheap for us and useful to an
# attacker probing which identifiers already exist, so a caller gets a small
# burst per credential type and then has to wait.
MAX_SUBMISSIONS_PER_WINDOW = 5
RATE_WINDOW_MINUTES = 15


class SubmitIn(BaseModel):
    doc_type: str = Field(min_length=2, max_length=32)
    # The raw credential. Validated and masked in this request, then dropped.
    value: str = Field(min_length=1, max_length=64)
    # Only meaningful for credentials that lapse.
    expires_on: str | None = None


def _admin():
    from ..db.admin_client import admin_client
    return admin_client()


def _public_row(row: dict) -> dict:
    """The shape the owner may see. Contains the mask, never a raw value."""
    expiry_grade = vs.grade_expiry(row.get("expires_at"))
    status = row.get("status")
    # An expired credential stops reading as verified, whatever the column says.
    if expiry_grade == "expired" and status == vs.STATUS_VERIFIED:
        status = vs.STATUS_EXPIRED
    return {
        "doc_type": row["doc_type"],
        "status": status,
        "masked_value": row.get("doc_number_masked"),
        "format_valid": row.get("format_valid"),
        "provider": row.get("provider"),
        "submitted_at": row.get("submitted_at"),
        "verified_at": row.get("verified_at"),
        "expires_at": row.get("expires_at"),
        "expiry": expiry_grade,
        "rejected_reason": row.get("rejected_reason"),
    }


def _audit(admin, profile_id: str, doc_type: str, event: str,
           *, from_status=None, to_status=None, provider=None, note=None):
    """Append-only trail. Never carries a credential value."""
    try:
        admin.table("verification_events").insert({
            "profile_id": profile_id, "doc_type": doc_type, "event": event,
            "from_status": from_status, "to_status": to_status,
            "actor": "system", "provider": provider, "note": note,
        }).execute()
    except Exception:  # noqa: BLE001 - an audit failure must not lose the decision
        log.warning("could not record verification event", exc_info=True)


def _sync_account_status(admin, profile_id: str, credentials: list[dict]):
    """Keep profiles.verification_status in step with the credentials.

    Written by the system for the same reason the trigger exists: this column
    drives trust badges across the marketplace, so the user must not own it.
    """
    try:
        admin.table("profiles").update(
            {"verification_status": vs.account_status(credentials)}
        ).eq("id", profile_id).execute()
    except Exception:  # noqa: BLE001
        log.warning("could not sync account verification status", exc_info=True)


@router.get("/me")
async def my_verification(user: CurrentUserDep):
    """The caller's own credentials, progress, and what their role is asked for."""
    rows = (user.db.table("kyc_documents").select("*")
            .eq("profile_id", user.id).execute()).data or []
    creds = [_public_row(r) for r in rows]
    role = user.role or ""
    return {
        "role": role,
        "credentials": creds,
        # Which fields to show. A buyer is never offered a transport permit.
        "applicable": {
            "identity": list(vs.IDENTITY_TYPES),
            "role_credentials": list(vs.ROLE_CREDENTIALS.get(role.lower(), ())),
        },
        "progress": vs.progress(role, creds),
        "verification_mode": vs.verification_mode(),
        # True only where an authorised integration actually exists, so the UI
        # can say "manual review" instead of implying an instant check.
        "automated_available": {t: vs.authority_available(t)
                                for t in vs.relevant_types(role)},
    }


@router.post("/submit")
async def submit_credential(body: SubmitIn, user: CurrentUserDep):
    """Submit or resubmit one credential.

    Format is validated here, not on the client's word. The resulting status
    comes from the verification service, and in this deployment that is
    `pending` for everything -- there is no authorised integration to call.
    """
    doc_type = body.doc_type.strip().lower()
    role = (user.role or "").lower()

    if doc_type not in vs.ALL_TYPES:
        raise ValidationFailed("That is not a credential we collect.")
    if doc_type not in vs.relevant_types(role):
        # Role compatibility (rule 20): a buyer has no business filing a permit.
        raise ValidationFailed("That credential does not apply to your account type.")

    admin = _admin()

    # Rate limit before doing any work with the value.
    since = (datetime.now(timezone.utc)
             - timedelta(minutes=RATE_WINDOW_MINUTES)).isoformat()
    recent = (admin.table("verification_events").select("id", count="exact")
              .eq("profile_id", user.id).eq("doc_type", doc_type)
              .gte("created_at", since).limit(1).execute()).count or 0
    if recent >= MAX_SUBMISSIONS_PER_WINDOW:
        raise ValidationFailed(
            "Too many attempts for this credential. Please wait a few minutes "
            "before trying again.")

    fmt = vs.validate_format(doc_type, body.value)
    if not fmt.valid:
        _audit(admin, user.id, doc_type, "format_rejected",
               note="failed local format validation")
        raise ValidationFailed(fmt.message or "That value does not look right.")

    masked = vs.mask(doc_type, body.value)

    # Duplicate identity (rule 21). Deliberately vague: confirming which
    # account holds a given identifier would leak it.
    if doc_type in vs.IDENTITY_TYPES:
        clash = (admin.table("kyc_documents").select("profile_id")
                 .eq("doc_type", doc_type).eq("doc_number_masked", masked)
                 .eq("status", vs.STATUS_VERIFIED).limit(1).execute()).data or []
        if clash and str(clash[0]["profile_id"]) != str(user.id):
            raise Duplicate(
                "This identity credential is already associated with another "
                "verified account. Please contact support if you believe this "
                "is an error.")

    outcome = vs.verify(doc_type, body.value)

    expires_at = None
    if doc_type in vs.EXPIRING_TYPES and body.expires_on:
        try:
            expires_at = datetime.fromisoformat(body.expires_on[:10]).replace(
                tzinfo=timezone.utc).isoformat()
        except ValueError:
            raise ValidationFailed("Enter the expiry date as YYYY-MM-DD.")

    existing = (admin.table("kyc_documents").select("id, status")
                .eq("profile_id", user.id).eq("doc_type", doc_type)
                .limit(1).execute()).data or []
    payload = {
        "profile_id": user.id,
        "doc_type": doc_type,
        # ONLY the mask is stored. The raw value dies with this request.
        "doc_number_masked": masked,
        "format_valid": True,
        "status": outcome.status,
        "provider": outcome.provider,
        "reference": outcome.reference,
        "verified_at": (datetime.now(timezone.utc).isoformat()
                        if outcome.status == vs.STATUS_VERIFIED else None),
        "expires_at": expires_at,
        "rejected_reason": (outcome.message
                            if outcome.status == vs.STATUS_REJECTED else None),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if existing:
        admin.table("kyc_documents").update(payload).eq("id", existing[0]["id"]).execute()
        event, from_status = "resubmitted", existing[0]["status"]
    else:
        admin.table("kyc_documents").insert(payload).execute()
        event, from_status = "submitted", None

    _audit(admin, user.id, doc_type, event, from_status=from_status,
           to_status=outcome.status, provider=outcome.provider,
           note=outcome.message)

    rows = (admin.table("kyc_documents").select("*")
            .eq("profile_id", user.id).execute()).data or []
    creds = [_public_row(r) for r in rows]
    _sync_account_status(admin, user.id, creds)

    return {
        "credential": next(c for c in creds if c["doc_type"] == doc_type),
        "message": outcome.message,
        "progress": vs.progress(role, creds),
    }


@router.delete("/{doc_type}")
async def withdraw_credential(doc_type: str, user: CurrentUserDep):
    """Remove a credential the caller submitted. Data minimisation, on request."""
    doc_type = doc_type.strip().lower()
    if doc_type not in vs.ALL_TYPES:
        raise NotFound("That credential is not on file.")

    admin = _admin()
    existing = (admin.table("kyc_documents").select("id, status")
                .eq("profile_id", user.id).eq("doc_type", doc_type)
                .limit(1).execute()).data or []
    if not existing:
        raise NotFound("That credential is not on file.")

    admin.table("kyc_documents").delete().eq("id", existing[0]["id"]).execute()
    _audit(admin, user.id, doc_type, "withdrawn",
           from_status=existing[0]["status"], note="withdrawn by holder")

    rows = (admin.table("kyc_documents").select("*")
            .eq("profile_id", user.id).execute()).data or []
    creds = [_public_row(r) for r in rows]
    _sync_account_status(admin, user.id, creds)
    role = (user.role or "").lower()
    return {"ok": True, "progress": vs.progress(role, creds)}


@router.get("/trust/{profile_id}")
async def public_trust(profile_id: str, user: CurrentUserDep):
    """What OTHER users may see about someone's credentials.

    Statuses only -- no masked values, no dates, no provider, no reasons. A
    counterparty needs to know whether a licence was verified, never what its
    number is, and even the mask is the holder's business alone.
    """
    admin = _admin()
    prof = (admin.table("profiles").select("id, role, full_name, verification_status")
            .eq("id", profile_id).limit(1).execute()).data or []
    if not prof:
        raise NotFound("That profile does not exist.")
    profile = prof[0]

    rows = (admin.table("kyc_documents").select("doc_type, status, expires_at")
            .eq("profile_id", profile_id).execute()).data or []

    verified: list[str] = []
    for r in rows:
        status = r["status"]
        if vs.grade_expiry(r.get("expires_at")) == "expired":
            continue                      # an expired credential is not a badge
        if status == vs.STATUS_VERIFIED:
            verified.append(r["doc_type"])

    return {
        "profile_id": profile["id"],
        "role": profile["role"],
        "identity_verified": any(t in vs.IDENTITY_TYPES for t in verified),
        # Role credentials, named but not valued.
        "verified_credentials": [t for t in verified if t not in vs.IDENTITY_TYPES],
        "verified_count": len(verified),
    }
