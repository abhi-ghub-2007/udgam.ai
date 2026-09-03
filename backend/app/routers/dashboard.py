"""dashboard.py — role landing summaries (API_CONTRACT: /dashboard/*).

Phase 2 fills the marketplace numbers (listings, requests) with live counts.
Order/earnings fields stay 0 until Phase 4 lands them, and say so honestly by
simply being zero rather than faked.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import CurrentUserDep, require_role

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

require_farmer = Depends(require_role("farmer"))
require_buyer = Depends(require_role("buyer"))
require_transporter = Depends(require_role("transporter"))

_PROD = "*, crops(code,name_en,name_hi,name_mr)"
_REQ = "*, crops(code,name_en,name_hi,name_mr)"


def _flatten(row: dict) -> dict:
    crop = row.pop("crops", None) or {}
    row["crop_name"] = crop.get("name_en")
    row["crop_name_hi"] = crop.get("name_hi")
    row["crop_name_mr"] = crop.get("name_mr")
    return row


@router.get("/farmer", dependencies=[require_farmer])
async def farmer_dashboard(user: CurrentUserDep):
    listings = (
        user.db.table("products").select(_PROD)
        .eq("farmer_id", user.id).in_("status", ["active", "reserved"])
        .order("created_at", desc=True).execute()
    ).data
    crop_ids = list({p["crop_id"] for p in listings})

    open_requests = []
    if crop_ids:
        open_requests = (
            user.db.table("buyer_requests").select(_REQ)
            .in_("crop_id", crop_ids).eq("status", "open")
            .order("created_at", desc=True).limit(10).execute()
        ).data

    return {
        "active_listings": len(listings),
        "active_orders": 0,
        "earnings_month_paise": 0,
        "listings": [_flatten(dict(p)) for p in listings[:10]],
        "open_requests": [_flatten(dict(r)) for r in open_requests],
    }


@router.get("/buyer", dependencies=[require_buyer])
async def buyer_dashboard(user: CurrentUserDep):
    reqs = (
        user.db.table("buyer_requests").select("id,status,crop_id")
        .eq("buyer_id", user.id).execute()
    ).data
    open_count = sum(1 for r in reqs if r["status"] == "open")

    # Active orders
    orders = (
        user.db.table("orders").select("id, status, subtotal_paise, buyer_total_paise")
        .eq("buyer_id", user.id)
        .not_.in_("status", ["CLOSED", "CANCELLED"]).execute()
    ).data
    active_orders = len(orders)
    total_purchase_paise = sum(o.get("buyer_total_paise", 0) for o in orders)

    # All-time purchases (including closed)
    all_orders = (
        user.db.table("orders").select("buyer_total_paise")
        .eq("buyer_id", user.id).execute()
    ).data
    lifetime_paise = sum(o.get("buyer_total_paise", 0) for o in all_orders)

    # Recommended produce: match against open requests
    recommended = []
    open_reqs = [r for r in reqs if r["status"] == "open"]
    if open_reqs:
        crop_ids = list({r["crop_id"] for r in open_reqs})
        prods = (
            user.db.table("products").select(_PROD)
            .in_("crop_id", crop_ids).eq("status", "active")
            .order("created_at", desc=True).limit(10).execute()
        ).data
        recommended = [_flatten(dict(p)) for p in prods]

    # My recent requests
    my_reqs = (
        user.db.table("buyer_requests").select(_REQ)
        .eq("buyer_id", user.id)
        .order("created_at", desc=True).limit(5).execute()
    ).data

    return {
        "active_orders": active_orders,
        "open_requests": open_count,
        "saved_farmers": 0,
        "total_purchase_paise": lifetime_paise,
        "recommended": recommended,
        "requests": [_flatten(dict(r)) for r in my_reqs],
    }


@router.get("/transporter", dependencies=[require_transporter])
async def transporter_dashboard(user: CurrentUserDep):
    # Active shipments
    shipments = (
        user.db.table("shipments").select(
            "id, order_id, status, earnings_paise, planned_distance_km, "
            "delivered_at, eta_at, "
            "orders(order_no, status, farmer_id, buyer_id)"
        )
        .eq("transporter_id", user.id)
        .order("created_at", desc=True).execute()
    ).data

    active = [s for s in shipments if s["status"] in ("assigned", "picked_up", "in_transit")]
    completed = [s for s in shipments if s["status"] == "delivered"]
    total_earnings = sum(s.get("earnings_paise", 0) for s in completed)

    # This month earnings
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_earnings = sum(
        s.get("earnings_paise", 0) for s in completed
        if s.get("delivered_at") and s["delivered_at"] >= month_start.isoformat()
    )

    # Pending consolidation requests
    pending = (
        user.db.table("consolidation_requests").select("id")
        .eq("status", "pending")
        .execute()
    ).data

    # Available transport jobs (orders needing transport)
    available_jobs = (
        user.db.table("orders").select(
            "id, order_no, status, farmer_id, buyer_id, "
            "subtotal_paise, logistics_arranged_by, needed_by"
        )
        .eq("status", "PAYMENT_HELD")
        .order("created_at", desc=True).limit(10).execute()
    ).data

    # Enrich active shipments with location info
    upcoming = []
    for s in active[:5]:
        order = s.pop("orders", None) or {}
        upcoming.append({
            "id": s["id"],
            "order_no": order.get("order_no"),
            "order_status": order.get("status"),
            "status": s["status"],
            "eta_at": s.get("eta_at"),
            "planned_distance_km": s.get("planned_distance_km"),
            "earnings_paise": s.get("earnings_paise", 0),
        })

    return {
        "active_jobs": len(active),
        "earnings_month_paise": month_earnings,
        "total_earnings_paise": total_earnings,
        "pending_consolidation": len(pending),
        "completed_deliveries": len(completed),
        "upcoming_pickups": upcoming,
        "available_jobs": available_jobs,
    }

