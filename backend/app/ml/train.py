"""Fit the shipped price model and calibrate its interval (phases 15-18).

Training happens here, offline. The API never imports this module and never
retrains -- it loads the JSON artifact written below (see forecaster.py).

WHY THE ARTIFACT IS JSON
------------------------
Whatever wins the backtest has to be served on a 512MB free-tier instance
alongside FastAPI. A ridge model is thirteen coefficients plus two scaling
vectors, so the artifact is a few kilobytes of JSON and inference is one dot
product -- no pickle, no version-coupled binary, no new runtime dependency
beyond numpy, which the project already ships for the CV grader. If a GBM ever
wins by a margin that justifies it, this module gains a second writer; the
serving contract does not change.

THE INTERVAL IS MEASURED, NOT DECORATIVE
----------------------------------------
The band is not "+/- 10% because it looks about right". Residuals are computed
on the validation fold -- data the model never trained on -- and the interval
half-width is the empirical quantile of |residual| at the requested coverage.
`calibrated_coverage` in the artifact records the share of TEST residuals that
actually landed inside that band, so the number the API reports as coverage is
one that was measured on unseen data. If that figure comes back materially
below target, it is written down as-is rather than tuned until it flatters.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

import numpy as np

from .backtest import (ARTIFACTS, LOG_FEATURE_NAMES, PANEL, apply_log_features,
                       fit_ridge, fold_masks, metrics, predict_ridge,
                       split_dates, try_gbm)
from .features import FEATURE_NAMES, HORIZON_DAYS, build_matrix, load_panel

MODEL_NAME = "udgam-price-ridge"
MODEL_VERSION = "1.1.0"     # 1.0.0 fitted on rupee levels; 1.1.0 works in logs
TARGET_COVERAGE = 0.80
ARTIFACT_PATH = os.path.join(ARTIFACTS, "price_model.json")


def main(target_coverage=TARGET_COVERAGE):
    series = load_panel(PANEL)
    X, y, meta = build_matrix(series, horizon=HORIZON_DAYS)
    X, y = np.asarray(X, float), np.asarray(y, float)

    train_end, valid_end = split_dates(meta)
    tr, va, te = fold_masks(meta, train_end, valid_end)

    # Fit in log space: log target, log price-level features. See backtest.py
    # for why -- it is the only variant that beats naive on MAE, RMSE and
    # sMAPE simultaneously.
    Xl = apply_log_features(X)
    model = fit_ridge(Xl[tr], np.log(y[tr]))
    pred_va = np.exp(predict_ridge(model, Xl[va]))
    pred_te = np.exp(predict_ridge(model, Xl[te]))

    # The band is calibrated in log space too, so it comes back as a
    # MULTIPLICATIVE factor. That is the right shape for prices: a +/-300
    # rupee band is wide on Spinach and narrow on Brinjal, whereas "x1.18"
    # means the same thing on both.
    log_resid_va = np.abs(np.log(y[va]) - np.log(pred_va))
    log_half = float(np.quantile(log_resid_va, target_coverage))
    factor = float(np.exp(log_half))

    # Coverage verified on the test fold, which neither fitting nor calibration
    # has touched. This is the number the API is allowed to quote.
    lo_te, hi_te = pred_te / factor, pred_te * factor
    calibrated_coverage = float(np.mean((y[te] >= lo_te) & (y[te] <= hi_te)))

    # A fixed rupee band, kept only as the comparison that justifies the
    # multiplicative one.
    resid_va = np.abs(pred_va - y[va])
    half_width = float(np.quantile(resid_va, target_coverage))
    cov_fixed_rupees = float(np.mean(np.abs(pred_te - y[te]) <= half_width))

    baseline_te = metrics(y[te], np.array([m["price_now"] for m in meta])[te])
    model_te = metrics(y[te], pred_te)

    artifact = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "algorithm": "ridge_regression_closed_form_log_target",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "horizon_days": HORIZON_DAYS,
        "features": FEATURE_NAMES,
        "log_features": LOG_FEATURE_NAMES,
        "log_target": True,
        "target": f"log(modal_price) at t+{HORIZON_DAYS} days, Rs/quintal",
        "weights": model["w"].tolist(),
        "feature_mean": model["mu"].tolist(),
        "feature_std": model["sd"].tolist(),
        "interval": {
            "target_coverage": target_coverage,
            "mode": "multiplicative",
            "factor": round(factor, 4),
            "measured_coverage": round(calibrated_coverage, 4),
            "measured_coverage_fixed_rupees": round(cov_fixed_rupees, 4),
            "fixed_half_width": round(half_width, 2),
            "measured_on": "test fold, unseen by fitting and calibration",
        },
        "training": {
            "data_source": "agmarknet_daily_price_arrival_csv",
            "data_status": "REAL",
            "state": "Maharashtra",
            "crops": sorted({c for c, _ in series}),
            "series_count": len(series),
            "train_start": str(min(m["date"] for m in meta)),
            "train_end": str(train_end),
            "valid_end": str(valid_end),
            "test_end": str(max(m["date"] for m in meta)),
            "n_train": int(len(tr)), "n_valid": int(len(va)), "n_test": int(len(te)),
        },
        "metrics": {
            "validation": metrics(y[va], pred_va),
            "test": model_te,
            "test_baseline_naive": baseline_te,
            "improvement_vs_naive_pct": round(
                100 * (baseline_te["MAE"] - model_te["MAE"]) / baseline_te["MAE"], 2),
        },
    }

    os.makedirs(ARTIFACTS, exist_ok=True)
    with open(ARTIFACT_PATH, "w") as f:
        json.dump(artifact, f, indent=2)

    print(f"wrote {ARTIFACT_PATH}")
    print(f"  test MAE {model_te['MAE']} vs naive {baseline_te['MAE']} "
          f"({artifact['metrics']['improvement_vs_naive_pct']}%)")
    print(f"  interval x{factor:.3f} target={target_coverage} "
          f"measured={calibrated_coverage:.3f} "
          f"(fixed-rupee band would be {cov_fixed_rupees:.3f})")
    return artifact


if __name__ == "__main__":
    main()
