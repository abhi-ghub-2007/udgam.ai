"""transport.py — transport capacity, shipments, route optimisation (API_CONTRACT §7).

Covers F-7 (find transport), T-5/T-6 (empty leg / scheduled route),
T-7 (consolidation), and the route optimisation display.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import CurrentUserDep, require_role
from ..errors import NotFound, ValidationFailed, Forbidden, Duplicate
from ..services.route_optimizer import haversine, optimize_route
from ..services.state_machine import record_transition, validate_transition
from .notifications import notify

router = APIRouter(prefix="/api", tags=["transport"])

require_transporter = Depends(require_role("transporter"))

log = logging.getLogger("udgam.transport")

# How long a transport offer stays acceptable if nobody answers it. An offer
# that outlives its own pickup window is worse than no offer.
OFFER_TTL_HOURS = 24

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
    # 'delivered' is deliberately NOT settable here: a transporter reaching
    # the destination is not the same fact as the buyer having received the
    # goods. That transition only happens through POST .../confirm-delivery,
    # by the buyer. 'arrived' is reachable two ways -- automatically, from a
    # location update that crosses the geofence (see _maybe_mark_arrived),
    # or manually here, for when GPS was denied/unavailable and the
    # transporter has to say so themselves (§21).
    status: str = Field(pattern="^(picked_up|in_transit|arrived|cancelled)$")
    note: str | None = None


class ShipmentDetailsIn(BaseModel):
    """What a transporter needs before they can sensibly say yes (§5/§6).

    Pickup and drop are entered, never inferred from the farmer's and buyer's
    profile districts: produce may be held at a different store and a buyer may
    take delivery at a warehouse.
    """

    pickup_address: str = Field(min_length=3, max_length=500)
    pickup_contact_name: str | None = Field(default=None, max_length=120)
    pickup_contact_phone: str | None = Field(default=None, max_length=20)
    pickup_from: str | None = None            # ISO datetime — window opens
    pickup_until: str | None = None           # ISO datetime — window closes
    pickup_instructions: str | None = Field(default=None, max_length=500)
    # From Google Places Autocomplete, stored as given -- never re-geocoded.
    pickup_lat: float | None = Field(default=None, ge=-90, le=90)
    pickup_lon: float | None = Field(default=None, ge=-180, le=180)
    pickup_place_id: str | None = Field(default=None, max_length=200)

    drop_address: str = Field(min_length=3, max_length=500)
    drop_contact_name: str | None = Field(default=None, max_length=120)
    drop_contact_phone: str | None = Field(default=None, max_length=20)
    deliver_by: str | None = None             # ISO datetime — deadline
    drop_instructions: str | None = Field(default=None, max_length=500)
    drop_lat: float | None = Field(default=None, ge=-90, le=90)
    drop_lon: float | None = Field(default=None, ge=-180, le=180)
    drop_place_id: str | None = Field(default=None, max_length=200)

    # Who ARRANGES is orders.logistics_arranged_by. Who PAYS is this, and the
    # two are separate decisions (§4B) — a farmer may arrange a lorry the buyer
    # settles for. Defaults to the arranger only because that is the common
    # case, never because they are the same thing.
    transport_paid_by: str | None = Field(default=None, pattern="^(farmer|buyer)$")


class LocationUpdateIn(BaseModel):
    """One reading from the transporter's device (§8/§9)."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    heading: float | None = Field(default=None, ge=0, lt=360)
    speed_kmph: float | None = Field(default=None, ge=0)


# Within this many metres of the drop point, the shipment auto-marks
# 'arrived'. Loose enough for consumer GPS accuracy in the countryside,
# tight enough not to fire from the next village over.
ARRIVAL_GEOFENCE_M = 300
# The frontend already throttles; this is the same guarantee enforced
# server-side; a client cannot be trusted to actually rate-limit itself.
MIN_LOCATION_UPDATE_INTERVAL_S = 4


class OfferCreateIn(BaseModel):
    """Ask specific transport listings to carry this shipment."""

    capacity_ids: list[str] = Field(min_length=1, max_length=10)
    note: str | None = Field(default=None, max_length=500)


class OfferDeclineIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------- helpers
def _order_for_arranger(user, order_id: str) -> dict:
    """Load the order and prove this caller is the one who arranges transport.

    RLS already limits the read to order participants; this adds the business
    rule on top, so a buyer cannot arrange transport on an order whose farmer
    agreed to arrange it.
    """
    res = (
        user.db.table("orders")
        .select("id,status,buyer_id,farmer_id,logistics_arranged_by,needed_by")
        .eq("id", order_id).limit(1).execute()
    )
    if not res.data:
        raise NotFound("Order not found.")
    order = res.data[0]
    if user.role != order["logistics_arranged_by"]:
        raise Forbidden(
            f"Transport for this order is arranged by the {order['logistics_arranged_by']}."
        )
    return order


def _cargo_kg(user, order_id: str) -> float:
    """Weight actually being moved, from the order's own line items."""
    res = user.db.table("order_items").select("quantity_kg").eq("order_id", order_id).execute()
    return float(sum(float(i.get("quantity_kg") or 0) for i in res.data or []))


def _capacity_route_km(cap: dict) -> float | None:
    """Straight-line length of the listing's own route, when it has coordinates.

    Reuses route_optimizer.haversine rather than introducing a second distance
    calculation (§28).
    """
    o_lat, o_lon = cap.get("origin_lat"), cap.get("origin_lon")
    d_lat, d_lon = cap.get("dest_lat"), cap.get("dest_lon")
    if None in (o_lat, o_lon, d_lat, d_lon):
        return None
    return round(haversine(o_lat, o_lon, d_lat, d_lon), 1)


def _estimate_cost_paise(cap: dict, cargo_kg: float) -> int:
    """Estimated haulage cost from the listing's OWN published pricing.

    An estimate, never a settled amount: there is no payment rail for transport,
    so the shipment keeps this apart from `earnings_paise` and the UI labels it
    as an estimate (§7).
    """
    per_kg = int(cap.get("price_paise_per_kg") or 0) * cargo_kg
    km = _capacity_route_km(cap) or 0
    per_km = int(cap.get("price_paise_per_km") or 0) * km
    gross = per_kg + per_km
    discount = float(cap.get("discount_pct") or 0)
    return int(round(gross * (1 - discount / 100)))


def _live_shipment(user, order_id: str) -> dict | None:
    res = (
        user.db.table("shipments").select("*")
        .eq("order_id", order_id).neq("status", "cancelled").limit(1).execute()
    )
    return res.data[0] if res.data else None


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


# ---------------------------------------------------------------- shipment detail
@router.put("/orders/{order_id}/shipment")
async def upsert_shipment_details(order_id: str, body: ShipmentDetailsIn,
                                   user: CurrentUserDep):
    """Record where this order is collected from and delivered to (§5).

    Creates the shipment in `created` — the state the shipment_status enum
    already had for "planned, nobody carrying it yet" — so a transporter can
    read the job before deciding. Editable until somebody is assigned; after
    that the terms are what a transporter agreed to and must not move under
    them.
    """
    order = _order_for_arranger(user, order_id)
    if order["status"] in ("CANCELLED", "CLOSED", "DISPUTED", "DELIVERED"):
        raise ValidationFailed("This order is no longer being transported.")

    pickup_from = body.pickup_from or None
    pickup_until = body.pickup_until or None
    deliver_by = body.deliver_by or None

    # Cheap, explicit sanity checks so the farmer gets a sentence rather than a
    # constraint name. The database enforces the same thing regardless.
    if pickup_from and pickup_until and pickup_until < pickup_from:
        raise ValidationFailed("The pickup window closes before it opens.",
                               field="pickup_until")
    if pickup_from and deliver_by and deliver_by < pickup_from:
        raise ValidationFailed("Delivery is due before pickup begins.",
                               field="deliver_by")
    if pickup_until and pickup_until < datetime.now(timezone.utc).isoformat():
        raise ValidationFailed("That pickup window has already passed.",
                               field="pickup_until")

    cargo = _cargo_kg(user, order_id)
    if cargo <= 0:
        raise ValidationFailed("This order has nothing to transport.")

    patch = {
        "pickup_address": body.pickup_address.strip(),
        "pickup_contact_name": body.pickup_contact_name,
        "pickup_contact_phone": body.pickup_contact_phone,
        "pickup_from": pickup_from,
        "pickup_until": pickup_until,
        "pickup_instructions": body.pickup_instructions,
        "pickup_lat": body.pickup_lat,
        "pickup_lon": body.pickup_lon,
        "pickup_place_id": body.pickup_place_id,
        "drop_address": body.drop_address.strip(),
        "drop_contact_name": body.drop_contact_name,
        "drop_contact_phone": body.drop_contact_phone,
        "deliver_by": deliver_by,
        "drop_instructions": body.drop_instructions,
        "drop_lat": body.drop_lat,
        "drop_lon": body.drop_lon,
        "drop_place_id": body.drop_place_id,
        "cargo_kg": cargo,
        "transport_paid_by": body.transport_paid_by or order["logistics_arranged_by"],
    }

    existing = _live_shipment(user, order_id)
    if existing:
        if existing.get("transporter_id"):
            raise ValidationFailed(
                "A transporter has already accepted these terms; cancel the "
                "shipment before changing them."
            )
        user.db.table("shipments").update(patch).eq("id", existing["id"]).execute()
        shipment_id = existing["id"]
    else:
        patch["order_id"] = order_id
        patch["status"] = "created"
        res = user.db.table("shipments").insert(patch).execute()
        if not res.data:
            raise ValidationFailed("Could not save the transport details.")
        shipment_id = res.data[0]["id"]

    out = user.db.table("shipments").select("*").eq("id", shipment_id).limit(1).execute()
    return {"shipment": out.data[0] if out.data else None}


@router.get("/orders/{order_id}/transport-options")
async def transport_options(order_id: str, user: CurrentUserDep):
    """Transport listings that could actually carry this shipment.

    Filtered on objective fitness only — enough capacity, and a route that
    matches where the goods are going. Ordered by declared neutral factors
    (cost, then distance, then id as a stable tie-break). Reliability travels
    with each option for the human to weigh, but is NOT a ranking input:
    services/orchestration.py lists `transporter_id` among FORBIDDEN_FACTORS
    and does not declare transporter reputation as a ranking factor, so using
    it to order this list would quietly break the neutrality policy (§29).
    """
    order = _order_for_arranger(user, order_id)
    shipment = _live_shipment(user, order_id)
    if not shipment:
        raise ValidationFailed(
            "Add the pickup and delivery details before looking for transport.")

    cargo = float(shipment.get("cargo_kg") or _cargo_kg(user, order_id))

    res = (
        user.db.table("transport_capacity")
        .select("*, profiles!transport_capacity_transporter_id_fkey"
                "(id,full_name,district,avg_rating,rating_count,verification_status)")
        .in_("status", ["open", "partially_booked"])
        .gte("available_capacity_kg", cargo)
        .limit(50).execute()
    )

    # Offers already sent for this shipment, so the UI does not ask twice.
    offered = (
        user.db.table("consolidation_requests")
        .select("capacity_id,status")
        .eq("shipment_id", shipment["id"]).execute()
    ).data or []
    offered_by_capacity = {o["capacity_id"]: o["status"] for o in offered}

    options = []
    for cap in res.data or []:
        prof = cap.pop("profiles", None) or {}
        options.append({
            "capacity_id": cap["id"],
            "transporter_id": cap["transporter_id"],
            "transporter_name": prof.get("full_name"),
            "capacity_type": cap["capacity_type"],
            "origin_district": cap.get("origin_district"),
            "dest_district": cap.get("dest_district"),
            "depart_at": cap.get("depart_at"),
            "available_capacity_kg": float(cap.get("available_capacity_kg") or 0),
            "route_km": _capacity_route_km(cap),
            "estimated_cost_paise": _estimate_cost_paise(cap, cargo),
            "discount_pct": float(cap.get("discount_pct") or 0),
            # Decision support, not ranking input.
            "reliability": {
                "avg_rating": prof.get("avg_rating"),
                "rating_count": prof.get("rating_count") or 0,
                "verification_status": prof.get("verification_status"),
            },
            "offer_status": offered_by_capacity.get(cap["id"]),
        })

    options.sort(key=lambda o: (o["estimated_cost_paise"],
                                 o["route_km"] if o["route_km"] is not None else 1e9,
                                 o["capacity_id"]))

    return {
        "shipment_id": shipment["id"],
        "cargo_kg": cargo,
        "arranged_by": order["logistics_arranged_by"],
        "ranked_by": "estimated_cost_paise asc, then distance_km asc, then reference_id asc",
        "options": options,
        "method": "ALGORITHMIC",
    }


@router.post("/orders/{order_id}/assign-transport")
async def assign_transport(order_id: str, user: CurrentUserDep,
                            capacity_id: str):
    """Ask one specific transport listing to carry this order.

    This used to write `shipments` with a transporter_id straight from the
    query string and move the order to LOGISTICS_ASSIGNED — the named
    transporter was booked without ever being asked, and nothing checked the
    load against their capacity. It now sends an offer they can accept or
    decline, which is the same intent ("I want this one") with consent
    restored. Kept at its old path, and it had no callers, so nothing breaks.
    """
    return await create_offers(order_id, OfferCreateIn(capacity_ids=[capacity_id]), user)


@router.post("/orders/{order_id}/transport-offers", status_code=201)
async def create_offers(order_id: str, body: OfferCreateIn, user: CurrentUserDep):
    """Offer the shipment to one or more transport listings (§11/§12).

    Sending to several at once is what makes a decline survivable: the job does
    not die with the first no.
    """
    order = _order_for_arranger(user, order_id)
    shipment = _live_shipment(user, order_id)
    if not shipment:
        raise ValidationFailed(
            "Add the pickup and delivery details before requesting transport.")
    if shipment.get("transporter_id"):
        raise ValidationFailed("This shipment already has a transporter.")

    cargo = float(shipment.get("cargo_kg") or _cargo_kg(user, order_id))
    expires = (datetime.now(timezone.utc) + timedelta(hours=OFFER_TTL_HOURS)).isoformat()

    created, skipped = [], []
    for capacity_id in dict.fromkeys(body.capacity_ids):  # de-dupe, keep order
        cap = (
            user.db.table("transport_capacity").select("*")
            .eq("id", capacity_id).limit(1).execute()
        ).data
        if not cap:
            skipped.append({"capacity_id": capacity_id, "reason": "not_found"})
            continue
        cap = cap[0]

        # §6: a lorry that cannot hold the load must not be offered it.
        if float(cap.get("available_capacity_kg") or 0) < cargo:
            skipped.append({"capacity_id": capacity_id, "reason": "insufficient_capacity"})
            continue
        if cap.get("status") not in ("open", "partially_booked"):
            skipped.append({"capacity_id": capacity_id, "reason": "unavailable"})
            continue

        row = {
            "capacity_id": capacity_id,
            "requester_id": user.id,
            "requester_role": user.role,
            "order_id": order_id,
            "shipment_id": shipment["id"],
            "quantity_kg": cargo,
            "status": "pending",
            "expires_at": expires,
            "response_note": body.note,
        }
        try:
            res = user.db.table("consolidation_requests").insert(row).execute()
        except Exception as exc:  # noqa: BLE001 - unique index = already offered
            if "uq_consolidation_open_offer" in str(exc):
                skipped.append({"capacity_id": capacity_id, "reason": "already_offered"})
                continue
            raise
        if res.data:
            created.append(res.data[0])
            notify(
                cap["transporter_id"], "transport_offer",
                "notif.transport_offer_title", "notif.transport_offer_body",
                params={"order_no": order.get("order_no") or "", "kg": cargo},
                entity_type="consolidation_request", entity_id=res.data[0]["id"],
            )

    if not created and skipped:
        raise ValidationFailed(
            "None of those transporters can take this load.",
            field="capacity_ids",
        )

    return {"offers": created, "skipped": skipped, "expires_at": expires}


# ---------------------------------------------------------------- transporter inbox
@router.get("/transport/jobs", dependencies=[require_transporter])
async def list_transport_jobs(user: CurrentUserDep):
    """Offers waiting on this transporter, with everything needed to decide (§11).

    RLS on consolidation_requests already limits this to offers addressed to
    the caller's own listings; the filters here are about usefulness, not
    security.
    """
    now = datetime.now(timezone.utc).isoformat()
    res = (
        user.db.table("consolidation_requests")
        .select("*, shipments(*), orders(order_no,status,needed_by), "
                "transport_capacity(id,total_capacity_kg,available_capacity_kg,"
                "price_paise_per_kg,price_paise_per_km,discount_pct,"
                "origin_district,dest_district,origin_lat,origin_lon,dest_lat,dest_lon)")
        .eq("status", "pending")
        .order("created_at", desc=True).limit(50).execute()
    )

    jobs = []
    for r in res.data or []:
        shipment = r.pop("shipments", None) or {}
        order = r.pop("orders", None) or {}
        cap = r.pop("transport_capacity", None) or {}
        # An expired offer is not a job; it stays in the table as history.
        if r.get("expires_at") and r["expires_at"] < now:
            continue
        # Somebody else already won it. Hidden rather than deleted, so the
        # accept endpoint stays the single authority on who got the job.
        if shipment.get("transporter_id"):
            continue
        cargo = float(r.get("quantity_kg") or shipment.get("cargo_kg") or 0)
        jobs.append({
            "offer_id": r["id"],
            "order_id": r.get("order_id"),
            "order_no": order.get("order_no"),
            "shipment_id": r.get("shipment_id"),
            "expires_at": r.get("expires_at"),
            "note": r.get("response_note"),
            "cargo_kg": cargo,
            "capacity_id": cap.get("id"),
            "available_capacity_kg": float(cap.get("available_capacity_kg") or 0),
            "fits": float(cap.get("available_capacity_kg") or 0) >= cargo,
            "estimated_cost_paise": _estimate_cost_paise(cap, cargo) if cap else None,
            "route_km": _capacity_route_km(cap) if cap else None,
            "pickup": {
                "address": shipment.get("pickup_address"),
                "contact_name": shipment.get("pickup_contact_name"),
                "contact_phone": shipment.get("pickup_contact_phone"),
                "from": shipment.get("pickup_from"),
                "until": shipment.get("pickup_until"),
                "instructions": shipment.get("pickup_instructions"),
            },
            "drop": {
                "address": shipment.get("drop_address"),
                "contact_name": shipment.get("drop_contact_name"),
                "contact_phone": shipment.get("drop_contact_phone"),
                "deliver_by": shipment.get("deliver_by"),
                "instructions": shipment.get("drop_instructions"),
            },
            "transport_paid_by": shipment.get("transport_paid_by"),
        })
    return {"jobs": jobs}


@router.post("/transport/offers/{offer_id}/accept", dependencies=[require_transporter])
async def accept_offer(offer_id: str, user: CurrentUserDep):
    """Take the job (§11), and be the only one who does (§13).

    Two transporters can press this at the same moment. Neither the status
    check below nor a disabled button can stop that — between reading `pending`
    and writing the shipment there is a window. The unique partial index
    uq_shipment_live_per_order (one live shipment per order) is what actually
    decides it: the loser's UPDATE cannot make a second live shipment, and gets
    told the job is gone rather than a 500. Pressing accept twice is safe for
    the same reason plus the status check — the second press is a no-op.
    """
    offer = (
        user.db.table("consolidation_requests")
        .select("*, transport_capacity(id,transporter_id,available_capacity_kg,status,"
                "price_paise_per_kg,price_paise_per_km,discount_pct,"
                "origin_lat,origin_lon,dest_lat,dest_lon)")
        .eq("id", offer_id).limit(1).execute()
    ).data
    if not offer:
        raise NotFound("That transport request is not available.")
    offer = offer[0]
    cap = offer.pop("transport_capacity", None) or {}

    # RLS already blocks updating someone else's offer; this makes the refusal
    # a sentence instead of an empty result.
    if cap.get("transporter_id") != user.id:
        raise Forbidden("That transport request was not sent to you.")
    if offer["status"] != "pending":
        raise ValidationFailed(f"This request was already {offer['status']}.")
    if offer.get("expires_at") and offer["expires_at"] < datetime.now(timezone.utc).isoformat():
        raise ValidationFailed("This request has expired.")

    cargo = float(offer.get("quantity_kg") or 0)
    if float(cap.get("available_capacity_kg") or 0) < cargo:
        raise ValidationFailed(
            f"This load is {cargo:g} kg and you have "
            f"{float(cap.get('available_capacity_kg') or 0):g} kg free.")

    shipment_id = offer.get("shipment_id")
    ship = user.db.table("shipments").select("*").eq("id", shipment_id).limit(1).execute().data
    if not ship:
        raise NotFound("The shipment for this request no longer exists.")
    ship = ship[0]
    if ship.get("transporter_id"):
        raise Duplicate("Another transporter has already taken this job.")

    order = user.db.table("orders").select("id,status,order_no,buyer_id,farmer_id") \
        .eq("id", ship["order_id"]).limit(1).execute().data
    if not order:
        raise NotFound("Order not found.")
    order = order[0]
    # Real bug seen in manual testing: an offer could be sent (and a
    # transporter could see it) while the order was only ACCEPTED, not yet
    # PAYMENT_HELD -- LOGISTICS_ASSIGNED is only reachable from PAYMENT_HELD
    # (state_machine.py). validate_transition alone raised a generic
    # InvalidStateTransition (409), which the frontend's blanket
    # "any 409 = someone else took it" mapping turned into "Another
    # transporter accepted this first" -- true for nobody. Named here instead.
    if order["status"] != "PAYMENT_HELD":
        raise ValidationFailed(
            "The buyer has not completed payment for this order yet. "
            "You will be able to accept once payment is held."
        )
    validate_transition(order["status"], "LOGISTICS_ASSIGNED", "transporter")

    # Claim. Conditioned on transporter_id still being unset, so two
    # simultaneous accepts cannot both write; whoever loses updates 0 rows.
    claimed = (
        user.db.table("shipments")
        .update({
            "transporter_id": user.id,
            "capacity_id": cap["id"],
            "status": "assigned",
            "transport_cost_estimate_paise": _estimate_cost_paise(cap, cargo),
        })
        .eq("id", shipment_id).is_("transporter_id", "null").execute()
    )
    if not claimed.data:
        raise Duplicate("Another transporter has already taken this job.")

    user.db.table("consolidation_requests").update({
        "status": "accepted",
        "responded_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", offer_id).execute()

    user.db.table("orders").update({"status": "LOGISTICS_ASSIGNED"}) \
        .eq("id", ship["order_id"]).execute()
    record_transition(user.db, ship["order_id"], order["status"], "LOGISTICS_ASSIGNED",
                      user.id, "transporter", "Transport offer accepted.")

    # Reserve the space so the same lorry is not offered the world.
    user.db.table("transport_capacity").update({
        "available_capacity_kg": max(
            float(cap.get("available_capacity_kg") or 0) - cargo, 0),
    }).eq("id", cap["id"]).execute()

    _retire_losing_offers(shipment_id, winning_offer_id=offer_id,
                           order_no=order.get("order_no"))

    for uid in (order.get("buyer_id"), order.get("farmer_id")):
        if uid:
            notify(uid, "transport_assigned", "notif.transport_assigned_title",
                   "notif.transport_assigned_body",
                   params={"order_no": order.get("order_no") or ""},
                   entity_type="order", entity_id=ship["order_id"])

    return {"ok": True, "shipment_id": shipment_id, "status": "assigned"}


@router.post("/transport/offers/{offer_id}/decline", dependencies=[require_transporter])
async def decline_offer(offer_id: str, body: OfferDeclineIn, user: CurrentUserDep):
    """Turn the job down (§11), leaving the shipment offerable to somebody else.

    Declining never touches the shipment: it stays `created` with no
    transporter, so any other outstanding offer is still live and the arranger
    can send more (§12). A decline is recorded, not silently dropped.
    """
    offer = (
        user.db.table("consolidation_requests")
        .select("*, transport_capacity(transporter_id), orders(order_no)")
        .eq("id", offer_id).limit(1).execute()
    ).data
    if not offer:
        raise NotFound("That transport request is not available.")
    offer = offer[0]
    cap = offer.pop("transport_capacity", None) or {}
    order = offer.pop("orders", None) or {}

    if cap.get("transporter_id") != user.id:
        raise Forbidden("That transport request was not sent to you.")
    if offer["status"] != "pending":
        raise ValidationFailed(f"This request was already {offer['status']}.")

    user.db.table("consolidation_requests").update({
        "status": "rejected",
        "responded_at": datetime.now(timezone.utc).isoformat(),
        "response_note": body.reason,
    }).eq("id", offer_id).execute()

    # Tell whoever is arranging transport, so the job does not quietly stall.
    still_open = (
        user.db.table("consolidation_requests").select("id")
        .eq("shipment_id", offer.get("shipment_id")).eq("status", "pending").execute()
    ).data or []
    notify(
        offer["requester_id"],
        "transport_declined",
        "notif.transport_declined_title",
        "notif.transport_declined_body" if still_open else "notif.transport_none_left_body",
        params={"order_no": order.get("order_no") or "", "remaining": len(still_open)},
        entity_type="order", entity_id=offer.get("order_id"),
    )

    return {"ok": True, "status": "rejected", "offers_still_open": len(still_open)}


def _retire_losing_offers(shipment_id: str, winning_offer_id: str,
                           order_no: str | None) -> None:
    """Close the other outstanding offers once the job is taken.

    Service-role: these rows belong to OTHER transporters' listings, and
    consolidation_update deliberately lets only the owning transporter touch
    them — correctly, since that policy is what stops a transporter cancelling
    a rival's offer. Retiring them is a consequence of an accept the router has
    already authorised, not a user action, so it runs as the system (A-12).
    Best-effort: the accept has happened either way, and a stale `pending` row
    is harmless because list_transport_jobs hides offers whose shipment is
    taken and accept_offer refuses them.
    """
    from ..db.admin_client import admin_client

    try:
        admin = admin_client()
        losers = (
            admin.table("consolidation_requests")
            .select("id, transport_capacity(transporter_id)")
            .eq("shipment_id", shipment_id).eq("status", "pending")
            .neq("id", winning_offer_id).execute()
        ).data or []
        for row in losers:
            admin.table("consolidation_requests").update({
                "status": "cancelled",
                "responded_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", row["id"]).execute()
            cap = row.get("transport_capacity") or {}
            if cap.get("transporter_id"):
                notify(cap["transporter_id"], "transport_offer_closed",
                       "notif.offer_closed_title", "notif.offer_closed_body",
                       params={"order_no": order_no or ""},
                       entity_type="consolidation_request", entity_id=row["id"])
    except Exception:  # noqa: BLE001 - never undo a completed assignment
        log.warning("could not retire losing offers for shipment %s",
                    shipment_id, exc_info=True)


@router.post("/shipments/{shipment_id}/status", dependencies=[require_transporter])
async def update_shipment_status(shipment_id: str, body: ShipmentUpdateIn,
                                  user: CurrentUserDep):
    """Transporter advances the shipment: picked_up -> in_transit -> arrived.

    Farmer/buyer confirmation gates the two ends of this chain, not the
    transporter alone: picked_up requires the farmer's pickup_confirmed_at
    (§3/§13 -- the transporter used to control every transition with no
    second actor at all), and 'delivered' isn't reachable here regardless of
    what the transporter reports -- only the buyer's own confirm-delivery
    call sets it.
    """
    ship = user.db.table("shipments").select("*") \
        .eq("id", shipment_id).eq("transporter_id", user.id).limit(1).execute()
    if not ship.data:
        raise NotFound("Shipment not found or not yours.")
    s = ship.data[0]

    if body.status == "picked_up" and not s.get("pickup_confirmed_at"):
        raise ValidationFailed(
            "The farmer has not confirmed the pickup yet. "
            "You will be able to mark this picked up once they do."
        )

    now = datetime.now(timezone.utc).isoformat()
    patch: dict = {"status": body.status}
    if body.status == "picked_up":
        patch["picked_up_at"] = now
    elif body.status == "in_transit":
        patch["journey_started_at"] = now
        patch["is_tracking"] = True
    elif body.status == "arrived":
        patch["arrived_at"] = now
        patch["is_tracking"] = False
    elif body.status == "cancelled":
        patch["is_tracking"] = False

    user.db.table("shipments").update(patch).eq("id", shipment_id).execute()

    order = user.db.table("orders").select("id,status,order_no,buyer_id,farmer_id") \
        .eq("id", s["order_id"]).limit(1).execute()
    order_row = order.data[0] if order.data else None

    # Map shipment status → order status. 'arrived' deliberately has no
    # order-status counterpart: the order stays IN_TRANSIT until the buyer's
    # own confirm-delivery call, which is the only path to DELIVERED.
    ORDER_MAP = {"picked_up": "PICKED_UP", "in_transit": "IN_TRANSIT"}
    if body.status in ORDER_MAP and order_row:
        order_status = ORDER_MAP[body.status]
        from_st = order_row["status"]
        validate_transition(from_st, order_status, "transporter")
        user.db.table("orders").update({"status": order_status}).eq("id", s["order_id"]).execute()
        record_transition(user.db, s["order_id"], from_st, order_status,
                          user.id, "transporter", body.note)

    if order_row and body.status == "in_transit":
        for uid in (order_row.get("buyer_id"), order_row.get("farmer_id")):
            if uid:
                notify(uid, "journey_started", "notif.journey_started_title",
                       "notif.journey_started_body",
                       params={"order_no": order_row.get("order_no") or ""},
                       entity_type="order", entity_id=s["order_id"])
    elif order_row and body.status == "arrived":
        if order_row.get("buyer_id"):
            notify(order_row["buyer_id"], "arrived_at_destination",
                   "notif.arrived_title", "notif.arrived_body",
                   params={"order_no": order_row.get("order_no") or ""},
                   entity_type="order", entity_id=s["order_id"])
        if order_row.get("farmer_id"):
            notify(order_row["farmer_id"], "arrived_at_destination",
                   "notif.arrived_title", "notif.arrived_body_farmer",
                   params={"order_no": order_row.get("order_no") or ""},
                   entity_type="order", entity_id=s["order_id"])

    return {"ok": True, "status": body.status}


@router.post("/shipments/{shipment_id}/confirm-pickup")
async def confirm_pickup(shipment_id: str, user: CurrentUserDep):
    """The farmer says the produce is ready and handed over (§3).

    This is the gate `update_shipment_status` checks before a transporter can
    mark 'picked_up' -- without it, nothing stopped the transporter alone
    from starting the journey the instant they were assigned.
    """
    ship = user.db.table("shipments").select("*, orders(id,status,farmer_id,order_no)") \
        .eq("id", shipment_id).limit(1).execute().data
    if not ship:
        raise NotFound("Shipment not found.")
    s = ship[0]
    order = s.pop("orders", None) or {}

    if order.get("farmer_id") != user.id:
        raise Forbidden("Only the farmer on this order can confirm pickup.")
    if s["status"] != "assigned":
        raise ValidationFailed(f"This shipment is {s['status']}, not ready to confirm.")
    if s.get("pickup_confirmed_at"):
        raise ValidationFailed("Pickup was already confirmed.")

    now = datetime.now(timezone.utc).isoformat()
    user.db.table("shipments").update({
        "pickup_confirmed_at": now, "pickup_confirmed_by": user.id,
    }).eq("id", shipment_id).execute()

    if s.get("transporter_id"):
        notify(s["transporter_id"], "pickup_confirmed",
               "notif.pickup_confirmed_title", "notif.pickup_confirmed_body",
               params={"order_no": order.get("order_no") or ""},
               entity_type="shipment", entity_id=shipment_id)

    return {"ok": True, "pickup_confirmed_at": now}


@router.post("/shipments/{shipment_id}/confirm-delivery")
async def confirm_delivery(shipment_id: str, user: CurrentUserDep):
    """The buyer says the goods actually arrived (§13).

    The transporter reaching the destination (status 'arrived') is a GPS fact
    the transporter or a geofence can report; it is never allowed to become
    'delivered' by itself. Only this call, by the buyer, does that -- and it
    is what the whole downstream chain (payment, order CLOSED, reviews)
    depends on being genuine.
    """
    ship = user.db.table("shipments").select("*, orders(id,status,buyer_id,farmer_id,order_no)") \
        .eq("id", shipment_id).limit(1).execute().data
    if not ship:
        raise NotFound("Shipment not found.")
    s = ship[0]
    order = s.pop("orders", None) or {}

    if order.get("buyer_id") != user.id:
        raise Forbidden("Only the buyer on this order can confirm delivery.")
    if s["status"] not in ("arrived", "in_transit"):
        raise ValidationFailed(f"This shipment is {s['status']}, nothing to confirm yet.")

    now = datetime.now(timezone.utc).isoformat()
    user.db.table("shipments").update({
        "status": "delivered", "delivered_at": now, "is_tracking": False,
    }).eq("id", shipment_id).execute()

    order_row = order
    if order_row.get("status"):
        validate_transition(order_row["status"], "DELIVERED", "buyer")
        user.db.table("orders").update({"status": "DELIVERED"}).eq("id", order["id"]).execute()
        record_transition(user.db, order["id"], order_row["status"], "DELIVERED",
                          user.id, "buyer", "Delivery confirmed by buyer.")

    if s.get("transporter_id"):
        notify(s["transporter_id"], "delivery_confirmed",
               "notif.delivery_confirmed_title", "notif.delivery_confirmed_body_transporter",
               params={"order_no": order.get("order_no") or ""},
               entity_type="order", entity_id=order["id"])
    if order.get("farmer_id"):
        notify(order["farmer_id"], "delivery_confirmed",
               "notif.delivery_confirmed_title", "notif.delivery_confirmed_body_farmer",
               params={"order_no": order.get("order_no") or ""},
               entity_type="order", entity_id=order["id"])

    return {"ok": True, "status": "delivered"}


@router.post("/shipments/{shipment_id}/location", dependencies=[require_transporter])
async def update_location(shipment_id: str, body: LocationUpdateIn, user: CurrentUserDep):
    """One GPS reading from the transporter's own device (§8/§9).

    Writes both the fast-path columns on `shipments` (what the live map reads)
    and a row in `shipment_locations` (the history trail that table already
    had RLS for and no writer). Throttled server-side -- a compromised or
    buggy client cannot flood this regardless of what the frontend intends.
    """
    ship = user.db.table("shipments").select("id,status,location_updated_at,drop_lat,drop_lon,order_id") \
        .eq("id", shipment_id).eq("transporter_id", user.id).limit(1).execute().data
    if not ship:
        raise NotFound("Shipment not found or not yours.")
    s = ship[0]
    if s["status"] not in ("picked_up", "in_transit"):
        raise ValidationFailed("Location updates are only accepted while a shipment is under way.")

    now = datetime.now(timezone.utc)
    last = s.get("location_updated_at")
    if last:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if (now - last_dt).total_seconds() < MIN_LOCATION_UPDATE_INTERVAL_S:
            return {"ok": True, "throttled": True}

    patch = {
        "current_lat": body.lat, "current_lon": body.lon,
        "current_heading": body.heading, "current_speed_kmph": body.speed_kmph,
        "current_accuracy_m": body.accuracy_m,
        "location_updated_at": now.isoformat(), "is_tracking": True,
    }

    # Auto-detect arrival from GPS (§11). Idempotent: a shipment already
    # 'arrived' or beyond does not get re-notified on every subsequent ping
    # inside the geofence.
    arrived_now = False
    if s["status"] == "in_transit" and s.get("drop_lat") is not None and s.get("drop_lon") is not None:
        distance_km = haversine(body.lat, body.lon, s["drop_lat"], s["drop_lon"])
        if distance_km * 1000 <= ARRIVAL_GEOFENCE_M:
            patch["status"] = "arrived"
            patch["arrived_at"] = now.isoformat()
            arrived_now = True

    user.db.table("shipments").update(patch).eq("id", shipment_id).execute()
    user.db.table("shipment_locations").insert({
        "shipment_id": shipment_id, "lat": body.lat, "lon": body.lon,
        "speed_kmph": body.speed_kmph, "heading": body.heading,
        "accuracy_m": body.accuracy_m,
    }).execute()

    if arrived_now:
        order = user.db.table("orders").select("buyer_id,farmer_id,order_no") \
            .eq("id", s["order_id"]).limit(1).execute().data
        if order:
            o = order[0]
            if o.get("buyer_id"):
                notify(o["buyer_id"], "arrived_at_destination", "notif.arrived_title",
                       "notif.arrived_body", params={"order_no": o.get("order_no") or ""},
                       entity_type="order", entity_id=s["order_id"])
            if o.get("farmer_id"):
                notify(o["farmer_id"], "arrived_at_destination", "notif.arrived_title",
                       "notif.arrived_body_farmer", params={"order_no": o.get("order_no") or ""},
                       entity_type="order", entity_id=s["order_id"])

    return {"ok": True, "arrived": arrived_now}


@router.get("/shipments/{shipment_id}/checkpoints")
async def shipment_checkpoints(shipment_id: str, user: CurrentUserDep):
    """The journey's checkpoints, derived from real timestamps on the
    shipment (§11) -- never a frontend-only fake state. RLS on the SELECT
    below (shipments_select) is what actually authorises this: only the
    transporter or an order participant can read the row at all.
    """
    s = user.db.table("shipments").select(
        "id,status,created_at,pickup_confirmed_at,picked_up_at,journey_started_at,"
        "arrived_at,delivered_at"
    ).eq("id", shipment_id).limit(1).execute().data
    if not s:
        raise NotFound("Shipment not found.")
    s = s[0]

    checkpoints = [
        {"code": "created", "at": s["created_at"], "done": True},
        {"code": "pickup_confirmed", "at": s.get("pickup_confirmed_at"),
         "done": bool(s.get("pickup_confirmed_at"))},
        {"code": "journey_started", "at": s.get("journey_started_at"),
         "done": bool(s.get("journey_started_at"))},
        {"code": "near_destination", "at": None, "done": False},  # ephemeral; not persisted
        {"code": "arrived", "at": s.get("arrived_at"), "done": bool(s.get("arrived_at"))},
        {"code": "delivered", "at": s.get("delivered_at"), "done": bool(s.get("delivered_at"))},
    ]
    return {"shipment_id": shipment_id, "status": s["status"], "checkpoints": checkpoints}


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
