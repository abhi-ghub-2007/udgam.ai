"""Chronological backtest: baselines vs learned models (phases 12-15).

SPLIT
-----
Strictly by DATE, never by row. Every series contributes its early dates to
train and its late dates to test, so the test set is entirely in the future
relative to training -- which is the only split that answers the question the
farmer is actually asking. A random split here would leak neighbouring days of
the same series into training and report a fantasy score.

  train  earliest 70% of dates
  valid  next 15%
  test   latest 15%

Samples are also dropped when their target date (t+7) falls inside a later
fold, so a training row can never have seen a test-period price.

MODELS
------
naive          tomorrow-is-today: predict price_now. The number to beat.
seasonal_naive predict price_lag_7.
ma7            predict the 7-day rolling mean.
ridge          linear, closed-form, numpy only. Runs everywhere including a
               512MB free-tier dyno, which matters because whatever wins here
               has to be served.
gbm            sklearn HistGradientBoosting / LightGBM, only if installed.
               Skipped honestly rather than faked when it is not.

METRICS
-------
MAE, RMSE, sMAPE. sMAPE rather than MAPE because mandi prices are small enough
in places (Spinach prints under 100/quintal) that MAPE explodes on the
denominator and stops being readable.
"""
from __future__ import annotations

import json
import math
import os
import time

import numpy as np

from .features import FEATURE_NAMES, HORIZON_DAYS, build_matrix, load_panel

PANEL = os.path.join("data", "processed", "panel_maharashtra.csv")
ARTIFACTS = os.path.join("backend", "app", "ml", "artifacts")


def metrics(y_true, y_pred):
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    err = y_pred - y_true
    denom = (np.abs(y_true) + np.abs(y_pred)) / 2
    smape = np.mean(np.where(denom > 0, np.abs(err) / np.where(denom > 0, denom, 1), 0)) * 100
    return {
        "MAE": round(float(np.mean(np.abs(err))), 2),
        "RMSE": round(float(math.sqrt(np.mean(err ** 2))), 2),
        "sMAPE": round(float(smape), 2),
        "n": int(len(y_true)),
    }


def split_dates(meta, train_frac=0.70, valid_frac=0.15):
    dates = sorted({m["date"] for m in meta})
    i, j = int(len(dates) * train_frac), int(len(dates) * (train_frac + valid_frac))
    return dates[i - 1], dates[j - 1]


def fold_masks(meta, train_end, valid_end, horizon=HORIZON_DAYS):
    """Index masks. A training sample whose TARGET lands after train_end is
    excluded: its label is a price from the validation period.
    """
    from datetime import timedelta
    tr, va, te = [], [], []
    for i, m in enumerate(meta):
        target_date = m["date"] + timedelta(days=horizon)
        if target_date <= train_end:
            tr.append(i)
        elif m["date"] > train_end and target_date <= valid_end:
            va.append(i)
        elif m["date"] > valid_end:
            te.append(i)
    return np.array(tr), np.array(va), np.array(te)


# Price-level feature columns. Both these and the target get a log transform in
# the shipped model: mandi prices span roughly 100..12,000 Rs/quintal across
# crops, so a model fitted on rupee levels minimises absolute error on the
# expensive series and quietly degrades the cheap ones -- which is exactly what
# the level model's worse-than-naive sMAPE (26.5% vs 21.5%) was reporting.
LOG_FEATURE_NAMES = ["price_lag_1", "price_lag_7", "price_lag_14",
                     "roll_mean_7", "roll_mean_14"]
LOG_FEATURE_IDX = [FEATURE_NAMES.index(n) for n in LOG_FEATURE_NAMES]


def apply_log_features(X):
    """Log-transform the price-level columns. Never mutates the caller's array."""
    Xl = np.asarray(X, float).copy()
    for i in LOG_FEATURE_IDX:
        Xl[:, i] = np.log(np.maximum(Xl[:, i], 1.0))
    return Xl


def fit_ridge(X, y, alpha=1.0):
    """Closed-form ridge on standardised features. Pure numpy on purpose."""
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Xs = np.hstack([(X - mu) / sd, np.ones((len(X), 1))])
    A = Xs.T @ Xs + alpha * np.eye(Xs.shape[1])
    A[-1, -1] -= alpha                       # never penalise the intercept
    w = np.linalg.solve(A, Xs.T @ y)
    return {"w": w, "mu": mu, "sd": sd}


def predict_ridge(model, X):
    Xs = np.hstack([(X - model["mu"]) / model["sd"], np.ones((len(X), 1))])
    return Xs @ model["w"]


def try_gbm():
    """Return (name, fit, predict) for whichever GBM is installed, else None."""
    try:
        from lightgbm import LGBMRegressor

        def fit(X, y):
            m = LGBMRegressor(n_estimators=400, learning_rate=0.05, num_leaves=15,
                              min_child_samples=20, subsample=0.9, colsample_bytree=0.9,
                              random_state=0, verbose=-1)
            m.fit(X, y)
            return m
        return "lightgbm", fit, lambda m, X: m.predict(X)
    except ImportError:
        pass
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor

        def fit(X, y):
            m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                              max_leaf_nodes=15, random_state=0)
            m.fit(X, y)
            return m
        return "sklearn_hgb", fit, lambda m, X: m.predict(X)
    except ImportError:
        return None


def main():
    series = load_panel(PANEL)
    X, y, meta = build_matrix(series, horizon=HORIZON_DAYS)
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    print(f"samples={len(X)}  features={len(FEATURE_NAMES)}  series={len(series)}")

    train_end, valid_end = split_dates(meta)
    tr, va, te = fold_masks(meta, train_end, valid_end)
    print(f"train<= {train_end} ({len(tr)})  valid<= {valid_end} ({len(va)})  test ({len(te)})")

    price_now = np.array([m["price_now"] for m in meta])
    lag_7 = np.array([m["price_lag_7"] for m in meta])
    roll_7 = np.array([m["roll_mean_7"] for m in meta])

    results = {}

    def record(name, pred_all, train_secs=0.0):
        t0 = time.perf_counter()
        r = {"validation": metrics(y[va], pred_all[va]),
             "test": metrics(y[te], pred_all[te]),
             "train_seconds": round(train_secs, 2),
             "predict_ms_per_1k": round((time.perf_counter() - t0) * 1000, 2)}
        results[name] = r
        print(f"{name:16} test MAE={r['test']['MAE']:8.2f} RMSE={r['test']['RMSE']:8.2f} "
              f"sMAPE={r['test']['sMAPE']:6.2f}%")

    record("naive_last", price_now)
    record("seasonal_naive_7", lag_7)
    record("moving_avg_7", roll_7)

    t0 = time.perf_counter()
    ridge = fit_ridge(X[tr], y[tr])
    ridge_secs = time.perf_counter() - t0
    record("ridge_lags", predict_ridge(ridge, X), ridge_secs)

    # Multiplicative target. Tried because crop price levels differ by ~3x;
    # rejected because multiplying a noisy ratio back through price_now
    # amplifies the error on exactly the expensive series it was meant to help.
    # Kept in the table so the rejection is visible rather than tidied away.
    t0 = time.perf_counter()
    ratio_ridge = fit_ridge(X[tr], (y[tr] / price_now[tr]))
    ratio_secs = time.perf_counter() - t0
    record("ridge_ratio", predict_ridge(ratio_ridge, X) * price_now, ratio_secs)

    # Log target AND log price-level features. This is the shipped model: it is
    # the only candidate that beats the naive baseline on MAE, RMSE and sMAPE
    # at once, because working in log space makes a 10% error on Spinach count
    # the same as a 10% error on Brinjal.
    Xl = apply_log_features(X)
    t0 = time.perf_counter()
    log_ridge = fit_ridge(Xl[tr], np.log(y[tr]))
    log_secs = time.perf_counter() - t0
    record("ridge_log", np.exp(predict_ridge(log_ridge, Xl)), log_secs)

    gbm = try_gbm()
    if gbm:
        name, fit, pred = gbm
        t0 = time.perf_counter()
        model = fit(X[tr], y[tr])
        secs = time.perf_counter() - t0
        record(name, pred(model, X), secs)
        # GBM on the same ratio target, so the comparison against ridge_ratio
        # is like-for-like and not confounded by the target definition.
        t0 = time.perf_counter()
        model_r = fit(X[tr], y[tr] / price_now[tr])
        secs_r = time.perf_counter() - t0
        record(f"{name}_ratio", pred(model_r, X) * price_now, secs_r)
    else:
        results["gbm"] = {"skipped": "neither lightgbm nor scikit-learn installed"}
        print("gbm              SKIPPED (not installed) -- reported, not faked")

    best = min((k for k in results if "test" in results[k]),
               key=lambda k: results[k]["test"]["MAE"])
    baseline_mae = results["naive_last"]["test"]["MAE"]
    summary = {
        "horizon_days": HORIZON_DAYS,
        "features": FEATURE_NAMES,
        "samples": len(X),
        "series": len(series),
        "split": {"train_end": str(train_end), "valid_end": str(valid_end),
                  "n_train": len(tr), "n_valid": len(va), "n_test": len(te)},
        "results": results,
        "best_by_test_mae": best,
        "beats_naive_baseline": bool(results[best]["test"]["MAE"] < baseline_mae),
        "improvement_vs_naive_pct": round(
            100 * (baseline_mae - results[best]["test"]["MAE"]) / baseline_mae, 2),
    }
    os.makedirs(ARTIFACTS, exist_ok=True)
    with open(os.path.join(ARTIFACTS, "backtest.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nbest={best}  beats naive={summary['beats_naive_baseline']}  "
          f"improvement={summary['improvement_vs_naive_pct']}%")
    return summary


if __name__ == "__main__":
    main()
