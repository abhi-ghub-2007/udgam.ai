"""orders.py — order CRUD + state machine (API_CONTRACT §6).

The order lifecycle (PRD §8) flows through the state machine in
services/state_machine.py. Every transition is recorded in
order_status_history. RLS scopes visibility to participants.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import CurrentUserDep, require_role
from ..errors import NotFound, ValidationFailed, Forbidden
from ..services.state_machine import validate_transition, record_transition
from ..services.pricing import compute_breakdown

router = APIRouter(prefix="/api", tags=["orders"])

require_buyer = Depends(require_role("buyer"))
require_farmer = Depends(require_role("farmer"))

_ORDER_SELECT = "*, order_items(*, crops(code,name_en,name_hi,name_mr))"


def _order_no() -> str:
    """UDG-XXXXXXXX order number."""
    return f"UDG-{secrets.token_hex(4).upper()}"


def _flatten_order(row: dict) -> dict:
    items = row.pop("order_items", []) or []
    for it in items:
        crop = it.pop("crops", None) or {}
        it["crop_name"] = crop.get("name_en")
        it["crop_name_hi"] = crop.get("name_hi")
        it["crop_name_mr"] = crop.get("name_mr")
    row["items"] = items
    return row


# ---------------------------------------------------------------- schemas
class OrderCreateIn(BaseModel):
    product_id: str
    farmer_id: str
    quantity_kg: float = Field(gt=0)
    logistics_arranged_by: str = Field(default="farmer", pattern="^(farmer|buyer)$")
    delivery_pincode: str | None = None
    needed_by: str | None = None  # ISO date
    notes: str | None = None


class OrderTransitionIn(BaseModel):
    to_status: str
    note: str | None = None


class DeliveryConfirmIn(BaseModel):
    otp: str = Field(min_length=4, max_length=6)


# ---------------------------------------------------------------- create
@router.post("/orders", status_code=201, dependencies=[require_buyer])
async def create_order(body: OrderCreateIn, user: CurrentUserDep):
    """Create an order from a product listing."""
    # Verify the product exists and has enough quantity
    prod = (
        user.db.table("products").select("*, crops(code,name_en)")
        .eq("id", body.product_id).eq("status", "active").limit(1).execute()
    )
    if not prod.data:
        raise NotFound("Listing not found or no longer available.")
    p = prod.data[0]

    if body.quantity_kg > float(p.get("available_quantity_kg", 0)):
        raise ValidationFailed(
            f"Only {p['available_quantity_kg']} kg available.",
            field="quantity_kg",
        )

    if body.farmer_id != p["farmer_id"]:
        raise ValidationFailed("Farmer does not own this listing.", field="farmer_id")

    # Compute pricing
    breakdown = compute_breakdown(
        quantity_kg=body.quantity_kg,
        unit_price_paise=p["asking_price_paise"],
    )

    order_no = _order_no()
    order_row = {
        "order_no": order_no,
        "buyer_id": user.id,
        "farmer_id": body.farmer_id,
        "status": "PLACED",
        "logistics_arranged_by": body.logistics_arranged_by,
        "subtotal_paise": breakdown.subtotal_paise,
        "platform_fee_paise": breakdown.platform_fee_paise,
        "buyer_total_paise": breakdown.buyer_total_paise,
        "farmer_payout_paise": breakdown.farmer_payout_paise,
        "delivery_pincode": body.delivery_pincode,
        "needed_by": body.needed_by,
        "placed_at": datetime.now(timezone.utc).isoformat(),
    }
    res = user.db.table("orders").insert(order_row).execute()
    if not res.data:
        raise ValidationFailed("Could not create the order.")
    order_id = res.data[0]["id"]

    # Create order item
    crop = p.get("crops") or {}
    user.db.table("order_items").insert({
        "order_id": order_id,
        "product_id": body.product_id,
        "farmer_id": body.farmer_id,
        "crop_id": p["crop_id"],
        "quantity_kg": body.quantity_kg,
        "unit_price_paise": p["asking_price_paise"],
        "line_total_paise": breakdown.subtotal_paise,
        "grade": p.get("grade"),
    }).execute()

    # Record initial transition
    record_transition(
        user.db, order_id, None, "PLACED",
        user.id, "buyer", body.notes,
    )

    # Reserve the quantity on the product
    new_avail = float(p["available_quantity_kg"]) - body.quantity_kg
    patch = {"available_quantity_kg": max(new_avail, 0)}
    if new_avail <= 0:
        patch["status"] = "reserved"
    user.db.table("products").update(patch).eq("id", body.product_id).execute()

    return await get_order(order_id, user)


# ---------------------------------------------------------------- read
@router.get("/orders")
async def list_orders(user: CurrentUserDep, status: str | None = None):
    """All orders the caller is a participant in."""
    q = user.db.table("orders").select("id, order_no, buyer_id, farmer_id, status, "
                                        "subtotal_paise, buyer_total_paise, farmer_payout_paise, "
                                        "transport_cost_paise, platform_fee_paise, "
                                        "logistics_arranged_by, needed_by, placed_at, "
                                        "accepted_at, delivered_at, closed_at, created_at")
    if status:
        q = q.eq("status", status)
    res = q.order("created_at", desc=True).limit(100).execute()

    # Enrich with item summary
    orders = []
    for o in res.data:
        items = (
            user.db.table("order_items")
            .select("crop_id, quantity_kg, unit_price_paise, grade, crops(name_en,name_hi,name_mr)")
            .eq("order_id", o["id"]).execute()
        ).data
        for it in items:
            crop = it.pop("crops", None) or {}
            it["crop_name"] = crop.get("name_en")
        o["items"] = items

        # Get counterparty name
        other_id = o["farmer_id"] if user.role == "buyer" else o["buyer_id"]
        if other_id:
            prof = user.db.table("profiles").select("full_name,district").eq("id", other_id).limit(1).execute()
            o["counterparty"] = prof.data[0] if prof.data else {}
        else:
            o["counterparty"] = {}
        orders.append(o)

    return {"orders": orders}


@router.get("/orders/{order_id}")
async def get_order(order_id: str, user: CurrentUserDep):
    """Full order detail with items, timeline, shipment."""
    res = (
        user.db.table("orders").select("*")
        .eq("id", order_id).limit(1).execute()
    )
    if not res.data:
        raise NotFound("Order not found.")
    order = res.data[0]

    items = (
        user.db.table("order_items")
        .select("*, crops(code,name_en,name_hi,name_mr)")
        .eq("order_id", order_id).execute()
    ).data
    for it in items:
        crop = it.pop("crops", None) or {}
        it["crop_name"] = crop.get("name_en")
        it["crop_name_hi"] = crop.get("name_hi")

    timeline = (
        user.db.table("order_status_history")
        .select("*").eq("order_id", order_id)
        .order("created_at").execute()
    ).data

    shipment = (
        user.db.table("shipments").select("*")
        .eq("order_id", order_id).limit(1).execute()
    ).data

    # Farmer + buyer profiles — phone only exposed when order is at/past ACCEPTED
    from ..services.masking import mask_phone, CONTACT_VISIBLE_STATUSES
    contact_visible = order.get("status") in CONTACT_VISIBLE_STATUSES
    farmer = buyer = {}
    if order.get("farmer_id"):
        f = user.db.table("profiles").select(
            "id,full_name,district,state,phone,avg_rating,rating_count"
        ).eq("id", order["farmer_id"]).limit(1).execute()
        farmer = f.data[0] if f.data else {}
        if farmer and not contact_visible and farmer.get("id") != user.id:
            farmer["phone"] = mask_phone(farmer.get("phone"))
    if order.get("buyer_id"):
        b = user.db.table("profiles").select(
            "id,full_name,district,state,phone,avg_rating,rating_count"
        ).eq("id", order["buyer_id"]).limit(1).execute()
        buyer = b.data[0] if b.data else {}
        if buyer and not contact_visible and buyer.get("id") != user.id:
            buyer["phone"] = mask_phone(buyer.get("phone"))

    # Payment info
    payment = (
        user.db.table("payments").select("*")
        .eq("order_id", order_id).order("created_at", desc=True).limit(1).execute()
    ).data

    return {
        "order": order,
        "items": items,
        "timeline": timeline,
        "shipment": shipment[0] if shipment else None,
        "farmer": farmer,
        "buyer": buyer,
        "payment": payment[0] if payment else None,
    }


# ---------------------------------------------------------------- transitions
@router.post("/orders/{order_id}/transition")
async def transition_order(order_id: str, body: OrderTransitionIn, user: CurrentUserDep):
    """Advance the order through the state machine."""
    res = user.db.table("orders").select("id,status").eq("id", order_id).limit(1).execute()
    if not res.data:
        raise NotFound("Order not found.")
    current = res.data[0]["status"]

    validate_transition(current, body.to_status, user.role)

    patch: dict = {"status": body.to_status}
    now = datetime.now(timezone.utc).isoformat()

    if body.to_status == "ACCEPTED":
        patch["accepted_at"] = now
    elif body.to_status == "DELIVERED":
        patch["delivered_at"] = now
    elif body.to_status == "CLOSED":
        patch["closed_at"] = now
        patch["escrow_status"] = "released"
    elif body.to_status == "CANCELLED":
        patch["cancelled_reason"] = body.note

    user.db.table("orders").update(patch).eq("id", order_id).execute()
    record_transition(user.db, order_id, current, body.to_status,
                      user.id, user.role, body.note)

    return await get_order(order_id, user)


# ---------------------------------------------------------------- payment mock
@router.post("/orders/{order_id}/pay", dependencies=[require_buyer])
async def mock_payment(order_id: str, user: CurrentUserDep):
    """Mock payment — creates a payment record and transitions to PAYMENT_HELD."""
    order = user.db.table("orders").select("id,status,buyer_total_paise,buyer_id") \
        .eq("id", order_id).limit(1).execute()
    if not order.data:
        raise NotFound("Order not found.")
    o = order.data[0]
    if o["buyer_id"] != user.id:
        raise Forbidden("Not your order.")
    if o["status"] != "ACCEPTED":
        raise ValidationFailed("Order must be in ACCEPTED state to pay.")

    # Create payment record
    user.db.table("payments").insert({
        "order_id": order_id,
        "buyer_id": user.id,
        "provider": "mock",
        "amount_paise": o["buyer_total_paise"],
        "status": "held",
        "held_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    # Transition
    user.db.table("orders").update({
        "status": "PAYMENT_HELD",
        "escrow_status": "held",
    }).eq("id", order_id).execute()
    record_transition(user.db, order_id, "ACCEPTED", "PAYMENT_HELD",
                      user.id, "buyer", "Payment held in escrow (mock).")

    return await get_order(order_id, user)


# ---------------------------------------------------------------- price breakdown
@router.get("/orders/{order_id}/breakdown")
async def order_breakdown(order_id: str, user: CurrentUserDep):
    """Transparent price breakdown for an order."""
    res = user.db.table("orders").select("*").eq("id", order_id).limit(1).execute()
    if not res.data:
        raise NotFound("Order not found.")
    o = res.data[0]
    return {
        "subtotal_paise": o.get("subtotal_paise", 0),
        "transport_cost_paise": o.get("transport_cost_paise", 0),
        "platform_fee_paise": o.get("platform_fee_paise", 0),
        "logistics_facilitation_fee_paise": o.get("logistics_facilitation_fee_paise", 0),
        "buyer_total_paise": o.get("buyer_total_paise", 0),
        "farmer_payout_paise": o.get("farmer_payout_paise", 0),
        "traditional_chain_price_paise": o.get("traditional_chain_price_paise"),
    }
