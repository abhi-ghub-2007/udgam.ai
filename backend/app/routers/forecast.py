"""forecast.py — 7-day price and demand forecasts (phases 16, 17, 20).

Read-only, like market.py, and additive in the same way: nothing that works
today calls these endpoints, so a failure here cannot take a dashboard down.

The model itself lives in backend/app/ml and is loaded lazily on first request
(backend/app/ml/forecaster.py). Import of this module does no file I/O and no
training, so a missing artifact degrades to `available: false` with a stated
reason instead of blocking startup.

Every response carries provenance -- model, version, training window, data
status, and how stale the underlying observation is -- because a forecast whose
origin the reader cannot see is not usable evidence for a farmer deciding
whether to sell.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..deps import CurrentUserDep
from ..errors import NotFound
from ..ml import demand as demand_model
from ..ml import forecaster
from .market import _crop_row

router = APIRouter(prefix="/api/forecast", tags=["forecast"])

# Enough to cover a 30-day rolling window plus the gaps a mandi series always
# has, without pulling a year of rows for one prediction.
_HISTORY_DAYS = 120


def _history(db, crop_id: str, district: str) -> list[dict]:
    """Observed rows only. A prediction must never be fed its own output."""
    res = (
        db.table("prices")
        .select("price_date, modal_price_paise, min_price_paise, max_price_paise,"
                " arrival_qty_tonnes, method, data_source, is_prediction")
        .eq("crop_id", crop_id).eq("district", district).eq("is_prediction", False)
        .order("price_date", desc=True).limit(_HISTORY_DAYS).execute()
    )
    return list(reversed(res.data or []))


def _observed_status(rows: list[dict]) -> str:
    """What the underlying observations actually are, not what we wish for.

    The model was trained on REAL Agmarknet history, but a deployment whose
    `prices` table still holds seeded synthetic rows would be forecasting from
    synthetic input. Saying so is the difference between provenance and
    decoration.
    """
    if not rows:
        return "UNAVAILABLE"
    methods = {r.get("method") for r in rows}
    if methods == {"REAL"}:
        return "REAL"
    if "REAL" in methods:
        return "MIXED"
    return "SYNTHETIC"


@router.get("/price")
async def price_forecast(
    user: CurrentUserDep,
    district: str,
    crop_id: str | None = None,
    crop_code: str | None = None,
    horizon: int = Query(7, ge=1, le=30),
):
    """7-day price forecast for one crop in one district.

    Returns a point estimate, an interval whose coverage was measured on data
    the model never saw, and a trend that is only called when the move clears
    the model's own noise floor. When there is not enough history -- or no
    model on this deployment -- the response says which, rather than guessing.
    """
    crop = _crop_row(user.db, crop_id, crop_code)
    rows = _history(user.db, crop["id"], district)
    result = forecaster.forecast_price(
        rows, crop=crop["name_en"], district=district, horizon_days=horizon)
    result["crop_id"] = crop["id"]
    result["crop_code"] = crop["code"]
    result["observed_data_status"] = _observed_status(rows)
    return result


@router.get("/demand")
async def demand_forecast(
    user: CurrentUserDep,
    district: str,
    crop_id: str | None = None,
    crop_code: str | None = None,
    horizon: int = Query(7, ge=1, le=30),
):
    """Demand outlook for one crop in one district.

    Honest by construction: the response says whether it is a real forecast or
    a SYNTHETIC demonstration, and reports the buyer-side row counts behind
    that decision. Mandi arrival volume appears only under its real name, as a
    supply-side context figure -- never relabelled as demand.
    """
    crop = _crop_row(user.db, crop_id, crop_code)
    prices = _history(user.db, crop["id"], district)

    orders = (
        user.db.table("orders")
        .select("id, created_at, status")
        .limit(1000).execute()
    ).data or []
    requests = (
        user.db.table("buyer_requests").select("id").limit(500).execute()
    ).data or []

    result = demand_model.forecast_demand(
        order_rows=orders, price_rows=prices, request_rows=requests,
        crop=crop["name_en"], district=district, horizon_days=horizon)
    result["crop_id"] = crop["id"]
    result["crop_code"] = crop["code"]
    return result


@router.get("/summary")
async def forecast_summary(
    user: CurrentUserDep,
    district: str,
    crop_id: str | None = None,
    crop_code: str | None = None,
):
    """Price and demand together, for the Market Decision Center card.

    One request rather than two so the card cannot render a price forecast and
    a demand signal drawn from different moments.
    """
    crop = _crop_row(user.db, crop_id, crop_code)
    rows = _history(user.db, crop["id"], district)

    price = forecaster.forecast_price(
        rows, crop=crop["name_en"], district=district)
    orders = (user.db.table("orders").select("id, created_at, status")
              .limit(1000).execute()).data or []
    dem = demand_model.forecast_demand(
        order_rows=orders, price_rows=rows,
        crop=crop["name_en"], district=district)

    return {
        "crop": {"id": crop["id"], "code": crop["code"], "name": crop["name_en"]},
        "district": district,
        "price": price,
        "demand": dem,
        "observed_data_status": _observed_status(rows),
        "history_days": len(rows),
    }


@router.get("/model")
async def model_metadata(user: CurrentUserDep):
    """The shipped model's registry entry: version, training window, metrics.

    Deliberately exposes the honest comparison -- test MAE alongside the naive
    baseline it has to beat -- so the claim in the UI can be checked rather
    than trusted.
    """
    return forecaster.model_info()
