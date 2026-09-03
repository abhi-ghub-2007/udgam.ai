"""auth router - session, config, bootstrap (API_CONTRACT section 1).

Login/logout/refresh happen in the browser via the Supabase JS client
(permitted by plan.md section 3). FastAPI never sees a password.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings
from ..db.supabase_client import anon_client
from ..deps import CurrentUserDep, IdentityDep
from ..errors import AppError, NotFound

router = APIRouter(prefix="/api", tags=["auth"])


# ---------------------------------------------------------------- schemas
class RoleDetails(BaseModel):
    # farmer
    land_area_acres: float | None = None
    primary_crop_ids: list[str] = Field(default_factory=list)
    fpo_name: str | None = None          # present => this account is an FPO
    # buyer
    buyer_type: Literal["individual", "bulk"] | None = None
    business_name: str | None = None
    gstin: str | None = None
    delivery_pincode: str | None = None
    # transporter
    vehicle_type: str | None = None
    vehicle_reg_no: str | None = None
    capacity_kg: float | None = None
    licence_no: str | None = None


class RegisterIn(BaseModel):
    role: Literal["farmer", "buyer", "transporter"]
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None
    preferred_language: Literal["en", "hi", "mr"] = "en"
    role_details: RoleDetails = Field(default_factory=RoleDetails)


class ActivateIn(BaseModel):
    """FPO-invited farmer sets their own password (A-5 / PRD R-3)."""
    invite_code: str = Field(min_length=6, max_length=6)
    phone: str
    new_password: str = Field(min_length=8)


# ---------------------------------------------------------------- routes
@router.get("/config")
async def get_config():
    """How the anon key reaches the browser without living in a committed
    file (A-16). The service-role key is never returned here or anywhere."""
    return {
        "supabase_url": settings.SUPABASE_URL,
        "supabase_anon_key": settings.SUPABASE_ANON_KEY,
        "languages": ["en", "hi", "mr"],
        "app_env": settings.APP_ENV,
        "configured": settings.supabase_configured,
    }


@router.get("/health")
async def health():
    db_ok = False
    if settings.supabase_configured:
        try:
            anon_client().table("crops").select("id").limit(1).execute()
            db_ok = True
        except Exception:  # noqa: BLE001 - health must never raise
            db_ok = False
    return {
        "status": "ok",
        "db": "up" if db_ok else ("down" if settings.supabase_configured else "unconfigured"),
        "integrations": {
            "mandi": settings.integration_mode("AGMARKNET_API_KEY", "price data"),
            "weather": settings.integration_mode("OPENWEATHERMAP_API_KEY", "weather"),
            "maps": "live" if settings.OSRM_BASE_URL and not settings.USE_MOCK_INTEGRATIONS else "mock",
            "payments": settings.integration_mode("RAZORPAY_KEY_ID", "payments"),
            "sms": "mock",
        },
    }


@router.post("/auth/register", status_code=201)
async def register(body: RegisterIn, user: IdentityDep):
    """Completes signup after Supabase Auth has created the user.

    Creates `profiles` + the role detail row (+ `fpos` when an FPO name is
    supplied). Called once, immediately after the browser's signUp() returns.
    """
    db, d = user.db, body.role_details

    db.table("profiles").upsert({
        "id": user.id,
        "role": body.role,
        "full_name": body.full_name,
        "phone": body.phone,
        "email": user.email,
        "district": body.district,
        "state": body.state,
        "pincode": body.pincode,
        "preferred_language": body.preferred_language,
    }).execute()

    if body.role == "farmer":
        if d.fpo_name:
            # An FPO is a farmer login with one extra capability (A-5).
            db.table("fpos").upsert({
                "profile_id": user.id, "fpo_name": d.fpo_name,
                "district": body.district, "state": body.state,
            }).execute()
        db.table("farmer_profiles").upsert({
            "profile_id": user.id,
            "land_area_acres": d.land_area_acres,
            "primary_crop_ids": d.primary_crop_ids,
            "onboarding_status": "active",
        }).execute()

    elif body.role == "buyer":
        db.table("buyer_profiles").upsert({
            "profile_id": user.id,
            "buyer_type": d.buyer_type or "individual",
            "business_name": d.business_name,
            "gstin": d.gstin,
            "delivery_pincode": d.delivery_pincode or body.pincode,
        }).execute()

    else:
        db.table("transporter_profiles").upsert({
            "profile_id": user.id,
            "vehicle_type": d.vehicle_type,
            "vehicle_reg_no": d.vehicle_reg_no,
            "capacity_kg": d.capacity_kg or 0,
            "licence_no": d.licence_no,
        }).execute()

    return await me(user)


@router.get("/auth/me")
async def me(user: CurrentUserDep):
    """Current profile + role detail row. The frontend role-gate calls this
    on every page load."""
    db = user.db
    res = db.table("profiles").select("*").eq("id", user.id).limit(1).execute()
    if not res.data:
        raise NotFound("Profile not found.")
    profile = res.data[0]

    detail_table = {
        "farmer": "farmer_profiles",
        "buyer": "buyer_profiles",
        "transporter": "transporter_profiles",
    }[profile["role"]]
    detail = db.table(detail_table).select("*").eq("profile_id", user.id).limit(1).execute()

    is_fpo = False
    if profile["role"] == "farmer":
        fpo = db.table("fpos").select("profile_id").eq("profile_id", user.id).execute()
        is_fpo = bool(fpo.data)

    return {
        "profile": profile,
        "details": detail.data[0] if detail.data else {},
        "is_fpo": is_fpo,
    }


@router.post("/auth/activate")
async def activate(body: ActivateIn):
    """Invited farmer claims their own account (A-5).

    Implemented in module 1.6 alongside the FPO invite endpoint that issues
    the code; wired here so the contract's surface is complete from Phase 1.
    """
    raise AppError(
        "Account activation is not available yet.",
        code="NOT_IMPLEMENTED", status_code=501,
    )
