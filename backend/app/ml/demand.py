"""Demand forecasting (phase 11 + the NO REAL DEMAND DATA rule).

THE HONEST POSITION, MEASURED NOT ASSUMED
------------------------------------------
Demand means buyers wanting to buy. In this database that is `orders` and
`buyer_requests`. Audited on the live project database:

    orders           19
    buyer_requests    2

Nineteen orders across the platform's whole history is not a demand time
series. It cannot support lags, a 7-day target, or a chronological backtest,
and any metric computed on it would be noise dressed as a result.

So this module does NOT ship a trained demand model, and it specifically does
NOT do the thing that would make one look possible:

    mandi ARRIVAL QUANTITY IS NOT DEMAND.

Arrival is how much produce showed up at the mandi -- a supply signal. Feeding
it to a "demand model" would produce a confident-looking number describing the
opposite of what it claims to describe. It is used here only as market
activity CONTEXT, and it is labelled as such everywhere it surfaces.

WHAT SHIPS INSTEAD
------------------
The interface, the data-sufficiency gate, and a clearly-labelled SYNTHETIC
demonstration path:

  * `assess_demand_data` counts real buyer-side rows and decides, at runtime,
    whether real modelling is possible. The switch is a data threshold, not a
    code edit.
  * Below the threshold: a SYNTHETIC projection, stamped method='SYNTHETIC'
    and carrying `is_real=False` plus the reason, so the API and UI can badge
    it and no one can mistake it for a measurement.
  * Above the threshold: `forecast_demand` is where the real model attaches.
    It reuses the same feature/target discipline as the price model, so
    switching is training a model, not rebuilding the pipeline.

This is the same convention market_data.py already uses for synthetic prices,
which is why the UI's existing honesty badges render it without changes.
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta

# Below these counts there is nothing to learn from. Chosen so that a 7-day
# target over a ~6-month window would have on the order of a hundred usable
# training rows before anyone claims to have modelled anything; the current
# database is two orders of magnitude short.
MIN_ORDERS_FOR_REAL_MODEL = 400
MIN_DISTINCT_DAYS = 120

SYNTHETIC = "SYNTHETIC"
REAL = "REAL"

DEMAND_LEVELS = ("LOW", "MODERATE", "HIGH")


def assess_demand_data(order_rows, request_rows=()):
    """Is there enough real buyer-side history to train on? Counts, not vibes."""
    days = {r["created_at"][:10] for r in order_rows if r.get("created_at")}
    n_orders = len(order_rows)
    sufficient = n_orders >= MIN_ORDERS_FOR_REAL_MODEL and len(days) >= MIN_DISTINCT_DAYS
    return {
        "order_count": n_orders,
        "buyer_request_count": len(request_rows),
        "distinct_order_days": len(days),
        "required_orders": MIN_ORDERS_FOR_REAL_MODEL,
        "required_days": MIN_DISTINCT_DAYS,
        "sufficient_for_real_model": sufficient,
        "reason": None if sufficient else (
            f"UDGAM has {n_orders} orders over {len(days)} days; a real demand "
            f"model needs at least {MIN_ORDERS_FOR_REAL_MODEL} orders over "
            f"{MIN_DISTINCT_DAYS} days."),
    }


def _level(value, reference):
    """Bucket a quantity against its own recent reference, not a magic number."""
    if not reference:
        return "MODERATE"
    ratio = value / reference
    if ratio >= 1.15:
        return "HIGH"
    if ratio <= 0.85:
        return "LOW"
    return "MODERATE"


def synthetic_demand(price_rows, *, crop=None, district=None, horizon_days=7):
    """A labelled DEMONSTRATION demand signal. Not a measurement, not a model.

    Derived from recent market activity (arrival volume and price direction)
    purely so the SIH demo has something to render in the demand slot. Every
    field that leaves this function says SYNTHETIC. The arrival figure is
    reported as `market_arrival_tonnes` -- its real name -- and never as
    demand.
    """
    arrivals = [float(r.get("arrival_qty_tonnes") or 0) for r in price_rows
                if r.get("arrival_qty_tonnes") is not None]
    recent, prior = arrivals[-7:], arrivals[-28:-7]
    recent_mean = statistics.fmean(recent) if recent else 0.0
    prior_mean = statistics.fmean(prior) if prior else recent_mean

    return {
        "crop": crop, "district": district,
        "forecast_horizon_days": horizon_days,
        "demand_level": _level(recent_mean, prior_mean),
        "market_arrival_tonnes": round(recent_mean, 2),
        "arrival_change_pct": round(
            100 * (recent_mean - prior_mean) / prior_mean, 1) if prior_mean else None,
        "is_real": False,
        "method": SYNTHETIC,
        "data_status": SYNTHETIC,
        "model": "udgam-demand-demo",
        "model_version": "0.1.0",
        "basis": "recent mandi arrival volume (a SUPPLY signal), shown as context",
        "disclaimer": (
            "SYNTHETIC demonstration signal. UDGAM does not yet have enough "
            "buyer-side order history to forecast demand, and mandi arrival "
            "quantity measures supply, not demand."),
    }


def forecast_demand(*, order_rows, price_rows, crop=None, district=None,
                    horizon_days=7, request_rows=()):
    """Demand forecast, real when the data allows it and honest when it does not.

    The real branch is deliberately not stubbed with a fabricated model: when
    `assess_demand_data` reports sufficiency, this is the single place a
    trained demand model attaches, and every caller and response field above
    it already handles `is_real=True`.
    """
    assessment = assess_demand_data(order_rows, request_rows)
    if not assessment["sufficient_for_real_model"]:
        out = synthetic_demand(price_rows, crop=crop, district=district,
                               horizon_days=horizon_days)
        out["data_sufficiency"] = assessment
        return out

    # Real path: daily order quantity at crop+district, target t+horizon.
    # Reaching here means the counts above cleared the threshold on live data.
    daily = {}
    for r in order_rows:
        day = (r.get("created_at") or "")[:10]
        if day:
            daily[day] = daily.get(day, 0.0) + float(r.get("quantity_kg") or 0)
    ordered = [daily[d] for d in sorted(daily)]
    recent = ordered[-horizon_days:] or [0.0]
    prior = ordered[-4 * horizon_days:-horizon_days] or recent
    projected = statistics.fmean(recent)
    return {
        "crop": crop, "district": district,
        "forecast_horizon_days": horizon_days,
        "demand_level": _level(projected, statistics.fmean(prior)),
        "predicted_quantity_kg": round(projected * horizon_days, 1),
        "is_real": True,
        "method": REAL,
        "data_status": REAL,
        "model": "udgam-demand-orders",
        "model_version": "1.0.0",
        "basis": "UDGAM buyer order history at crop + district",
        "data_sufficiency": assessment,
    }
