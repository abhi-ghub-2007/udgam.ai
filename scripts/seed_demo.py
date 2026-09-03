"""Seed reference + demo data (A-12: allowed to use the service-role key).

Idempotent: upserts on natural keys, so re-running never duplicates. Run with
the project venv:  .venv/Scripts/python.exe scripts/seed_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.db.admin_client import admin_client  # noqa: E402

# Common Indian crops. shelf_life drives the freshness/expiry logic later.
CROPS = [
    ("TOMATO",   "Tomato",        "टमाटर",      "टोमॅटो",       "vegetable", 7),
    ("ONION",    "Onion",         "प्याज",       "कांदा",        "vegetable", 60),
    ("POTATO",   "Potato",        "आलू",         "बटाटा",        "vegetable", 90),
    ("WHEAT",    "Wheat",         "गेहूँ",        "गहू",          "grain",     365),
    ("RICE",     "Rice",          "चावल",        "तांदूळ",       "grain",     365),
    ("MAIZE",    "Maize",         "मक्का",        "मका",          "grain",     180),
    ("SOYBEAN",  "Soybean",       "सोयाबीन",     "सोयाबीन",      "oilseed",   180),
    ("COTTON",   "Cotton",        "कपास",        "कापूस",        "fibre",     180),
    ("SUGARCANE","Sugarcane",     "गन्ना",        "ऊस",           "cash",      14),
    ("BANANA",   "Banana",        "केला",        "केळी",         "fruit",     7),
    ("MANGO",    "Mango",         "आम",          "आंबा",         "fruit",     10),
    ("GRAPES",   "Grapes",        "अंगूर",        "द्राक्षे",      "fruit",     10),
    ("CHILLI",   "Green Chilli",  "हरी मिर्च",    "हिरवी मिरची",  "vegetable", 10),
    ("BRINJAL",  "Brinjal",       "बैंगन",        "वांगी",        "vegetable", 7),
    ("OKRA",     "Okra",          "भिंडी",        "भेंडी",        "vegetable", 5),
    ("CAULIFLOWER","Cauliflower", "फूलगोभी",      "फ्लॉवर",       "vegetable", 7),
    ("SPINACH",  "Spinach",       "पालक",         "पालक",         "vegetable", 3),
    ("GROUNDNUT","Groundnut",     "मूंगफली",      "भुईमूग",       "oilseed",   180),
    ("TURMERIC", "Turmeric",      "हल्दी",        "हळद",          "spice",     365),
    ("PomeGRANATE","Pomegranate", "अनार",         "डाळिंब",       "fruit",     21),
]


def seed_crops() -> int:
    rows = [
        {"code": c, "name_en": en, "name_hi": hi, "name_mr": mr,
         "category": cat, "default_shelf_life_days": days}
        for (c, en, hi, mr, cat, days) in CROPS
    ]
    admin_client().table("crops").upsert(rows, on_conflict="code").execute()
    return len(rows)


# Demo accounts the landing-page role picker signs into (see landing.js). The
# password is shared and public on purpose — these are throwaway demo logins on
# a throwaway project, never real users.
DEMO_PASSWORD = "Udgam@1234"
DEMO_USERS = [
    {"key": "farmer", "email": "demo.farmer@udgam.test", "role": "farmer",
     "full_name": "Ramesh Patil", "district": "Nashik", "state": "Maharashtra",
     "phone": "9800000001"},
    {"key": "buyer", "email": "demo.buyer@udgam.test", "role": "buyer",
     "full_name": "Sunita Deshmukh", "district": "Pune", "state": "Maharashtra",
     "phone": "9800000002"},
    {"key": "transporter", "email": "demo.transporter@udgam.test", "role": "transporter",
     "full_name": "Vikram Rao", "district": "Kolhapur", "state": "Maharashtra",
     "phone": "9800000003"},
]


def _ensure_auth_user(email: str) -> str:
    """Create the auth user (email pre-confirmed, so no email is ever sent and
    no email rate limit applies). Returns the user id, reusing an existing one."""
    admin = admin_client()
    try:
        res = admin.auth.admin.create_user({
            "email": email, "password": DEMO_PASSWORD, "email_confirm": True,
        })
        return res.user.id
    except Exception:  # noqa: BLE001 - already exists; find and return its id
        page = admin.auth.admin.list_users()
        users = page if isinstance(page, list) else getattr(page, "users", [])
        for u in users:
            if getattr(u, "email", None) == email:
                # Reset the password so the known demo password always works.
                admin.auth.admin.update_user_by_id(u.id, {"password": DEMO_PASSWORD})
                return u.id
        raise


def _crop_id(code: str) -> str:
    r = admin_client().table("crops").select("id").eq("code", code).limit(1).execute()
    return r.data[0]["id"]


def seed_demo_users() -> dict[str, str]:
    admin = admin_client()
    ids: dict[str, str] = {}
    for u in DEMO_USERS:
        uid = _ensure_auth_user(u["email"])
        ids[u["key"]] = uid
        admin.table("profiles").upsert({
            "id": uid, "role": u["role"], "full_name": u["full_name"],
            "email": u["email"], "phone": u["phone"],
            "district": u["district"], "state": u["state"], "preferred_language": "en",
        }).execute()
        if u["role"] == "farmer":
            admin.table("farmer_profiles").upsert(
                {"profile_id": uid, "onboarding_status": "active", "land_area_acres": 3.5},
            ).execute()
        elif u["role"] == "buyer":
            admin.table("buyer_profiles").upsert(
                {"profile_id": uid, "buyer_type": "bulk", "business_name": "Deshmukh Traders",
                 "delivery_pincode": "411001"},
            ).execute()
        else:
            admin.table("transporter_profiles").upsert(
                {"profile_id": uid, "vehicle_type": "Tata Ace", "capacity_kg": 750,
                 "vehicle_reg_no": "MH12AB1234"},
            ).execute()
    return ids


def seed_market(ids: dict[str, str]) -> tuple[int, int]:
    """A few live listings and open requests so the marketplace, matching, and
    dashboards show a living app on first login (idempotent per demo farmer)."""
    admin = admin_client()
    farmer, buyer = ids["farmer"], ids["buyer"]

    # Clear this demo farmer's / buyer's prior demo rows so re-running is clean.
    admin.table("products").delete().eq("farmer_id", farmer).execute()
    admin.table("buyer_requests").delete().eq("buyer_id", buyer).execute()

    listings = [
        ("TOMATO", 500, 2200, "A", "Nashik"),
        ("ONION", 1200, 1500, "B", "Nashik"),
        ("WHEAT", 2000, 2800, "A", "Nashik"),
    ]
    for code, qty, price, grade, district in listings:
        admin.table("products").insert({
            "farmer_id": farmer, "crop_id": _crop_id(code),
            "quantity_kg": qty, "available_quantity_kg": qty,
            "asking_price_paise": price, "grade": grade, "grade_method": "HEURISTIC",
            "grade_confidence": 0.8, "status": "active", "district": district,
        }).execute()

    requests = [
        ("TOMATO", 300, 2400, "B", "Pune"),
        ("ONION", 800, 1600, "C", "Pune"),
    ]
    for code, qty, price, min_grade, district in requests:
        admin.table("buyer_requests").insert({
            "buyer_id": buyer, "crop_id": _crop_id(code),
            "quantity_kg": qty, "target_price_paise": price, "min_grade": min_grade,
            "delivery_district": district, "delivery_pincode": "411001", "status": "open",
        }).execute()

    return len(listings), len(requests)


def main() -> None:
    n = seed_crops()
    total = admin_client().table("crops").select("id").execute()
    print(f"crops upserted: {n}  (table now has {len(total.data)} rows)")

    ids = seed_demo_users()
    print(f"demo users ready: {', '.join(f'{k}={v[:8]}...' for k, v in ids.items())}")

    listings, requests = seed_market(ids)
    print(f"seeded {listings} listings + {requests} buyer requests")
    print(f"demo login password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
