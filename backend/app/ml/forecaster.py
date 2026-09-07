"""Price forecast at inference time (phases 16-19, 25).

This is the only ML module the API imports. It loads a small JSON artifact
lazily on first use -- import time does no file I/O, so a missing or corrupt
artifact degrades the forecast endpoint rather than preventing the whole
service from starting. Nothing here trains, and nothing here touches the
database: the router hands in history rows it already read, exactly the way
market_data.py is fed.

The history rows are `prices` rows, so the feature builder shared with
training works unchanged -- there is no second definition of `price_lag_7`
that could drift away from the one the model was fitted on.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, timedelta

from .features import FEATURE_NAMES, HORIZON_DAYS, features_at

ARTIFACT_PATH = os.path.join(os.path.dirname(__file__), "artifacts", "price_model.json")

# Enough history to compute a 14-day lag and a 7-day rolling window with room
# for the gaps a mandi series always has. Below this the model is not asked to
# guess -- the caller is told why.
MIN_HISTORY_ROWS = 10

_artifact = None
_load_failed = False


def load_artifact(path=ARTIFACT_PATH):
    """Cached artifact load. Returns None when unavailable, never raises."""
    global _artifact, _load_failed
    if _artifact is not None:
        return _artifact
    if _load_failed:
        return None
    try:
        with open(path) as f:
            art = json.load(f)
        if art.get("features") != FEATURE_NAMES:
            # The shipped weights were fitted on a different feature order.
            # Serving them would silently mismatch coefficients to columns.
            _load_failed = True
            return None
        _artifact = art
        return art
    except (OSError, ValueError):
        _load_failed = True
        return None


def model_available():
    return load_artifact() is not None


def _predict(art, feats):
    """One dot product, with the SAME transforms training used.

    The log columns and log target are read from the artifact rather than
    hardcoded, so a future model fitted on rupee levels serves correctly
    through this same function without a code change -- and, more importantly,
    a mismatch between how the model was fitted and how it is served cannot
    arise from someone editing one file and not the other.
    """
    w, mu, sd = art["weights"], art["feature_mean"], art["feature_std"]
    log_cols = set(art.get("log_features") or ())
    total = w[-1]                                   # intercept
    for i, name in enumerate(FEATURE_NAMES):
        x = feats[name]
        if name in log_cols:
            x = math.log(max(x, 1.0))
        s = sd[i] or 1.0
        total += w[i] * ((x - mu[i]) / s)
    return math.exp(total) if art.get("log_target") else total


def _to_history(price_rows):
    """`prices` rows -> the row shape features_at expects. Paise -> rupees."""
    out = []
    for r in price_rows:
        modal = r.get("modal_price_paise")
        if modal is None:
            continue
        d = r.get("price_date")
        if isinstance(d, str):
            y, m, dd = (int(x) for x in d.split("-")[:3])
            d = date(y, m, dd)
        lo, hi = r.get("min_price_paise"), r.get("max_price_paise")
        out.append({
            "date": d,
            "modal_price": modal / 100.0,
            "price_min": lo / 100.0 if lo is not None else None,
            "price_max": hi / 100.0 if hi is not None else None,
            "market_count": int(r.get("market_count") or 1),
            "total_arrival_tonnes": float(r.get("arrival_qty_tonnes") or 0.0),
        })
    out.sort(key=lambda x: x["date"])
    return out


def _trend(now, predicted, band_half_width):
    """Only call a direction when the move clears the model's own noise floor.

    A 20 rupee move on a series whose band is +/-300 is not a rising market,
    it is rounding. Anything inside half the band is reported STABLE.
    """
    delta = predicted - now
    if abs(delta) < band_half_width * 0.5:
        return "STABLE"
    return "RISING" if delta > 0 else "FALLING"


def forecast_price(price_rows, *, crop=None, district=None, horizon_days=HORIZON_DAYS):
    """Forecast, or a stated reason there isn't one. Never raises, never guesses.

    Returns the phase-16 shape: point estimate, an interval whose coverage was
    measured on unseen data, a trend that respects the noise floor, and the
    provenance of both the data and the model.
    """
    art = load_artifact()
    unavailable = {
        "crop": crop, "district": district,
        "forecast_horizon_days": horizon_days,
        "predicted_price": None, "lower_bound": None, "upper_bound": None,
        "trend": None, "available": False,
    }
    if art is None:
        return {**unavailable, "reason": "model_unavailable",
                "message": "The price model is not loaded on this deployment."}

    if horizon_days != art["horizon_days"]:
        return {**unavailable, "reason": "unsupported_horizon",
                "message": (f"This model forecasts {art['horizon_days']} days ahead; "
                            f"{horizon_days} was requested.")}

    history = _to_history(price_rows)
    if len(history) < MIN_HISTORY_ROWS:
        return {**unavailable, "reason": "insufficient_history",
                "message": (f"Needs at least {MIN_HISTORY_ROWS} days of market "
                            f"history; this crop and district has {len(history)}.")}

    today = history[-1]
    feats = features_at(history, today)
    if feats is None:
        # features_at only refuses when the 7-day lag is missing, which means
        # the recent history is too gappy to anchor a 7-day forecast.
        return {**unavailable, "reason": "insufficient_history",
                "message": "The last week of this market's history has too many gaps."}

    predicted = _predict(art, feats)
    if not math.isfinite(predicted) or predicted <= 0:
        return {**unavailable, "reason": "unstable_prediction",
                "message": "The model produced an implausible value for this series."}

    iv = art["interval"]
    if iv["mode"] == "multiplicative":
        # Calibrated in log space, so the band is a factor: the same relative
        # uncertainty on a 400 rupee Spinach print and a 4,000 rupee Brinjal one.
        lower = predicted / iv["factor"]
        upper = predicted * iv["factor"]
        coverage = iv["measured_coverage"]
    else:
        half = iv.get("fixed_half_width", 0.0)
        lower, upper = predicted - half, predicted + half
        coverage = iv.get("measured_coverage", iv.get("measured_coverage_fixed"))
    half = (upper - lower) / 2

    now = today["modal_price"]
    stale_days = (date.today() - today["date"]).days
    return {
        "crop": crop, "district": district,
        "forecast_horizon_days": art["horizon_days"],
        "current_price": round(now, 2),
        "predicted_price": round(predicted, 2),
        "lower_bound": round(max(0.0, lower), 2),
        "upper_bound": round(upper, 2),
        "price_unit": "Rs./Quintal",
        "trend": _trend(now, predicted, half),
        "available": True,
        # Coverage is the share of unseen test residuals that fell inside this
        # band, not a confidence percentage invented for the UI.
        "interval_coverage": coverage,
        "model": art["model_name"],
        "model_version": art["model_version"],
        "data_status": art["training"]["data_status"],
        "data_source": art["training"]["data_source"],
        "trained_at": art["trained_at"],
        "training_period": {"start": art["training"]["train_start"],
                            "end": art["training"]["train_end"]},
        "latest_observation": today["date"].isoformat(),
        "data_age_days": stale_days,
        "history_days_used": len(history),
        "test_mae": art["metrics"]["test"]["MAE"],
        "baseline_mae": art["metrics"]["test_baseline_naive"]["MAE"],
        "improvement_vs_naive_pct": art["metrics"]["improvement_vs_naive_pct"],
    }


def model_info():
    """Registry view of the shipped model, for /forecast/summary and tests."""
    art = load_artifact()
    if art is None:
        return {"available": False, "reason": "model_unavailable"}
    return {
        "available": True,
        "model": art["model_name"], "model_version": art["model_version"],
        "algorithm": art["algorithm"], "trained_at": art["trained_at"],
        "horizon_days": art["horizon_days"], "features": art["features"],
        "target": art["target"], "training": art["training"],
        "metrics": art["metrics"], "interval": art["interval"],
    }
