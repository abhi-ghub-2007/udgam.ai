"""buyer_matching.py — buyer requests + smart matching (API_CONTRACT §5).

Requests are the buyer's half of the marketplace loop (F-6/B-3). Matching
(AI-5) is ALGORITHMIC (A-17): a transparent weighted score with a per-candidate
`reasons[]` breakdown, never a black box. RLS scopes every read/write.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import CurrentUserDep, require_role
from ..errors import NotFound, ValidationFailed

router = APIRouter(prefix="/api", tags=["requests", "matching"])

require_buyer = Depends(require_role("buyer"))
require_farmer = Depends(require_role("farmer"))

_REQ_SELECT = "*, crops(code,name_en,name_hi,name_mr,category)"
_GRADE_RANK = {"A": 3, "B": 2, "C": 1}


def _flatten_req(row: dict) -> dict:
    crop = row.pop("crops", None) or {}
    row["crop_code"] = crop.get("code")
    row["crop_name"] = crop.get("name_en")
    row["crop_name_hi"] = crop.get("name_hi")
    row["crop_name_mr"] = crop.get("name_mr")
    return row


# ---------------------------------------------------------------- schemas
class RequestIn(BaseModel):
    crop_id: str
    quantity_kg: float = Field(gt=0)
    min_grade: str = Field(default="C", pattern="^[ABC]$")
    target_price_paise: int | None = Field(default=None, gt=0)
    needed_by: date | None = None
    delivery_pincode: str | None = None
    delivery_district: str | None = None
    notes: str | None = Field(default=None, max_length=1000)


class RequestPatch(BaseModel):
    quantity_kg: float | None = Field(default=None, gt=0)
    target_price_paise: int | None = Field(default=None, gt=0)
    needed_by: date | None = None
    status: str | None = Field(default=None, pattern="^(open|cancelled)$")
    notes: str | None = Field(default=None, max_length=1000)


# ---------------------------------------------------------------- requests
@router.post("/buyer-requests", status_code=201, dependencies=[require_buyer])
async def create_request(body: RequestIn, user: CurrentUserDep):
    district = body.delivery_district
    if not district:
        prof = user.db.table("profiles").select("district").eq("id", user.id).limit(1).execute()
        district = prof.data[0]["district"] if prof.data else None
    row = {
        "buyer_id": user.id,
        "crop_id": body.crop_id,
        "quantity_kg": body.quantity_kg,
        "min_grade": body.min_grade,
        "target_price_paise": body.target_price_paise,
        "needed_by": body.needed_by.isoformat() if body.needed_by else None,
        "delivery_pincode": body.delivery_pincode,
        "delivery_district": district,
        "notes": body.notes,
        "status": "open",
    }
    res = user.db.table("buyer_requests").insert(row).execute()
    if not res.data:
        raise ValidationFailed("Could not post the request.")
    return _flatten_req(
        user.db.table("buyer_requests").select(_REQ_SELECT)
        .eq("id", res.data[0]["id"]).limit(1).execute().data[0]
    )


@router.get("/buyer-requests")
async def list_requests(
    user: CurrentUserDep,
    crop_id: str | None = None,
    district: str | None = None,
    min_qty: float | None = None,
):
    """F-6: EVERY farmer sees ALL open requests. RLS returns open rows (+ the
    caller's own); filters narrow the feed."""
    q = user.db.table("buyer_requests").select(_REQ_SELECT).eq("status", "open")
    if crop_id:
        q = q.eq("crop_id", crop_id)
    if district:
        q = q.eq("delivery_district", district)
    if min_qty:
        q = q.gte("quantity_kg", min_qty)
    res = q.order("created_at", desc=True).limit(100).execute()
    return {"requests": [_flatten_req(r) for r in res.data]}


@router.get("/buyer-requests/mine", dependencies=[require_buyer])
async def my_requests(user: CurrentUserDep):
    res = (
        user.db.table("buyer_requests").select(_REQ_SELECT)
        .eq("buyer_id", user.id).order("created_at", desc=True).execute()
    )
    return {"requests": [_flatten_req(r) for r in res.data]}


@router.patch("/buyer-requests/{request_id}", dependencies=[require_buyer])
async def update_request(request_id: str, body: RequestPatch, user: CurrentUserDep):
    patch = body.model_dump(exclude_none=True)
    if body.needed_by:
        patch["needed_by"] = body.needed_by.isoformat()
    if body.status == "cancelled":
        patch["status"] = "cancelled"
    if not patch:
        raise ValidationFailed("Nothing to update.")
    res = (
        user.db.table("buyer_requests").update(patch)
        .eq("id", request_id).eq("buyer_id", user.id).execute()
    )
    if not res.data:
        raise NotFound("Request not found or not yours.")
    return _flatten_req(
        user.db.table("buyer_requests").select(_REQ_SELECT)
        .eq("id", request_id).limit(1).execute().data[0]
    )


# ---------------------------------------------------------------- AI-5 matching
def _score_listing_for_request(p: dict, req: dict) -> tuple[float, list[str]]:
    """Weighted fit of one listing against one request. Transparent by design:
    each term is named in `reasons`."""
    reasons: list[str] = []
    score = 0.0

    # Grade meets the floor (0 or 35). Below floor disqualifies later.
    pg = _GRADE_RANK.get(p.get("grade") or "C", 1)
    rg = _GRADE_RANK.get(req.get("min_grade") or "C", 1)
    if pg >= rg:
        score += 35
        reasons.append(f"grade {p.get('grade') or '?'} meets min {req.get('min_grade')}")

    # Price fit (0..35): at or below target is full marks, scaling down above.
    target = req.get("target_price_paise")
    ask = p.get("asking_price_paise") or 0
    if target and ask:
        if ask <= target:
            score += 35
            reasons.append("price at/under target")
        else:
            over = (ask - target) / target
            score += max(0.0, 35 * (1 - min(over, 1)))
            reasons.append(f"price {over:.0%} over target")
    else:
        score += 15
        reasons.append("no target price given")

    # Proximity (0..20): same district is the cheap, reliable win.
    if p.get("district") and p["district"] == req.get("delivery_district"):
        score += 20
        reasons.append("same district")
    elif p.get("district"):
        reasons.append(f"different district ({p['district']})")

    # Quantity coverage (0..10).
    if (p.get("available_quantity_kg") or 0) >= (req.get("quantity_kg") or 0):
        score += 10
        reasons.append("can cover full quantity")

    return round(score, 1), reasons


@router.get("/matching/listings", dependencies=[require_buyer])
async def match_listings(user: CurrentUserDep):
    """Listings recommended for this buyer, ranked against their open requests.
    method: ALGORITHMIC."""
    reqs = (
        user.db.table("buyer_requests").select("*")
        .eq("buyer_id", user.id).eq("status", "open").execute()
    ).data
    if not reqs:
        return {"method": "ALGORITHMIC", "matches": [], "note": "Post a request to get matches."}

    crop_ids = list({r["crop_id"] for r in reqs})
    prods = (
        user.db.table("products").select("*, crops(code,name_en,name_hi,name_mr)")
        .in_("crop_id", crop_ids).eq("status", "active").limit(200).execute()
    ).data

    ranked = []
    for p in prods:
        best = max(
            (_score_listing_for_request(p, r) for r in reqs if r["crop_id"] == p["crop_id"]),
            default=(0.0, []), key=lambda t: t[0],
        )
        if best[0] > 0:
            ranked.append({**_flatten_req(dict(p)), "score": best[0], "reasons": best[1]})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {"method": "ALGORITHMIC", "matches": ranked[:30]}


@router.get("/matching/requests", dependencies=[require_farmer])
async def match_requests(user: CurrentUserDep, product_id: str):
    """Open requests ranked by fit for one of the farmer's listings (F-6)."""
    prod = (
        user.db.table("products").select("*")
        .eq("id", product_id).eq("farmer_id", user.id).limit(1).execute()
    )
    if not prod.data:
        raise NotFound("Listing not found or not yours.")
    p = prod.data[0]

    reqs = (
        user.db.table("buyer_requests").select(_REQ_SELECT)
        .eq("crop_id", p["crop_id"]).eq("status", "open").limit(200).execute()
    ).data

    ranked = []
    for r in reqs:
        score, reasons = _score_listing_for_request(p, r)
        if score > 0:
            ranked.append({**_flatten_req(dict(r)), "score": score, "reasons": reasons})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {"method": "ALGORITHMIC", "matches": ranked[:30]}


@router.get("/matching/buyers", dependencies=[require_farmer])
async def match_buyers(user: CurrentUserDep):
    """Recommend buyers (F-5): open requests across the farmer's listed crops,
    ranked by fit against the farmer's best matching listing."""
    mine = (
        user.db.table("products").select("*")
        .eq("farmer_id", user.id).eq("status", "active").execute()
    ).data
    if not mine:
        return {"method": "ALGORITHMIC", "matches": [], "note": "List produce to see buyers."}

    crop_ids = list({p["crop_id"] for p in mine})
    reqs = (
        user.db.table("buyer_requests").select(_REQ_SELECT)
        .in_("crop_id", crop_ids).eq("status", "open").limit(200).execute()
    ).data

    ranked = []
    for r in reqs:
        candidates = [p for p in mine if p["crop_id"] == r["crop_id"]]
        best = max((_score_listing_for_request(p, r) for p in candidates),
                   default=(0.0, []), key=lambda t: t[0])
        if best[0] > 0:
            ranked.append({**_flatten_req(dict(r)), "score": best[0], "reasons": best[1]})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {"method": "ALGORITHMIC", "matches": ranked[:30]}
