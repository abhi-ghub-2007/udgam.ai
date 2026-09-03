"""Seed reference + demo data (A-12: allowed to use the service-role key).

Idempotent: upserts on natural keys, so re-running never duplicates. Run with
the project venv:  .venv/Scripts/python.exe scripts/seed_demo.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.db.admin_client import admin_client  # noqa: E402
from backend.app.services import market_data as md  # noqa: E402

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
    """Return the auth user id for `email`, creating it only if absent.

    Idempotent. The profiles row shares its primary key with the auth user and
    carries the email, so that is the exact, cheap lookup and it is tried first.
    admin.auth.admin.list_users() is paginated — on a project with a few hundred
    users the demo account is not on page one, which is why the old
    create-then-scan-page-one fallback raised "already registered" on a re-run.
    """
    admin = admin_client()

    row = (admin.table("profiles").select("id").eq("email", email)
           .limit(1).execute().data)
    if row:
        user_id = row[0]["id"]
        # Keep the shared demo password working even if it was changed.
        admin.auth.admin.update_user_by_id(user_id, {"password": DEMO_PASSWORD})
        return user_id

    try:
        res = admin.auth.admin.create_user({
            "email": email, "password": DEMO_PASSWORD, "email_confirm": True,
        })
        return res.user.id
    except Exception:  # noqa: BLE001 - exists in auth but has no profile row yet
        for page in range(1, 26):
            batch = admin.auth.admin.list_users(page=page, per_page=200)
            users = batch if isinstance(batch, list) else getattr(batch, "users", [])
            if not users:
                break
            for u in users:
                if getattr(u, "email", None) == email:
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


# --- SIH26132 market data spine ----------------------------------------------
# Crops the Market Decision Center demonstrates against. Kept small on purpose:
# 8 districts x 90 days x every crop would be ~14k rows for no demo benefit.
MARKET_CROPS = ["TOMATO", "ONION", "POTATO", "WHEAT", "BANANA", "COTTON"]
MARKET_HISTORY_DAYS = 90
FORECAST_HORIZONS = (3, 7, 14)


def seed_market_prices() -> tuple[int, int]:
    """Generate the SYNTHETIC price spine.

    Every row is written with method='SYNTHETIC' and data_source='synthetic_v1',
    never 'agmarknet' (the column default), so nothing in this dataset can be
    mistaken for a real mandi observation. One model_runs row records the
    provenance of the whole generation pass.

    Idempotent: the pass deletes only its own synthetic rows before rewriting,
    so a future real-data feed writing method='REAL' rows is never touched.
    """
    admin = admin_client()

    run = admin.table("model_runs").insert({
        "model_name": md.SYNTHETIC_MODEL,
        "model_version": md.SYNTHETIC_VERSION,
        "method": "SYNTHETIC",
        "data_source": md.SYNTHETIC_SOURCE,
        "notes": ("Deterministic synthetic price + demand series for the SIH26132 "
                  "demo. No Agmarknet feed and no trained model exist in this tree; "
                  "these rows are generated and labelled SYNTHETIC end to end."),
    }).execute().data[0]
    run_id = run["id"]

    crops = admin.table("crops").select("id, code, category").in_("code", MARKET_CROPS).execute().data
    admin.table("prices").delete().eq("data_source", md.SYNTHETIC_SOURCE).execute()
    admin.table("demand_forecasts").delete().eq("method", "SYNTHETIC").execute()

    price_rows: list[dict] = []
    demand_rows: list[dict] = []

    for crop in crops:
        for district, (_lat, _lon, state) in md.MARKET_DISTRICTS.items():
            series = md.synthesize_series(
                crop["code"], district,
                category=crop.get("category"), days=MARKET_HISTORY_DAYS,
            )
            for pt in series:
                price_rows.append({
                    "crop_id": crop["id"], "district": district, "state": state,
                    "price_date": pt.price_date.isoformat(),
                    "modal_price_paise": pt.modal_price_paise,
                    "min_price_paise": pt.min_price_paise,
                    "max_price_paise": pt.max_price_paise,
                    "arrival_qty_tonnes": pt.arrival_qty_tonnes,
                    "is_prediction": False,
                    "method": "SYNTHETIC",
                    "data_source": md.SYNTHETIC_SOURCE,
                    "model_run_id": run_id,
                })

            last_day = series[-1].price_date
            for horizon in FORECAST_HORIZONS:
                modal, low, high, conf = md.synthesize_forecast(series, horizon_days=horizon)
                price_rows.append({
                    "crop_id": crop["id"], "district": district, "state": state,
                    "price_date": (last_day + timedelta(days=horizon)).isoformat(),
                    "modal_price_paise": modal,
                    "confidence_low_paise": low, "confidence_high_paise": high,
                    "is_prediction": True, "horizon_days": horizon,
                    "method": "SYNTHETIC",
                    "data_source": md.SYNTHETIC_SOURCE,
                    "model_run_id": run_id,
                })

            # Demand: this week's arrivals against the trailing 4-week mean.
            recent = [p.arrival_qty_tonnes for p in series[-7:]]
            baseline = [p.arrival_qty_tonnes for p in series[-28:]]
            predicted = round(sum(recent) / max(1, len(recent)), 3)
            base_avg = round(sum(baseline) / max(1, len(baseline)), 3)
            change = round(((predicted - base_avg) / base_avg) * 100, 2) if base_avg else 0.0
            week_start = last_day - timedelta(days=last_day.weekday())
            demand_rows.append({
                "crop_id": crop["id"], "district": district,
                "forecast_week_start": week_start.isoformat(),
                "predicted_qty_tonnes": predicted,
                "baseline_qty_tonnes": base_avg,
                "change_pct": change,
                "confidence": 0.4,
                "method": "SYNTHETIC",
                "model_run_id": run_id,
            })

    for i in range(0, len(price_rows), 500):
        admin.table("prices").insert(price_rows[i:i + 500]).execute()
    admin.table("demand_forecasts").upsert(
        demand_rows, on_conflict="crop_id,district,forecast_week_start"
    ).execute()

    admin.table("model_runs").update({"row_count": len(price_rows) + len(demand_rows)})         .eq("id", run_id).execute()
    return len(price_rows), len(demand_rows)


# --- SIH26132 logistics + storage economics ----------------------------------
# Without posted capacity the Net Exit Optimizer correctly refuses to cost a
# mandi sale, and without storage the Sale Window cannot price waiting. Both are
# real rows in the existing tables, posted by the demo transporter, not values
# invented at request time.
TRANSPORT_ROUTES = [
    # (origin, dest, paise/kg, paise/km, capacity_kg, discount_pct, type)
    ("Nashik", "Mumbai",     180,  900, 12000, 0,  "scheduled_route"),
    ("Nashik", "Pune",       150,  850, 12000, 0,  "scheduled_route"),
    ("Nashik", "Nashik",      60,  400,  8000, 0,  "on_demand"),
    ("Nashik", "Aurangabad", 165,  880, 10000, 15, "empty_leg"),
    ("Pune",   "Mumbai",     140,  820, 10000, 0,  "scheduled_route"),
    ("Nashik", "Nagpur",     320, 1100,  9000, 0,  "scheduled_route"),
]

STORAGE_SITES = [
    # (name, district, type, capacity_kg, paise/kg/day, temp_c)
    ("Nashik Cold Chain Unit",   "Nashik", "cold", 50000, 12, 4.0),
    ("Nashik Dry Godown",        "Nashik", "dry",  80000,  4, None),
    ("Pune Cold Store",          "Pune",   "cold", 40000, 14, 3.0),
    ("Aurangabad Dry Warehouse", "Aurangabad", "dry", 60000, 3, None),
]


DEMO_TRANSPORTER_EMAIL = next(
    u["email"] for u in DEMO_USERS if u["key"] == "transporter"
)


def seed_logistics_and_storage() -> tuple[int, int]:
    """Post transporter capacity and storage listings for the demo transporter.

    The account is resolved from DEMO_TRANSPORTER_EMAIL — the stable identifier
    this file already declares — never from list ordering or a caller-supplied
    id. Seeding against whichever transporter happened to sort first would
    attach demo inventory to a real account.

    Idempotent: clears only this account's own rows before rewriting, so
    re-running never duplicates and no other user's postings are touched.
    """
    admin = admin_client()
    owner = (admin.table("profiles")
             .select("id, role, email").eq("email", DEMO_TRANSPORTER_EMAIL)
             .limit(1).execute().data)
    if not owner:
        raise RuntimeError(
            f"{DEMO_TRANSPORTER_EMAIL} has no profile; run seed_demo_users() first."
        )
    if owner[0]["role"] != "transporter":
        raise RuntimeError(
            f"{DEMO_TRANSPORTER_EMAIL} is not a transporter; refusing to seed."
        )
    transporter = owner[0]["id"]

    # T-9: storage may only be created by a profile flagged as a provider.
    admin.table("profiles").update({"is_storage_provider": True})         .eq("id", transporter).execute()

    admin.table("transport_capacity").delete().eq("transporter_id", transporter).execute()
    admin.table("storage_listings").delete().eq("owner_id", transporter).execute()

    depart = datetime.now(timezone.utc) + timedelta(days=1)
    cap_rows = []
    for origin, dest, per_kg, per_km, cap, discount, ctype in TRANSPORT_ROUTES:
        o = md.MARKET_DISTRICTS.get(origin)
        d = md.MARKET_DISTRICTS.get(dest)
        cap_rows.append({
            "transporter_id": transporter,
            "capacity_type": ctype,
            "origin_district": origin, "dest_district": dest,
            "origin_lat": o[0] if o else None, "origin_lon": o[1] if o else None,
            "dest_lat": d[0] if d else None, "dest_lon": d[1] if d else None,
            "depart_at": depart.isoformat(),
            "total_capacity_kg": cap, "available_capacity_kg": cap,
            "price_paise_per_kg": per_kg, "price_paise_per_km": per_km,
            "discount_pct": discount, "status": "open",
            # transport_capacity.notes is the only provenance field this table
            # has; storage_listings has none, so its name carries the label.
            "notes": "DEMO/SYNTHETIC seed data - not a real posted route",
        })
    admin.table("transport_capacity").insert(cap_rows).execute()

    store_rows = [{
        "owner_id": transporter, "name": f"{name} (demo)", "district": district,
        "storage_type": stype, "capacity_kg": cap, "available_capacity_kg": cap,
        "price_paise_per_kg_day": rate, "temperature_c": temp, "status": "active",
    } for (name, district, stype, cap, rate, temp) in STORAGE_SITES]
    admin.table("storage_listings").insert(store_rows).execute()

    return len(cap_rows), len(store_rows)


def main() -> None:
    n = seed_crops()
    total = admin_client().table("crops").select("id").execute()
    print(f"crops upserted: {n}  (table now has {len(total.data)} rows)")

    ids = seed_demo_users()
    print(f"demo users ready: {', '.join(f'{k}={v[:8]}...' for k, v in ids.items())}")

    listings, requests = seed_market(ids)
    print(f"seeded {listings} listings + {requests} buyer requests")
    caps, stores = seed_logistics_and_storage()
    print(f"seeded {caps} transport capacity rows + {stores} storage listings")

    prices, demand = seed_market_prices()
    print(f"seeded {prices} SYNTHETIC price rows + {demand} demand forecasts")
    print(f"demo login password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
