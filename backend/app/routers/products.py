"""products.py — farmer listings & marketplace browse (API_CONTRACT §4).

Every query runs on the caller's JWT-bound client, so Postgres RLS — not this
router — decides who may read a draft or write a listing (PRD R-12). The
ownership re-checks here are for clean 403/404 messages, not for security.
"""
from __future__ import annotations

from datetime import date

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field

from ..db.admin_client import admin_client
from ..deps import CurrentUserDep, require_role
from ..errors import NotFound, ValidationFailed
from ..services.grading import grade_image

router = APIRouter(prefix="/api", tags=["products"])

require_farmer = Depends(require_role("farmer"))

# One nested select reused everywhere so crop names ride along with the row.
_SELECT = "*, crops(code,name_en,name_hi,name_mr,category)"


def _flatten(row: dict) -> dict:
    """Lift the joined crop names onto the product for a flat client payload."""
    crop = row.pop("crops", None) or {}
    row["crop_code"] = crop.get("code")
    row["crop_name"] = crop.get("name_en")
    row["crop_name_hi"] = crop.get("name_hi")
    row["crop_name_mr"] = crop.get("name_mr")
    row["photo_url"] = public_photo_url(row.get("photo_path"))
    return row


# ---------------------------------------------------------------- schemas
class ProductIn(BaseModel):
    crop_id: str
    quantity_kg: float = Field(gt=0)
    asking_price_paise: int = Field(gt=0)
    harvest_date: date | None = None
    available_until: date | None = None
    description: str | None = Field(default=None, max_length=1000)
    location_id: str | None = None
    district: str | None = None


class ProductPatch(BaseModel):
    quantity_kg: float | None = Field(default=None, gt=0)
    asking_price_paise: int | None = Field(default=None, gt=0)
    available_until: date | None = None
    description: str | None = Field(default=None, max_length=1000)
    status: str | None = None


def public_photo_url(path: str | None) -> str | None:
    """Public URL for a stored photo. The bucket is public, so this is a plain
    string build — no signing round-trip on every list render."""
    if not path:
        return None
    from ..config import settings
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/product-photos/{path}"


# ---------------------------------------------------------------- browse
@router.get("/products")
async def list_products(
    user: CurrentUserDep,
    crop_id: str | None = None,
    grade: str | None = None,
    min_qty: float | None = None,
    max_price: int | None = None,
    district: str | None = None,
    sort: str = Query("recent", pattern="^(recent|price_asc|price_desc)$"),
):
    """Marketplace browse. RLS already limits rows to live listings (+ the
    caller's own); the filters below just narrow that set."""
    q = user.db.table("products").select(_SELECT).in_("status", ["active", "reserved"])
    if crop_id:
        q = q.eq("crop_id", crop_id)
    if grade:
        q = q.eq("grade", grade)
    if min_qty:
        q = q.gte("available_quantity_kg", min_qty)
    if max_price:
        q = q.lte("asking_price_paise", max_price)
    if district:
        q = q.eq("district", district)

    if sort == "price_asc":
        q = q.order("asking_price_paise")
    elif sort == "price_desc":
        q = q.order("asking_price_paise", desc=True)
    else:
        q = q.order("created_at", desc=True)

    res = q.limit(100).execute()
    return {"products": [_flatten(r) for r in res.data]}


@router.get("/products/mine", dependencies=[require_farmer])
async def my_products(user: CurrentUserDep):
    res = (
        user.db.table("products").select(_SELECT)
        .eq("farmer_id", user.id).order("created_at", desc=True).execute()
    )
    return {"products": [_flatten(r) for r in res.data]}


@router.get("/products/{product_id}")
async def get_product(product_id: str, user: CurrentUserDep):
    res = user.db.table("products").select(_SELECT).eq("id", product_id).limit(1).execute()
    if not res.data:
        raise NotFound("Listing not found.")
    product = _flatten(res.data[0])

    grades = (
        user.db.table("quality_grades").select("*")
        .eq("product_id", product_id).order("created_at", desc=True).limit(1).execute()
    )
    farmer = (
        user.db.table("profiles")
        .select("id,full_name,district,state,avg_rating,rating_count,verification_status")
        .eq("id", product["farmer_id"]).limit(1).execute()
    )
    return {
        "product": product,
        "quality_grade": grades.data[0] if grades.data else None,
        "farmer": farmer.data[0] if farmer.data else None,
    }


# ---------------------------------------------------------------- write
@router.post("/products", status_code=201, dependencies=[require_farmer])
async def create_product(body: ProductIn, user: CurrentUserDep):
    district = body.district
    if not district and body.location_id:
        loc = (
            user.db.table("locations").select("district")
            .eq("id", body.location_id).limit(1).execute()
        )
        district = loc.data[0]["district"] if loc.data else None
    if not district:
        prof = user.db.table("profiles").select("district").eq("id", user.id).limit(1).execute()
        district = prof.data[0]["district"] if prof.data else None

    row = {
        "farmer_id": user.id,
        "crop_id": body.crop_id,
        "quantity_kg": body.quantity_kg,
        "available_quantity_kg": body.quantity_kg,
        "asking_price_paise": body.asking_price_paise,
        "harvest_date": body.harvest_date.isoformat() if body.harvest_date else None,
        "available_until": body.available_until.isoformat() if body.available_until else None,
        "description": body.description,
        "location_id": body.location_id,
        "district": district,
        "status": "active",     # live immediately; grade fills in after photo
    }
    res = user.db.table("products").insert(row).execute()
    if not res.data:
        raise ValidationFailed("Could not create the listing.")
    return _flatten(
        user.db.table("products").select(_SELECT)
        .eq("id", res.data[0]["id"]).limit(1).execute().data[0]
    )


@router.patch("/products/{product_id}")
async def update_product(product_id: str, body: ProductPatch, user: CurrentUserDep):
    patch = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "status" in patch and patch["status"] not in {"active", "withdrawn"}:
        raise ValidationFailed("Status can only be set to active or withdrawn.", field="status")
    if not patch:
        raise ValidationFailed("Nothing to update.")
    res = (
        user.db.table("products").update(patch)
        .eq("id", product_id).eq("farmer_id", user.id).execute()
    )
    if not res.data:
        raise NotFound("Listing not found or not yours.")
    return _flatten(
        user.db.table("products").select(_SELECT)
        .eq("id", product_id).limit(1).execute().data[0]
    )


@router.delete("/products/{product_id}", status_code=200)
async def withdraw_product(product_id: str, user: CurrentUserDep):
    """Soft-delete: listings are never hard-deleted (they may be referenced by
    orders). Sets status='withdrawn' so it leaves the marketplace."""
    res = (
        user.db.table("products").update({"status": "withdrawn"})
        .eq("id", product_id).eq("farmer_id", user.id).execute()
    )
    if not res.data:
        raise NotFound("Listing not found or not yours.")
    return {"ok": True, "id": product_id, "status": "withdrawn"}


# ---------------------------------------------------------------- AI-1 grade
@router.post("/products/{product_id}/photo", dependencies=[require_farmer])
async def grade_photo(product_id: str, user: CurrentUserDep, file: UploadFile = File(...)):
    """Accepts the photo directly, runs AI-1 on it, stores it, writes the grade.

    The browser uploads THROUGH this endpoint rather than straight to Storage.
    Storage RLS would otherwise need a per-user object policy, and a failed
    upload is indistinguishable from a failed grade at the UI. Doing it here
    keeps the frontend free of any storage credential (A-12 still holds: the
    service-role key never leaves the server) and makes AI-1 the single
    authority on the grade. Returns the grade WITH its feature breakdown — the
    visible artefact from PRD §13 step 2.
    """
    prod = (
        user.db.table("products").select("id,farmer_id,crops(code)")
        .eq("id", product_id).eq("farmer_id", user.id).limit(1).execute()
    )
    if not prod.data:
        raise NotFound("Listing not found or not yours.")
    crop_code = (prod.data[0].get("crops") or {}).get("code")

    image_bytes = await file.read()
    if not image_bytes:
        raise ValidationFailed("The photo was empty.", field="file")
    if len(image_bytes) > 8 * 1024 * 1024:
        raise ValidationFailed("Photo must be under 8 MB.", field="file")

    try:
        g = grade_image(image_bytes, crop_code)
    except ValueError as exc:
        raise ValidationFailed(str(exc), field="file") from exc

    ext = (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        ext = "jpg"
    photo_path = f"{user.id}/{uuid.uuid4()}.{ext}"
    try:
        admin_client().storage.from_("product-photos").upload(
            photo_path, image_bytes,
            {"content-type": file.content_type or "image/jpeg"},
        )
    except Exception:  # noqa: BLE001 - a stored photo is not worth losing the grade over
        photo_path = None

    user.db.table("quality_grades").insert({
        "product_id": product_id,
        "photo_path": photo_path or "unstored",
        "grade": g.grade,
        "confidence": g.confidence,
        "method": g.method,
        "features": g.features,
    }).execute()

    patch = {
        "grade": g.grade,
        "grade_confidence": g.confidence,
        "grade_method": g.method,
    }
    if photo_path:
        patch["photo_path"] = photo_path
    user.db.table("products").update(patch).eq("id", product_id).execute()

    return {
        "grade": g.grade,
        "confidence": g.confidence,
        "method": g.method,
        "features": g.features,
        "reasons": g.reasons,
        "photo_path": photo_path,
        "photo_url": public_photo_url(photo_path),
    }
