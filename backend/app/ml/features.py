"""Feature + target construction for the 7-day price forecast (phases 9-10).

LEAKAGE IS THE ONLY THING THAT MATTERS HERE
-------------------------------------------
Every feature for a row dated t is computed from observations at t or earlier,
and the target is the price at t+7. `build_matrix` is written so that this is
structurally true rather than merely intended: features come from
`series[:i+1]` and the target from `series[i+horizon]`, so a future value
cannot reach a feature even by accident.

The panel is not a contiguous daily grid -- a district may report on 283 of
304 days. Lags are therefore taken on the CALENDAR date, not on row position:
`price_lag_7` is the price 7 days earlier, or missing if that day has no
observation. Positional lags would silently mean "7 observations ago", which
on a gappy series is a different and much vaguer quantity.

FEATURE SET (deliberately small)
--------------------------------
~10 months of history over 32 series does not support a hundred features.
Anything with heavy missingness or no plausible mechanism was left out
rather than added "just in case":

  price_lag_1/7/14      recent level; lag_7 is the seasonal-naive anchor
  roll_mean_7/14        smoothed level, robust to a single odd print
  roll_std_7            recent volatility -- also feeds the forecast band
  price_change_7        momentum, as a ratio so it is scale-free
  arrival_lag_1         supply signal at prediction time
  arrival_roll_7        smoothed supply
  spread_ratio          (max-min)/modal, market disagreement that day
  market_count          how many mandis backed this number
  dow, month            calendar. NOT week_of_year or quarter: with a single
                        10-month window those would be near-duplicates of
                        month with more levels to overfit.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import date, timedelta

HORIZON_DAYS = 7

FEATURE_NAMES = [
    "price_lag_1", "price_lag_7", "price_lag_14",
    "roll_mean_7", "roll_mean_14", "roll_std_7",
    "price_change_7",
    "arrival_lag_1", "arrival_roll_7",
    "spread_ratio", "market_count",
    "dow", "month",
]


def load_panel(path):
    """Processed panel CSV -> {(crop, district): [row, ...]} sorted by date."""
    series = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            y, m, d = (int(x) for x in r["date"].split("-"))
            series[(r["crop"], r["district"])].append({
                "date": date(y, m, d),
                "modal_price": float(r["modal_price"]),
                "price_min": float(r["price_min"]) if r["price_min"] else None,
                "price_max": float(r["price_max"]) if r["price_max"] else None,
                "market_count": int(r["market_count"]),
                "total_arrival_tonnes": float(r["total_arrival_tonnes"]),
            })
    for k in series:
        series[k].sort(key=lambda x: x["date"])
    return dict(series)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _std(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def features_at(history, today):
    """Features for the row `today`, using `history` = every row up to and
    including it. Returns None when the row is too early to have lags.

    `history` must never contain a row dated after `today`; callers slice it
    that way, and this function only ever looks backwards from the end.
    """
    by_date = {r["date"]: r for r in history}
    t = today["date"]

    def price_on(days_back):
        r = by_date.get(t - timedelta(days=days_back))
        return r["modal_price"] if r else None

    def window(days):
        lo = t - timedelta(days=days)
        return [r for r in history if lo < r["date"] <= t]

    lag_1, lag_7, lag_14 = price_on(1), price_on(7), price_on(14)
    # lag_7 anchors the seasonal-naive comparison, so a row without it is not
    # comparable against the baseline and is dropped rather than imputed.
    if lag_7 is None:
        return None

    w7, w14 = window(7), window(14)
    roll_mean_7 = _mean([r["modal_price"] for r in w7])
    roll_mean_14 = _mean([r["modal_price"] for r in w14])
    roll_std_7 = _std([r["modal_price"] for r in w7]) or 0.0
    arrival_roll_7 = _mean([r["total_arrival_tonnes"] for r in w7]) or 0.0

    prev = by_date.get(t - timedelta(days=1))
    arrival_lag_1 = prev["total_arrival_tonnes"] if prev else today["total_arrival_tonnes"]

    price = today["modal_price"]
    change_7 = (price / lag_7) if lag_7 else 1.0

    if today["price_min"] and today["price_max"] and price:
        spread_ratio = (today["price_max"] - today["price_min"]) / price
    else:
        spread_ratio = 0.0

    return {
        "price_lag_1": lag_1 if lag_1 is not None else price,
        "price_lag_7": lag_7,
        "price_lag_14": lag_14 if lag_14 is not None else lag_7,
        "roll_mean_7": roll_mean_7 if roll_mean_7 is not None else price,
        "roll_mean_14": roll_mean_14 if roll_mean_14 is not None else price,
        "roll_std_7": roll_std_7,
        "price_change_7": change_7,
        "arrival_lag_1": arrival_lag_1,
        "arrival_roll_7": arrival_roll_7,
        "spread_ratio": spread_ratio,
        "market_count": float(today["market_count"]),
        "dow": float(t.weekday()),
        "month": float(t.month),
    }


def build_matrix(series, horizon=HORIZON_DAYS, with_target=True):
    """All series -> (X rows, y, meta). One sample per (series, date) that has
    both usable features and, when training, a price exactly `horizon` days on.

    The target is the observed price at t+horizon. If that calendar day has no
    observation the sample is skipped -- interpolating a target would be
    inventing the very number the model is graded on.
    """
    X, y, meta = [], [], []
    for (crop, district), rows in series.items():
        by_date = {r["date"]: r for r in rows}
        for i, today in enumerate(rows):
            feats = features_at(rows[:i + 1], today)   # strictly past+present
            if feats is None:
                continue
            target = None
            if with_target:
                future = by_date.get(today["date"] + timedelta(days=horizon))
                if future is None:
                    continue
                target = future["modal_price"]
            X.append([feats[n] for n in FEATURE_NAMES])
            y.append(target)
            meta.append({
                "crop": crop, "district": district, "date": today["date"],
                "price_now": today["modal_price"],
                "price_lag_7": feats["price_lag_7"],
                "roll_mean_7": feats["roll_mean_7"],
                "roll_std_7": feats["roll_std_7"],
            })
    return X, y, meta
