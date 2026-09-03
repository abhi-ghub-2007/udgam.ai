"""transport.py — transport capacity, shipments, route optimisation (API_CONTRACT §7).

Covers F-7 (find transport), T-5/T-6 (empty leg / scheduled route),
T-7 (consolidation), and the route optimisation display.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import CurrentUserDep, require_role
from ..errors import NotFound, ValidationFailed, Forbidden
from ..services.route_optimizer import optimize_route
from ..services.state_machine import record_transition

router = APIRouter(prefix="/api", tags=["transport"])

require_transporter = Depends(require_role("transporter"))

_CAP_SELECT = ("id, transporter_id, capacity_type, origin_district, dest_district, "
               "depart_at, total_capacity_kg, available_capacity_kg, "
               "price_paise_per_kg, price_paise_per_km, discount_pct, "
               "status, notes, created_at")


# ---------------------------------------------------------------- schemas
class CapacityIn(BaseModel):
    capacity_type: str = Field(pattern="^(scheduled_route|empty_leg|on_demand)$")
    origin_district: str | None = None
    dest_district: str | None = None
    depart_at: str | None = None
    total_capacity_kg: float = Field(gt=0)
    price_paise_per_kg: int = Field(default=0, ge=0)
    price_paise_per_km: int = Field(default=0, ge=0)
    discount_pct: float = Field(default=0, ge=0, le=100)
    notes: str | None = None


class ShipmentUpdateIn(BaseModel):
    status: str = Field(pattern="^(assigned|picked_up|in_transit|delivered|cancelled)$")
    note: str | None = None


# ---------------------------------------------------------------- transport capacity
@router.post("/transport/capacity", status_code=201, dependencies=[require_transporter])
async def create_capacity(body: CapacityIn, user: CurrentUserDep):
    row = {
        "transporter_id": user.id,
        "capacity_type": body.capacity_type,
        "origin_district": body.origin_district,
        "dest_district": body.dest_district,
        "depart_at": body.depart_at,
        "total_capacity_kg": body.total_capacity_kg,
        "available_capacity_kg": body.total_capacity_kg,
        "price_paise_per_kg": body.price_paise_per_kg,
        "price_paise_per_km": body.price_paise_per_km,
        "discount_pct": body.discount_pct,
        "status": "open",
        "notes": body.notes,
    }
    res = user.db.table("transport_capacity").insert(row).execute()
    if not res.data:
        raise ValidationFailed("Could not create transport listing.")
    return res.data[0]


@router.get("/transport/capacity")
async def list_capacity(
    user: CurrentUserDep,
    origin: str | None = None,
    dest: str | None = None,
    capacity_type: str | None = None,
    min_capacity: float | None = None,
):
    """Browse available transport capacity."""
    q = user.db.table("transport_capacity").select(
        _CAP_SELECT + ", profiles!transport_capacity_transporter_id_fkey(full_name,district,avg_rating)"
    ).in_("status", ["open", "partially_booked"])

    if origin:
        q = q.eq("origin_district", origin)
    if dest:
        q = q.eq("dest_district", dest)
    if capacity_type:
        q = q.eq("capacity_type", capacity_type)
    if min_capacity:
        q = q.gte("available_capacity_kg", min_capacity)

    res = q.order("created_at", desc=True).limit(50).execute()
    items = []
    for r in res.data:
        prof = r.pop("profiles", None) or {}
        r["transporter_name"] = prof.get("full_name")
        r["transporter_district"] = prof.get("district")
        r["transporter_rating"] = prof.get("avg_rating")
        items.append(r)
    return {"capacity": items}


@router.get("/transport/capacity/mine", dependencies=[require_transporter])
async def my_capacity(user: CurrentUserDep):
    res = (
        user.db.table("transport_capacity").select(_CAP_SELECT)
        .eq("transporter_id", user.id)
        .order("created_at", desc=True).execute()
    )
    return {"capacity": res.data}


# ---------------------------------------------------------------- shipments
@router.get("/shipments")
async def list_shipments(user: CurrentUserDep, status: str | None = None):
    """Shipments visible to the caller (transporter or order participant)."""
    q = user.db.table("shipments").select(
        "*, orders(order_no, status, buyer_id, farmer_id)"
    )
    if status:
        q = q.eq("status", status)
    res = q.order("created_at", desc=True).limit(50).execute()

    items = []
    for s in res.data:
        order = s.pop("orders", None) or {}
        s["order_no"] = order.get("order_no")
        s["order_status"] = order.get("status")
        items.append(s)
    return {"shipments": items}


@router.post("/orders/{order_id}/assign-transport")
async def assign_transport(order_id: str, user: CurrentUserDep,
                            transporter_id: str,
                            capacity_id: str | None = None):
    """Assign a transporter to an order, transitioning to LOGISTICS_ASSIGNED."""
    # RLS ensures only participants can see the order
    order = user.db.table("orders").select("id,status,logistics_arranged_by") \
        .eq("id", order_id).limit(1).execute()
    if not order.data:
        raise NotFound("Order not found.")
    o = order.data[0]

    # Validate state transition
    from ..services.state_machine import validate_transition
    validate_transition(o["status"], "LOGISTICS_ASSIGNED", user.role)
    
    # Ensure the caller is the one supposed to arrange logistics
    if user.role != o["logistics_arranged_by"]:
        raise Forbidden(f"Logistics must be arranged by the {o['logistics_arranged_by']}.")

    # Create shipment
    shipment = {
        "order_id": order_id,
        "transporter_id": transporter_id,
        "capacity_id": capacity_id,
        "status": "assigned",
    }
    user.db.table("shipments").insert(shipment).execute()

    # Transition order
    user.db.table("orders").update({"status": "LOGISTICS_ASSIGNED"}).eq("id", order_id).execute()
    record_transition(user.db, order_id, o["status"], "LOGISTICS_ASSIGNED",
                      user.id, user.role, f"Transport assigned to {transporter_id}.")

    return {"ok": True}


@router.post("/shipments/{shipment_id}/status", dependencies=[require_transporter])
async def update_shipment_status(shipment_id: str, body: ShipmentUpdateIn,
                                  user: CurrentUserDep):
    """Transporter updates shipment status, which propagates to order status."""
    ship = user.db.table("shipments").select("*") \
        .eq("id", shipment_id).eq("transporter_id", user.id).limit(1).execute()
    if not ship.data:
        raise NotFound("Shipment not found or not yours.")
    s = ship.data[0]

    now = datetime.now(timezone.utc).isoformat()
    patch: dict = {"status": body.status}
    if body.status == "picked_up":
        patch["picked_up_at"] = now
    elif body.status == "delivered":
        patch["delivered_at"] = now

    user.db.table("shipments").update(patch).eq("id", shipment_id).execute()

    # Map shipment status → order status
    ORDER_MAP = {
        "picked_up": "PICKED_UP",
        "in_transit": "IN_TRANSIT",
        "delivered": "DELIVERED",
    }
    if body.status in ORDER_MAP:
        order_status = ORDER_MAP[body.status]
        order = user.db.table("orders").select("id,status").eq("id", s["order_id"]).limit(1).execute()
        if order.data:
            from_st = order.data[0]["status"]
            # Validate state machine before updating
            from ..services.state_machine import validate_transition
            validate_transition(from_st, order_status, "transporter")
            user.db.table("orders").update({"status": order_status}).eq("id", s["order_id"]).execute()
            record_transition(user.db, s["order_id"], from_st, order_status,
                              user.id, "transporter", body.note)

    return {"ok": True, "status": body.status}


# ---------------------------------------------------------------- route optimization
@router.get("/transport/optimize", dependencies=[require_transporter])
async def get_optimized_route(user: CurrentUserDep):
    """Optimize the transporter's current active deliveries into a route."""
    shipments = (
        user.db.table("shipments").select(
            "id, order_id, pickup_location_id, drop_location_id, "
            "orders(order_no, farmer_id, buyer_id)"
        )
        .eq("transporter_id", user.id)
        .in_("status", ["assigned", "picked_up", "in_transit"])
        .execute()
    ).data

    if not shipments:
        return optimize_route([])  # Will return synthetic demo

    # Build stops from order participants' locations
    stops = []
    seen = set()
    for s in shipments:
        order = s.get("orders") or {}
        for pid in [order.get("farmer_id"), order.get("buyer_id")]:
            if pid and pid not in seen:
                seen.add(pid)
                prof = user.db.table("profiles").select("lat,lon,district,full_name") \
                    .eq("id", pid).limit(1).execute()
                if prof.data and prof.data[0].get("lat"):
                    p = prof.data[0]
                    stops.append({
                        "lat": p["lat"], "lon": p["lon"],
                        "label": p.get("full_name", ""),
                        "district": p.get("district", ""),
                        "type": "pickup" if pid == order.get("farmer_id") else "drop",
                    })

    result = optimize_route(stops)
    return {
        "naive_distance_km": result.naive_distance_km,
        "optimized_distance_km": result.optimized_distance_km,
        "distance_saved_pct": result.distance_saved_pct,
        "naive_duration_min": result.naive_duration_min,
        "optimized_duration_min": result.optimized_duration_min,
        "method": result.method,
        "solver": result.solver,
        "stops": result.stops,
    }


# ---------------------------------------------------------------- earnings
@router.get("/transport/earnings", dependencies=[require_transporter])
async def get_earnings(user: CurrentUserDep):
    """Transporter's earnings summary + history."""
    shipments = (
        user.db.table("shipments").select(
            "id, order_id, earnings_paise, planned_distance_km, "
            "actual_distance_km, delivered_at, status, "
            "orders(order_no)"
        )
        .eq("transporter_id", user.id)
        .order("created_at", desc=True)
        .execute()
    ).data

    total = sum(s.get("earnings_paise", 0) for s in shipments)
    completed = [s for s in shipments if s["status"] == "delivered"]
    total_distance = sum(float(s.get("actual_distance_km") or s.get("planned_distance_km") or 0) for s in completed)

    # This month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = sum(
        s.get("earnings_paise", 0) for s in completed
        if s.get("delivered_at") and s["delivered_at"] >= month_start.isoformat()
    )

    history = []
    for s in shipments:
        order = s.pop("orders", None) or {}
        history.append({
            "shipment_id": s["id"],
            "order_no": order.get("order_no"),
            "distance_km": float(s.get("actual_distance_km") or s.get("planned_distance_km") or 0),
            "earnings_paise": s.get("earnings_paise", 0),
            "delivered_at": s.get("delivered_at"),
            "status": s["status"],
        })

    return {
        "total_earnings_paise": total,
        "this_month_paise": this_month,
        "total_distance_km": round(total_distance, 1),
        "avg_per_km_paise": round(total / total_distance) if total_distance > 0 else 0,
        "completed_deliveries": len(completed),
        "history": history,
    }
