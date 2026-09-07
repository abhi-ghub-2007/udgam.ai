"""Chronos-2 zero-shot challenger (phase 13).

Run separately from backtest.py, on purpose. This module imports torch and
downloads pretrained weights; the backtest, the training script and the API
must all stay runnable on a machine that has none of that, so nothing here is
imported by any of them.

WHAT IS BEING COMPARED
----------------------
Exactly the same question, on exactly the same rows: given a district's price
history up to day t, what is the modal price at t+7? Chronos sees the raw
price series as context and forecasts 7 steps; the score is taken on the same
test-fold (series, date) pairs the tabular models were scored on, so the
numbers sit in one table honestly.

Chronos is given the price series alone -- it is a univariate foundation model
and cannot take the arrival/spread/market-count features the ridge model uses.
That is a real property of the comparison, not a handicap introduced here, and
it is stated in the report rather than hidden.

Zero-shot only. Fine-tuning was not attempted: 32 usable Maharashtra series
over ~10 months is far below what fine-tuning a pretrained TSFM needs to beat
its own zero-shot performance, and the master prompt's own conditions for
fine-tuning (sufficient series, demonstrated backtest gain, justified
deployment cost) are not met.
"""
from __future__ import annotations

import json
import os
import time
from datetime import timedelta

import numpy as np

from .backtest import ARTIFACTS, PANEL, metrics, split_dates
from .features import HORIZON_DAYS, build_matrix, load_panel

MODEL_ID = os.environ.get("UDGAM_CHRONOS_MODEL", "amazon/chronos-2")
# Context length in observations. ~13 weeks is plenty for a 7-day horizon and
# keeps CPU inference tractable across hundreds of test points.
CONTEXT = 96
# Cap the evaluation set: every point is a separate forward pass on CPU.
MAX_POINTS = int(os.environ.get("UDGAM_CHRONOS_MAX_POINTS", "400"))


def load_pipeline():
    from chronos import BaseChronosPipeline
    import torch
    return BaseChronosPipeline.from_pretrained(MODEL_ID, device_map="cpu",
                                               torch_dtype=torch.float32)


def main():
    series = load_panel(PANEL)
    _, y, meta = build_matrix(series, horizon=HORIZON_DAYS)
    y = np.asarray(y, float)
    train_end, valid_end = split_dates(meta)

    # The same test fold the tabular models were scored on.
    test_idx = [i for i, m in enumerate(meta) if m["date"] > valid_end]
    if MAX_POINTS and len(test_idx) > MAX_POINTS:
        # Evenly spaced subsample so every series and every part of the test
        # window stays represented -- not the first N, which would be one date
        # range, and not a random draw, which would not be reproducible.
        step = len(test_idx) / MAX_POINTS
        test_idx = [test_idx[int(i * step)] for i in range(MAX_POINTS)]

    by_series = {k: {r["date"]: r["modal_price"] for r in v} for k, v in series.items()}
    ordered = {k: sorted(v) for k, v in by_series.items()}

    print(f"loading {MODEL_ID} (downloads weights on first run)...")
    t0 = time.perf_counter()
    pipe = load_pipeline()
    load_secs = time.perf_counter() - t0
    print(f"loaded in {load_secs:.1f}s; scoring {len(test_idx)} test points on CPU")

    import torch

    contexts, targets, naive, scored_idx = [], [], [], []
    for i in test_idx:
        m = meta[i]
        key = (m["crop"], m["district"])
        dates = [d for d in ordered[key] if d <= m["date"]][-CONTEXT:]
        if len(dates) < 24:                       # too little context to be fair
            continue
        contexts.append(torch.tensor([by_series[key][d] for d in dates], dtype=torch.float32))
        targets.append(y[i])
        naive.append(m["price_now"])
        scored_idx.append(i)

    t0 = time.perf_counter()
    preds, lo_q, hi_q = [], [], []
    BATCH = 32
    for s in range(0, len(contexts), BATCH):
        chunk = contexts[s:s + BATCH]
        # Chronos-2 takes `inputs` positionally and returns one tensor PER
        # series (shape [prediction_length, n_quantiles]), not a stacked batch.
        quantiles, _mean = pipe.predict_quantiles(
            chunk, prediction_length=HORIZON_DAYS,
            quantile_levels=[0.1, 0.5, 0.9])
        for q in quantiles:
            # Each entry is [n_targets, prediction_length, n_quantiles]; these
            # series are univariate, so target 0, final step, is the 7-day
            # forecast and the three quantile columns are [0.1, 0.5, 0.9].
            step = q[0][HORIZON_DAYS - 1]
            lo_q.append(float(step[0]))
            preds.append(float(step[1]))    # median = point forecast
            hi_q.append(float(step[2]))
    infer_secs = time.perf_counter() - t0

    targets = np.asarray(targets, float)
    preds = np.asarray(preds, float)
    naive = np.asarray(naive, float)

    # Chronos returns quantiles, so its 80% interval can be scored the same way
    # the shipped model's calibrated band is -- coverage measured, not claimed.
    lo_arr, hi_arr = np.asarray(lo_q, float), np.asarray(hi_q, float)
    coverage = float(np.mean((targets >= lo_arr) & (targets <= hi_arr)))

    # Score the tabular models on EXACTLY these points. Comparing Chronos on a
    # 400-point subsample against ridge on all 1,285 test rows would be a
    # different question dressed as the same one.
    from .backtest import apply_log_features, fit_ridge, fold_masks, predict_ridge
    X_all, _, _ = build_matrix(series, horizon=HORIZON_DAYS)
    X_all = np.asarray(X_all, float)
    tr, _va, _te = fold_masks(meta, train_end, valid_end)
    same = np.asarray(scored_idx, int)

    ridge_model = fit_ridge(X_all[tr], y[tr])
    # ridge_log is the model that actually ships, so it is the one Chronos has
    # to beat for the deployment cost to be worth paying.
    Xl = apply_log_features(X_all)
    log_model = fit_ridge(Xl[tr], np.log(y[tr]))

    head_to_head = {
        "naive_last": metrics(targets, naive),
        "ridge_lags_level": metrics(targets, predict_ridge(ridge_model, X_all[same])),
        "ridge_log_SHIPPED": metrics(targets, np.exp(predict_ridge(log_model, Xl[same]))),
        "chronos2_zero_shot": metrics(targets, preds),
    }
    try:
        from lightgbm import LGBMRegressor
        gbm = LGBMRegressor(n_estimators=400, learning_rate=0.05, num_leaves=15,
                            min_child_samples=20, random_state=0, verbose=-1)
        gbm.fit(X_all[tr], y[tr])
        head_to_head["lightgbm"] = metrics(targets, gbm.predict(X_all[same]))
    except ImportError:
        pass

    result = {
        "model": MODEL_ID,
        "mode": "zero_shot",
        "context_length": CONTEXT,
        "horizon_days": HORIZON_DAYS,
        "n_scored": int(len(targets)),
        "test": metrics(targets, preds),
        "naive_on_same_points": metrics(targets, naive),
        "interval_80_measured_coverage": round(coverage, 4),
        "mean_interval_width": round(float(np.mean(hi_arr - lo_arr)), 1),
        "head_to_head_same_points": head_to_head,
        "load_seconds": round(load_secs, 1),
        "inference_seconds_total": round(infer_secs, 1),
        "inference_ms_per_point": round(1000 * infer_secs / max(1, len(preds)), 1),
        "univariate": True,
        "note": ("Chronos sees the price series only; the ridge/LightGBM models "
                 "additionally use arrival, spread and market-count features."),
    }
    os.makedirs(ARTIFACTS, exist_ok=True)
    with open(os.path.join(ARTIFACTS, "chronos_challenger.json"), "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
