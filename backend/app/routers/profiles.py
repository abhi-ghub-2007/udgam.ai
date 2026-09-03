"""profiles router - profile, ratings, crop master (API_CONTRACT section 2)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..deps import CurrentUserDep
from ..errors import NotFound
from ..services.masking import mask_phone, may_see_phone

router = APIRouter(prefix="/api", tags=["profiles"])


class ProfilePatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None
    address_line: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None
    preferred_language: Literal["en", "hi", "mr"] | None = None


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str, user: CurrentUserDep):
    """Public profile card. Phone is masked unless the caller shares an order
    with this profile at ACCEPTED or later (A-13)."""
    res = (
        user.db.table("profiles")
        .select("id, role, full_name, phone, district, state, avg_rating, "
                "rating_count, verification_status, is_storage_provider, created_at")
        .eq("id", profile_id).limit(1).execute()
    )
    if not res.data:
        raise NotFound("Profile not found.")

    profile = res.data[0]
    if profile["id"] != user.id and not may_see_phone(user, profile_id):
        profile["phone"] = mask_phone(profile.get("phone"))
    return {"profile": profile}


@router.patch("/profiles/me")
async def update_me(body: ProfilePatch, user: CurrentUserDep):
    patch = body.model_dump(exclude_none=True)
    if not patch:
        return await _me_profile(user)
    user.db.table("profiles").update(patch).eq("id", user.id).execute()
    return await _me_profile(user)


async def _me_profile(user: CurrentUserDep):
    res = user.db.table("profiles").select("*").eq("id", user.id).limit(1).execute()
    if not res.data:
        raise NotFound("Profile not found.")
    return {"profile": res.data[0]}


@router.get("/profiles/me/ratings")
async def my_ratings(user: CurrentUserDep, limit: int = 20, offset: int = 0):
    res = (
        user.db.table("feedback")
        .select("id, order_id, rater_id, rating, tags, comment, created_at")
        .eq("ratee_id", user.id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    rows = res.data or []
    tally: dict[str, int] = {}
    for r in rows:
        for tag in r.get("tags") or []:
            tally[tag] = tally.get(tag, 0) + 1
    return {"items": rows, "tag_histogram": tally, "limit": limit, "offset": offset}


@router.post("/profiles/me/storage-provider")
async def toggle_storage_provider(user: CurrentUserDep, enabled: bool = True):
    """Gate for T-9: only a flagged profile may create storage_listings."""
    user.db.table("profiles").update({"is_storage_provider": enabled}).eq("id", user.id).execute()
    return {"is_storage_provider": enabled}


@router.get("/crops")
async def list_crops(user: CurrentUserDep):
    res = user.db.table("crops").select("*").order("name_en").execute()
    return {"items": res.data or []}
