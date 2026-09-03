"""market.py — read-only market intelligence (SIH26132 market data spine).

Every endpoint here is SELECT-only. The `prices` / `demand_forecasts` /
`model_runs` tables carry a read policy for `authenticated` and no write policy
at all, so Postgres itself refuses writes on the caller's JWT-bound client
(db/SCHEMA.sql §13). Rows are written solely by scripts/seed_demo.py under the
service-role key, which is the one place A-12 permits it.

Nothing existing depends on this router. It is additive: if every endpoint below
500s, the farmer/buyer/transporter dashboards render exactly as they did before,
because none of them call it. Later phases consume it deliberately.

Provenance is not optional. Each figure ships with source, timestamp, freshness,
method, confidence and a synthetic flag, so no reader can mistake a generated
series for an observed mandi price.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..deps import CurrentUserDep
from ..errors import NotFound
from ..services import market_data as md

router = APIRouter(prefix="/api/market", tags=["market"])

_MAX_WINDOW_DAYS = 180
_DEFAULT_WINDOW_DAYS = 30


def _crop_row(db, crop_id: str | None, crop_code: str | None) -> dict:
    """Resolve a crop by id or code. One of the two is required."""
    if not crop_id and not crop_code:
        raise NotFound("Specify a crop to look up.")
    q = db.table("crops").select("id, code, name_en, name_hi, name_mr, category,"
                                " default_shelf_life_days")
    q = q.eq("id", crop_id) if crop_id else q.eq("code", (crop_code or "").upper())
    res = q.limit(1).execute()
    if not res.data:
        raise NotFound("We do not have market data for that crop yet.")
    return res.data[0]


def _observations(db, crop_id: str, district: str, days: int) -> list[dict]:
    """Observed history, oldest first. Ordered desc in Postgres to ride
    idx_prices_lookup, then reversed in Python — cheaper than a second index."""
    res = (
        db.table("prices")
        .select("price_date, modal_price_paise, min_price_paise, max_price_paise,"
                " arrival_qty_tonnes, method, data_source, created_at, is_prediction")
        .eq("crop_id", crop_id).eq("district", district).eq("is_prediction", False)
        .order("price_date", desc=True).limit(days).execute()
    )
    return list(reversed(res.data or []))


def _forecasts(db, crop_id: str, district: str) -> list[dict]:
    """Every stored horizon, nearest first.

    Returned as a list rather than one row because the Risk-Adjusted Sale Window
    (Phase 3) compares sell-now against several horizons, and a caller that only
    wants the nearest can take the head.
    """
    res = (
        db.table("prices")
        .select("price_date, modal_price_paise, confidence_low_paise,"
                " confidence_high_paise, horizon_days, method, data_source,"
                " created_at, is_prediction")
        .eq("crop_id", crop_id).eq("district", district).eq("is_prediction", True)
        .order("horizon_days").execute()
    )
    return res.data or []


@router.get("/districts")
async def list_districts(user: CurrentUserDep):
    """Markets the platform holds price data for. Static reference geography —
    the frontend uses it to populate the compare-markets picker."""
    return {
        "districts": [
            {"district": name, "state": state, "lat": lat, "lon": lon}
            for name, (lat, lon, state) in sorted(md.MARKET_DISTRICTS.items())
        ]
    }


@router.get("/prices")
async def market_prices(
    user: CurrentUserDep,
    district: str,
    crop_id: str | None = None,
    crop_code: str | None = None,
    days: int = Query(_DEFAULT_WINDOW_DAYS, ge=1, le=_MAX_WINDOW_DAYS),
):
    """Price history + trend + latest projection for one crop in one market.

    An empty table is a legitimate answer, not an error: `series` comes back
    empty with `latest` null and availability 'unavailable', so the caller can
    render an honest empty state instead of a crash.
    """
    crop = _crop_row(user.db, crop_id, crop_code)
    series = _observations(user.db, crop["id"], district, days)
    forecasts = _forecasts(user.db, crop["id"], district)

    latest = series[-1] if series else None
    return {
        "crop": crop,
        "district": district,
        "availability": "ok" if series else "unavailable",
        "series": series,
        "latest": (
            {
                "modal_price_paise": latest["modal_price_paise"],
                "min_price_paise": latest["min_price_paise"],
                "max_price_paise": latest["max_price_paise"],
                "arrival_qty_tonnes": latest["arrival_qty_tonnes"],
                "provenance": md.provenance(latest),
            }
            if latest else None
        ),
        "trend": md.trend_of(series),
        "forecasts": [
            {
                "for_date": f["price_date"],
                "horizon_days": f["horizon_days"],
                "modal_price_paise": f["modal_price_paise"],
                "confidence_low_paise": f["confidence_low_paise"],
                "confidence_high_paise": f["confidence_high_paise"],
                "provenance": md.provenance(f),
            }
            for f in forecasts
        ],
    }


@router.get("/compare")
async def compare_markets(
    user: CurrentUserDep,
    crop_id: str | None = None,
    crop_code: str | None = None,
    from_district: str | None = None,
    days: int = Query(7, ge=2, le=_MAX_WINDOW_DAYS),
):
    """One crop across every market we hold data for.

    Ordered by price descending — an objective, disclosed criterion. No market
    is boosted, and distance is reported rather than folded into the ordering,
    because what makes a market worth travelling to is net realization, and that
    is the Net Exit Optimizer's job (Phase 2), not this endpoint's.
    """
    crop = _crop_row(user.db, crop_id, crop_code)
    origin = from_district or (user.db.table("profiles").select("district")
                               .eq("id", user.id).limit(1).execute().data or [{}])[0].get("district")

    markets = []
    for name in md.MARKET_DISTRICTS:
        series = _observations(user.db, crop["id"], name, days)
        if not series:
            continue
        latest = series[-1]
        markets.append({
            "district": name,
            "modal_price_paise": latest["modal_price_paise"],
            "arrival_qty_tonnes": latest["arrival_qty_tonnes"],
            "trend": md.trend_of(series),
            "distance_km": md.district_distance_km(origin, name),
            "provenance": md.provenance(latest),
        })

    markets.sort(key=lambda m: m["modal_price_paise"], reverse=True)
    return {
        "crop": crop,
        "from_district": origin,
        "availability": "ok" if markets else "unavailable",
        "ranked_by": "modal_price_paise desc",
        "markets": markets,
    }
