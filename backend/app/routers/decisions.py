"""decisions.py — farmer decision support (SIH26132).

Phase 2 lands the Net Exit Optimizer here. The Risk-Adjusted Sale Window,
Dynamic Supply Aggregation and Emergency Exit Engine extend this router in later
phases rather than inventing their own, so the farmer-facing decision surface
stays in one place.

Read-only. Nothing here writes, reserves, or commits anything: it computes and
explains options, and the farmer acts through the existing order endpoints.

Authorization is farmer-only and ownership-checked. RLS already scopes
`products` to the owner, but the ownership assertion below is explicit so an
IDOR would fail loudly in the API rather than depending on a policy staying
correct forever.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from ..deps import CurrentUserDep, require_role
from ..errors import Forbidden, NotFound
from ..services import market_data as md
from ..services import net_exit
from ..services.opportunity import Opportunity

router = APIRouter(prefix="/api/decisions", tags=["decisions"])

require_farmer = Depends(require_role("farmer"))

# A lot is compared against at most this many mandi markets, nearest first, to
# keep one request bounded regardless of how many districts hold price data.
_MAX_MARKETS = 8


def _payment_reliability(buyer: dict | None) -> tuple[float | None, str]:
    """A trust signal from data that genuinely exists.

    UDGAM does not yet track completion or cancellation rates, so this reports
    what the profile actually carries — verification status and rating — and
    says exactly that. Inventing a reliability percentage would be worse than
    returning None.
    """
    if not buyer:
        return None, "buyer profile unavailable"
    verified = buyer.get("verification_status") == "verified"
    rating = buyer.get("avg_rating")
    count = buyer.get("rating_count") or 0
    if not verified and not count:
        return None, "unverified buyer with no completed ratings yet"
    score = 0.0
    parts = []
    if verified:
        score += 0.5
        parts.append("identity verified")
    if count:
        score += 0.5 * min(1.0, float(rating or 0) / 5.0)
        parts.append(f"{rating}/5 over {count} rating(s)")
    return round(min(1.0, score), 3), "; ".join(parts)


@router.get("/net-exit", dependencies=[require_farmer])
async def net_exit_options(user: CurrentUserDep, product_id: str, holding_days: int = 0):
    """Rank the ways this lot could be sold by expected farmer net realization.

    Compares platform sales against every buyer requirement open for the crop,
    and mandi sales in every market that has a price on record. Returns the
    arithmetic behind each option, not just a winner.

    Options that cannot be costed — a mandi with no price row, a route with no
    posted transport — are returned under `excluded` with the reason, never
    quietly filled in with a guess.
    """
    db = user.db

    # Postgres rejects a malformed uuid with 22P02, which would surface as a
    # bare 500 INTERNAL. A bad id is a caller mistake, so answer it as one.
    try:
        uuid.UUID(str(product_id))
    except (ValueError, AttributeError, TypeError):
        raise NotFound("That listing does not exist.")

    res = db.table("products").select("*").eq("id", product_id).limit(1).execute()
    if not res.data:
        raise NotFound("That listing does not exist.")
    product = res.data[0]
    if str(product.get("farmer_id")) != str(user.id):
        raise Forbidden("That listing belongs to another farmer.")

    crop_res = (db.table("crops")
                .select("id, code, name_en, category, default_shelf_life_days")
                .eq("id", product["crop_id"]).limit(1).execute())
    if not crop_res.data:
        raise NotFound("That listing's crop is missing.")
    crop = crop_res.data[0]

    origin = product.get("district") or (
        db.table("profiles").select("district").eq("id", user.id)
        .limit(1).execute().data or [{}]
    )[0].get("district")

    quantity = float(product.get("available_quantity_kg") or product.get("quantity_kg") or 0)

    # Posted capacity is fetched once and reused for every channel, so the
    # transport quote is derived identically wherever it appears.
    capacities = (db.table("transport_capacity")
                  .select("available_capacity_kg, price_paise_per_kg,"
                          " price_paise_per_km, discount_pct, dest_district, status")
                  .eq("status", "open").limit(200).execute()).data or []

    opportunities: list[Opportunity] = []

    # --- channel 1: platform sales against open buyer requirements ---------
    requests = (db.table("buyer_requests")
                .select("*, profiles!buyer_requests_buyer_id_fkey("
                        "full_name, verification_status, avg_rating, rating_count)")
                .eq("crop_id", product["crop_id"]).eq("status", "open")
                .limit(50).execute()).data or []

    for req in requests:
        buyer = req.pop("profiles", None) or {}
        reliability, basis = _payment_reliability(buyer)
        req["buyer_name"] = buyer.get("full_name") or "Buyer requirement"
        opportunities.append(net_exit.build_direct_buyer_opportunity(
            product=product, request=req, crop=crop,
            distance_km=md.district_distance_km(origin, req.get("delivery_district")),
            capacities=[c for c in capacities
                        if not c.get("dest_district")
                        or c.get("dest_district") == req.get("delivery_district")],
            holding_days=holding_days,
            payment_reliability=reliability, payment_reliability_basis=basis,
        ))

    # --- channel 2: mandi sales where a price exists -----------------------
    markets = sorted(
        md.MARKET_DISTRICTS,
        key=lambda d: (md.district_distance_km(origin, d) if origin else 0) or 0,
    )[:_MAX_MARKETS]

    for district in markets:
        row = (db.table("prices")
               .select("modal_price_paise, price_date, created_at, method,"
                       " data_source, is_prediction, horizon_days")
               .eq("crop_id", product["crop_id"]).eq("district", district)
               .eq("is_prediction", False)
               .order("price_date", desc=True).limit(1).execute()).data
        price_row = row[0] if row else None
        opportunities.append(net_exit.build_mandi_opportunity(
            product=product, crop=crop, district=district, price_row=price_row,
            distance_km=md.district_distance_km(origin, district),
            capacities=[c for c in capacities
                        if not c.get("dest_district") or c.get("dest_district") == district],
            holding_days=holding_days,
            price_provenance=md.provenance(price_row) if price_row else None,
        ))

    result = net_exit.rank(opportunities)
    return {
        "product": {
            "id": product["id"], "crop_id": product["crop_id"],
            "crop_code": crop.get("code"), "crop_name": crop.get("name_en"),
            "grade": product.get("grade"), "quantity_kg": quantity,
            "asking_price_paise": product.get("asking_price_paise"),
            "district": origin,
        },
        "holding_days": holding_days,
        "best": result["best"].to_dict() if result["best"] else None,
        "ranked": [o.to_dict() for o in result["ranked"]],
        "excluded": [o.to_dict() for o in result["excluded"]],
        "ranked_by": result["ranked_by"],
        "method": result["method"],
        "assumptions": result["assumptions"],
        "availability": "ok" if result["best"] else "insufficient_data",
    }
