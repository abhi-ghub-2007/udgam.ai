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

# Five of each role, so reliability can be COMPARED rather than just displayed
# (one transporter tells a judge nothing). The first of each keeps its original
# key and email because the landing-page role picker signs into exactly those.
#
# Districts are spread along real Maharashtra produce corridors so that route
# matching has something to match on, and coordinates are the district centres
# — good enough for the Haversine estimate, and not claimed to be a farm gate.
DEMO_USERS = [
    # --- farmers ---------------------------------------------------------
    {"key": "farmer", "email": "demo.farmer@udgam.test", "role": "farmer",
     "full_name": "Ramesh Patil", "district": "Nashik", "state": "Maharashtra",
     "phone": "9800000001", "lat": 19.9975, "lon": 73.7898, "land_acres": 3.5},
    {"key": "farmer2", "email": "demo.farmer2@udgam.test", "role": "farmer",
     "full_name": "Anita Shinde", "district": "Sangli", "state": "Maharashtra",
     "phone": "9800000011", "lat": 16.8524, "lon": 74.5815, "land_acres": 6.0},
    {"key": "farmer3", "email": "demo.farmer3@udgam.test", "role": "farmer",
     "full_name": "Devidas Jadhav", "district": "Jalgaon", "state": "Maharashtra",
     "phone": "9800000012", "lat": 21.0077, "lon": 75.5626, "land_acres": 2.0},
    {"key": "farmer4", "email": "demo.farmer4@udgam.test", "role": "farmer",
     "full_name": "Shalini More", "district": "Satara", "state": "Maharashtra",
     "phone": "9800000013", "lat": 17.6805, "lon": 74.0183, "land_acres": 9.5},
    {"key": "farmer5", "email": "demo.farmer5@udgam.test", "role": "farmer",
     "full_name": "Ibrahim Shaikh", "district": "Aurangabad", "state": "Maharashtra",
     "phone": "9800000014", "lat": 19.8762, "lon": 75.3433, "land_acres": 4.2},

    # --- buyers ----------------------------------------------------------
    {"key": "buyer", "email": "demo.buyer@udgam.test", "role": "buyer",
     "full_name": "Sunita Deshmukh", "district": "Pune", "state": "Maharashtra",
     "phone": "9800000002", "lat": 18.5204, "lon": 73.8567,
     "business": "Deshmukh Traders", "buyer_type": "bulk", "pincode": "411001"},
    {"key": "buyer2", "email": "demo.buyer2@udgam.test", "role": "buyer",
     "full_name": "Farhan Qureshi", "district": "Mumbai Suburban", "state": "Maharashtra",
     "phone": "9800000021", "lat": 19.0760, "lon": 72.8777,
     "business": "Crescent Fresh Foods", "buyer_type": "bulk", "pincode": "400070"},
    {"key": "buyer3", "email": "demo.buyer3@udgam.test", "role": "buyer",
     "full_name": "Meera Kulkarni", "district": "Thane", "state": "Maharashtra",
     "phone": "9800000022", "lat": 19.2183, "lon": 72.9781,
     "business": "Kulkarni Retail", "buyer_type": "individual", "pincode": "400601"},
    {"key": "buyer4", "email": "demo.buyer4@udgam.test", "role": "buyer",
     "full_name": "Sardar Gill", "district": "Nagpur", "state": "Maharashtra",
     "phone": "9800000023", "lat": 21.1458, "lon": 79.0882,
     "business": "Gill Agro Processing", "buyer_type": "bulk", "pincode": "440001"},
    {"key": "buyer5", "email": "demo.buyer5@udgam.test", "role": "buyer",
     "full_name": "Lakshmi Iyer", "district": "Kolhapur", "state": "Maharashtra",
     "phone": "9800000024", "lat": 16.7050, "lon": 74.2433,
     "business": "Iyer Exports", "buyer_type": "bulk", "pincode": "416001"},

    # --- transporters ----------------------------------------------------
    {"key": "transporter", "email": "demo.transporter@udgam.test", "role": "transporter",
     "full_name": "Vikram Rao", "district": "Kolhapur", "state": "Maharashtra",
     "phone": "9800000003", "lat": 16.7050, "lon": 74.2433,
     "vehicle": "Tata Ace", "reg": "MH12AB1234", "capacity_kg": 750,
     "serves": ["Kolhapur", "Sangli", "Pune"], "rate_per_km": 1800},
    {"key": "transporter2", "email": "demo.transporter2@udgam.test", "role": "transporter",
     "full_name": "Balu Gaikwad", "district": "Nashik", "state": "Maharashtra",
     "phone": "9800000031", "lat": 19.9975, "lon": 73.7898,
     "vehicle": "Eicher 14 ft", "reg": "MH15CD5678", "capacity_kg": 4000,
     "serves": ["Nashik", "Pune", "Mumbai Suburban"], "rate_per_km": 3200},
    {"key": "transporter3", "email": "demo.transporter3@udgam.test", "role": "transporter",
     "full_name": "Rehana Sayyed", "district": "Aurangabad", "state": "Maharashtra",
     "phone": "9800000032", "lat": 19.8762, "lon": 75.3433,
     "vehicle": "Mahindra Bolero pickup", "reg": "MH20EF9012", "capacity_kg": 1200,
     "serves": ["Aurangabad", "Jalgaon", "Nashik"], "rate_per_km": 2100},
    {"key": "transporter4", "email": "demo.transporter4@udgam.test", "role": "transporter",
     "full_name": "Joseph Fernandes", "district": "Thane", "state": "Maharashtra",
     "phone": "9800000033", "lat": 19.2183, "lon": 72.9781,
     "vehicle": "Ashok Leyland 19 ft (reefer)", "reg": "MH04GH3456", "capacity_kg": 7000,
     "serves": ["Thane", "Mumbai Suburban", "Pune", "Nashik"], "rate_per_km": 4500},
    {"key": "transporter5", "email": "demo.transporter5@udgam.test", "role": "transporter",
     "full_name": "Ganesh Pawar", "district": "Satara", "state": "Maharashtra",
     "phone": "9800000034", "lat": 17.6805, "lon": 74.0183,
     "vehicle": "Tata 407", "reg": "MH11IJ7890", "capacity_kg": 2500,
     "serves": ["Satara", "Kolhapur", "Pune"], "rate_per_km": 2600},
]

FARMER_KEYS = [u["key"] for u in DEMO_USERS if u["role"] == "farmer"]
BUYER_KEYS = [u["key"] for u in DEMO_USERS if u["role"] == "buyer"]
TRANSPORTER_KEYS = [u["key"] for u in DEMO_USERS if u["role"] == "transporter"]


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
        # avg_rating/rating_count are deliberately NOT set here: they are
        # recomputed from the feedback rows seed_reputation() writes, so the
        # number on screen is always the average of reviews that exist.
        admin.table("profiles").upsert({
            "id": uid, "role": u["role"], "full_name": u["full_name"],
            "email": u["email"], "phone": u["phone"],
            "district": u["district"], "state": u["state"], "preferred_language": "en",
            "lat": u.get("lat"), "lon": u.get("lon"), "pincode": u.get("pincode"),
        }).execute()
        if u["role"] == "farmer":
            admin.table("farmer_profiles").upsert(
                {"profile_id": uid, "onboarding_status": "active",
                 "land_area_acres": u.get("land_acres", 3.5)},
            ).execute()
        elif u["role"] == "buyer":
            admin.table("buyer_profiles").upsert(
                {"profile_id": uid, "buyer_type": u.get("buyer_type", "bulk"),
                 "business_name": u.get("business"),
                 "delivery_pincode": u.get("pincode")},
            ).execute()
        else:
            admin.table("transporter_profiles").upsert(
                {"profile_id": uid, "vehicle_type": u.get("vehicle"),
                 "capacity_kg": u.get("capacity_kg", 750),
                 "vehicle_reg_no": u.get("reg"),
                 "service_districts": u.get("serves", []),
                 "base_rate_paise_per_km": u.get("rate_per_km", 0)},
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


def seed_fleet(ids: dict[str, str]) -> int:
    """Post capacity for the other four transporters, along the districts each
    one actually declares it serves, so route matching has real variety.

    The first transporter is left to seed_logistics_and_storage(), which also
    gives it storage listings. Idempotent the same way: each account's own rows
    are cleared before rewriting, and no other account is touched.
    """
    admin = admin_client()
    depart = datetime.now(timezone.utc) + timedelta(days=1)
    written = 0

    for u in DEMO_USERS:
        if u["role"] != "transporter" or u["key"] == "transporter":
            continue
        tid = ids[u["key"]]
        admin.table("transport_capacity").delete().eq("transporter_id", tid).execute()

        serves = u.get("serves", [])
        cap_kg = float(u.get("capacity_kg", 1000))
        rate_km = int(u.get("rate_per_km", 2000))
        rows = []
        # One lane per consecutive pair of served districts, plus a local
        # on-demand lane, which is what a small operator realistically offers.
        lanes = [(serves[i], serves[i + 1]) for i in range(len(serves) - 1)]
        lanes.append((u["district"], u["district"]))
        for i, (origin, dest) in enumerate(lanes):
            o = md.MARKET_DISTRICTS.get(origin)
            d = md.MARKET_DISTRICTS.get(dest)
            rows.append({
                "transporter_id": tid,
                "capacity_type": "on_demand" if origin == dest else (
                    "empty_leg" if i % 3 == 2 else "scheduled_route"),
                "origin_district": origin, "dest_district": dest,
                "origin_lat": o[0] if o else u.get("lat"),
                "origin_lon": o[1] if o else u.get("lon"),
                "dest_lat": d[0] if d else None, "dest_lon": d[1] if d else None,
                "depart_at": depart.isoformat(),
                "total_capacity_kg": cap_kg, "available_capacity_kg": cap_kg,
                # Bigger vehicles cost more per km but less per kg — the shape
                # a real rate card has, so cost ranking has something to sort.
                "price_paise_per_kg": max(40, int(24000 / max(cap_kg, 1) * 10)),
                "price_paise_per_km": rate_km,
                "discount_pct": 12 if i % 3 == 2 else 0,
                "status": "open",
                "notes": "DEMO/SYNTHETIC seed data - not a real posted route",
            })
        if rows:
            admin.table("transport_capacity").insert(rows).execute()
            written += len(rows)
    return written


# (farmer_key, buyer_key, transporter_key, crop, kg, paise/kg, farmer*, buyer*,
#  transporter*, delivered_late) — the stars are the ratings each side leaves.
# Deliberately uneven: a demo where everyone scores 5.0 proves nothing, and the
# late deliveries are what make "on-time 8/9" a fact rather than a decoration.
DEMO_HISTORY = [
    ("farmer",  "buyer",  "transporter2", "TOMATO", 500, 2500, 5, 5, 5, False),
    ("farmer",  "buyer2", "transporter2", "ONION",  800, 1800, 5, 4, 5, False),
    ("farmer",  "buyer3", "transporter4", "TOMATO", 300, 2600, 4, 5, 5, False),
    ("farmer",  "buyer4", "transporter4", "POTATO", 900, 1500, 5, 5, 4, True),
    ("farmer2", "buyer",  "transporter5", "BANANA", 600, 1400, 5, 5, 5, False),
    ("farmer2", "buyer5", "transporter5", "TOMATO", 400, 2400, 4, 4, 4, True),
    ("farmer2", "buyer2", "transporter",  "ONION",  700, 1750, 5, 5, 5, False),
    ("farmer3", "buyer3", "transporter3", "COTTON", 350, 5200, 4, 5, 4, False),
    ("farmer3", "buyer4", "transporter3", "WHEAT",  950, 2200, 4, 3, 5, False),
    ("farmer4", "buyer5", "transporter4", "TOMATO", 800, 2450, 5, 5, 5, False),
    ("farmer4", "buyer",  "transporter2", "POTATO", 500, 1550, 5, 4, 4, False),
    ("farmer4", "buyer2", "transporter5", "ONION",  650, 1700, 5, 5, 5, False),
    ("farmer5", "buyer3", "transporter3", "WHEAT",  450, 2150, 4, 4, 3, True),
    ("farmer5", "buyer4", "transporter",  "BANANA", 550, 1350, 4, 5, 5, False),
    ("farmer5", "buyer5", "transporter4", "COTTON", 300, 5100, 3, 4, 5, False),
]

FEEDBACK_TAGS = {
    5: ["on_time", "as_described"],
    4: ["as_described"],
    3: ["late"],
}


def seed_reputation(ids: dict[str, str]) -> tuple[int, int]:
    """Give the demo cast a past: completed orders, their shipments, and the
    reviews those orders earned.

    Every rating shown in the UI is the average of feedback rows written here,
    and every "completed"/"on-time" count is derived from these orders — so the
    reliability panel is reporting demo transactions that genuinely exist,
    rather than numbers typed into profiles (§44). The rows are labelled
    DEMO/SYNTHETIC in the order note and the review comment.

    Idempotent: orders carry a deterministic order_no per history entry, so a
    re-run updates the same rows instead of growing a second history.
    """
    admin = admin_client()
    crop_ids = {code: _crop_id(code) for code in {h[3] for h in DEMO_HISTORY}}
    now = datetime.now(timezone.utc)
    orders_written = reviews_written = 0

    for i, (fk, bk, tk, crop, kg, per_kg, f_star, b_star, t_star, late) in enumerate(DEMO_HISTORY):
        farmer_id, buyer_id, trans_id = ids[fk], ids[bk], ids[tk]
        order_no = f"UDG-DEMO{i:03d}"
        placed = now - timedelta(days=60 - i * 3)
        delivered = placed + timedelta(days=3 if not late else 5)
        subtotal = kg * per_kg
        fee = int(subtotal * 0.02)

        existing = (admin.table("orders").select("id")
                    .eq("order_no", order_no).limit(1).execute().data)
        row = {
            "order_no": order_no, "buyer_id": buyer_id, "farmer_id": farmer_id,
            "status": "CLOSED", "logistics_arranged_by": "buyer",
            "subtotal_paise": subtotal, "platform_fee_paise": fee,
            "buyer_total_paise": subtotal + fee, "farmer_payout_paise": subtotal,
            "placed_at": placed.isoformat(), "accepted_at": placed.isoformat(),
            "delivered_at": delivered.isoformat(), "closed_at": delivered.isoformat(),
            "cancelled_reason": None,
        }
        if existing:
            order_id = existing[0]["id"]
            admin.table("orders").update(row).eq("id", order_id).execute()
        else:
            order_id = admin.table("orders").insert(row).execute().data[0]["id"]
        orders_written += 1

        # order_items.product_id is NOT NULL: a sold line refers to the listing
        # it came from. Tagged in the description so a re-run finds the same
        # listing instead of growing a new one each time.
        tag = f"[DEMO-HIST-{i:03d}]"
        found = (admin.table("products").select("id")
                 .eq("farmer_id", farmer_id).ilike("description", f"{tag}%")
                 .limit(1).execute().data)
        product_row = {
            "farmer_id": farmer_id, "crop_id": crop_ids[crop],
            "quantity_kg": kg, "available_quantity_kg": 0,
            "asking_price_paise": per_kg, "status": "sold",
            "district": next(u["district"] for u in DEMO_USERS if u["key"] == fk),
            "description": f"{tag} demo history listing, already sold",
        }
        if found:
            product_id = found[0]["id"]
            admin.table("products").update(product_row).eq("id", product_id).execute()
        else:
            product_id = admin.table("products").insert(product_row).execute().data[0]["id"]

        admin.table("order_items").delete().eq("order_id", order_id).execute()
        admin.table("order_items").insert({
            "order_id": order_id, "product_id": product_id, "farmer_id": farmer_id,
            "crop_id": crop_ids[crop], "quantity_kg": kg,
            "unit_price_paise": per_kg, "line_total_paise": subtotal,
        }).execute()

        # The shipment is what makes the transporter a participant on this
        # order, which is what authorises the review of them.
        admin.table("shipments").delete().eq("order_id", order_id).execute()
        admin.table("shipments").insert({
            "order_id": order_id, "transporter_id": trans_id, "status": "delivered",
            "cargo_kg": kg,
            "pickup_address": f"Farm gate (demo) - {fk}",
            "drop_address": f"Warehouse (demo) - {bk}",
            "picked_up_at": (placed + timedelta(days=1)).isoformat(),
            "delivered_at": delivered.isoformat(),
            "deliver_by": (placed + timedelta(days=4)).isoformat(),
            "earnings_paise": int(kg * 90),
        }).execute()

        # Reviews, one per direction, matching what feedback's unique key allows.
        for rater, ratee, ratee_role, stars, text in (
            (buyer_id, farmer_id, "farmer", f_star, "Produce matched the grade."),
            (farmer_id, buyer_id, "buyer", b_star, "Paid without chasing."),
            (buyer_id, trans_id, "transporter", t_star,
             "Late to the drop." if late else "Arrived in the window."),
        ):
            admin.table("feedback").upsert({
                "order_id": order_id, "rater_id": rater, "ratee_id": ratee,
                "ratee_role": ratee_role, "rating": stars,
                "tags": FEEDBACK_TAGS.get(stars, []),
                "comment": f"[DEMO] {text}",
                "created_at": (delivered + timedelta(hours=6)).isoformat(),
            }, on_conflict="order_id,rater_id,ratee_id").execute()
            reviews_written += 1

    recompute_all_ratings()
    return orders_written, reviews_written


def recompute_all_ratings() -> int:
    """Recalculate every demo profile's rating FROM its feedback rows.

    The aggregate is never authored directly; it is only ever a summary of
    reviews that exist, so the two can never disagree.
    """
    admin = admin_client()
    touched = 0
    for u in DEMO_USERS:
        prof = (admin.table("profiles").select("id")
                .eq("email", u["email"]).limit(1).execute().data)
        if not prof:
            continue
        uid = prof[0]["id"]
        rows = (admin.table("feedback").select("rating")
                .eq("ratee_id", uid).execute().data) or []
        count = len(rows)
        avg = round(sum(r["rating"] for r in rows) / count, 2) if count else 0
        admin.table("profiles").update(
            {"avg_rating": avg, "rating_count": count}).eq("id", uid).execute()
        touched += 1
    return touched


def main() -> None:
    n = seed_crops()
    total = admin_client().table("crops").select("id").execute()
    print(f"crops upserted: {n}  (table now has {len(total.data)} rows)")

    ids = seed_demo_users()
    print(f"demo users ready: {', '.join(f'{k}={v[:8]}...' for k, v in ids.items())}")

    listings, requests = seed_market(ids)
    print(f"seeded {listings} listings + {requests} buyer requests")
    caps, stores = seed_logistics_and_storage()
    fleet = seed_fleet(ids)
    print(f"seeded {caps + fleet} transport capacity rows "
          f"({fleet} across the other four transporters) + {stores} storage listings")

    hist, reviews = seed_reputation(ids)
    print(f"seeded {hist} completed demo orders + {reviews} reviews "
          f"(ratings recomputed from those reviews, never typed in)")

    prices, demand = seed_market_prices()
    print(f"seeded {prices} SYNTHETIC price rows + {demand} demand forecasts")
    print(f"demo login password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
