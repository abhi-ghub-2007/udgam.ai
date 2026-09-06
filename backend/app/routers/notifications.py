"""notifications.py — notification CRUD (API_CONTRACT §10).

Notifications are stored with i18n keys and rendered client-side.
RLS scopes them to user_id = auth.uid().
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from ..deps import CurrentUserDep
from ..errors import NotFound

router = APIRouter(prefix="/api", tags=["notifications"])

log = logging.getLogger("udgam.notifications")


@router.get("/notifications")
async def list_notifications(user: CurrentUserDep, unread_only: bool = False):
    q = user.db.table("notifications").select("*").eq("user_id", user.id)
    if unread_only:
        q = q.is_("read_at", "null")
    res = q.order("created_at", desc=True).limit(50).execute()
    unread = sum(1 for n in res.data if not n.get("read_at"))
    return {"items": res.data, "unread_count": unread}


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, user: CurrentUserDep):
    from datetime import datetime, timezone
    res = (
        user.db.table("notifications")
        .update({"read_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", notification_id).eq("user_id", user.id).execute()
    )
    if not res.data:
        raise NotFound("Notification not found.")
    return {"ok": True}


@router.post("/notifications/read-all")
async def mark_all_read(user: CurrentUserDep):
    from datetime import datetime, timezone
    user.db.table("notifications") \
        .update({"read_at": datetime.now(timezone.utc).isoformat()}) \
        .eq("user_id", user.id).is_("read_at", "null").execute()
    return {"ok": True}


def create_notification(db, user_id: str, type_: str, title_key: str,
                         body_key: str, params: dict | None = None,
                         entity_type: str | None = None,
                         entity_id: str | None = None) -> None:
    """Helper to insert a notification. Called by order/transport routers."""
    db.table("notifications").insert({
        "user_id": user_id,
        "type": type_,
        "title_key": title_key,
        "body_key": body_key,
        "params": params or {},
        "entity_type": entity_type,
        "entity_id": entity_id,
    }).execute()


def notify(user_id: str, type_: str, title_key: str, body_key: str,
           params: dict | None = None, entity_type: str | None = None,
           entity_id: str | None = None) -> None:
    """Tell somebody ELSE that something happened to them.

    Service-role on purpose, and this is the only place it is used for
    notifications. `notifications` deliberately has no INSERT policy at all
    (db/SCHEMA.sql section 13 grants only select/update on user_id =
    auth.uid()), because a notification is a statement the system makes about
    a user, not something a user writes -- if any authenticated caller could
    insert, anyone could forge "your order was cancelled" into a stranger's
    inbox. With RLS default-deny, that means a JWT-scoped client cannot write
    one even for a legitimate counterparty, so the fan-out runs as the service
    role (A-12) after the router has already authorised the action that caused
    it.

    Never raises: a failed notification must not roll back the accept, decline
    or delivery that actually happened.
    """
    from ..db.admin_client import admin_client

    try:
        create_notification(admin_client(), user_id, type_, title_key,
                            body_key, params, entity_type, entity_id)
    except Exception:  # noqa: BLE001 - delivery is best-effort by design
        log.warning("notification %s for %s could not be stored", type_, user_id,
                    exc_info=True)
