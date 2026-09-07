"""Load the cleaned Maharashtra panel into `prices`, and write forecasts (phase 23).

This is what makes the rest of the system real rather than seeded: once
observed Agmarknet rows are in `prices` with method='REAL', the market pages,
the forecast endpoints, the Risk-Adjusted Sale Window and the Net Exit
Optimizer all read real history without a single line of them changing.

WHY IT WRITES THROUGH THE SERVICE ROLE
---------------------------------------
`prices` has a read policy for `authenticated` and no write policy at all
(db/SCHEMA.sql S13), so market data is deliberately not user-writable. This
script is the system, not a user, which is the same footing scripts/seed_demo.py
stands on (A-12).

IDEMPOTENCE
-----------
Observed rows are upserted on the (crop_id, district, price_date) unique index,
so re-running after a data refresh updates in place rather than duplicating.
Forecast rows are deleted and rewritten per crop+district+horizon, because a
stale forecast for the same horizon is not history worth keeping -- it is a
superseded guess.

SAFETY
------
`--dry-run` is the default. Nothing is written until `--apply` is passed, and
the summary prints exactly what would change first.
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from datetime import date, timedelta

from .features import HORIZON_DAYS, features_at, load_panel

PANEL = os.path.join("data", "processed", "panel_maharashtra.csv")
DATA_SOURCE = "agmarknet_csv_20251107_20260906"


def _crop_map(admin):
    """Panel crop names -> crops.id. Unmapped crops are reported, not invented."""
    rows = (admin.table("crops").select("id, code, name_en").execute()).data or []
    by_name = {r["name_en"].strip().lower(): r["id"] for r in rows}
    by_code = {r["code"].strip().upper(): r["id"] for r in rows}
    return by_name, by_code


def resolve_crop(name, by_name, by_code):
    return by_name.get(name.strip().lower()) or by_code.get(name.strip().upper())


def build_observed_rows(panel_path, by_name, by_code):
    """Panel CSV -> `prices` rows. Returns (rows, unmapped crop names)."""
    rows, unmapped = [], set()
    with open(panel_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            crop_id = resolve_crop(r["crop"], by_name, by_code)
            if not crop_id:
                unmapped.add(r["crop"])
                continue
            rows.append({
                "crop_id": crop_id,
                "district": r["district"],
                "state": "Maharashtra",
                "price_date": r["date"],
                # Paise, because that is the unit `prices` is declared in.
                "modal_price_paise": int(round(float(r["modal_price"]) * 100)),
                "min_price_paise": int(round(float(r["price_min"]) * 100)) if r["price_min"] else None,
                "max_price_paise": int(round(float(r["price_max"]) * 100)) if r["price_max"] else None,
                "arrival_qty_tonnes": float(r["total_arrival_tonnes"]),
                "is_prediction": False,
                "method": "REAL",
                "data_source": DATA_SOURCE,
            })
    return rows, unmapped


def build_forecast_rows(panel_path, by_name, by_code, model_run_id=None):
    """One forecast per series, from its latest observation, using the shipped model."""
    from . import forecaster
    series = load_panel(panel_path)
    out = []
    for (crop, district), rows in series.items():
        crop_id = resolve_crop(crop, by_name, by_code)
        if not crop_id or len(rows) < forecaster.MIN_HISTORY_ROWS:
            continue
        price_rows = [{
            "price_date": r["date"].isoformat(),
            "modal_price_paise": int(r["modal_price"] * 100),
            "min_price_paise": int(r["price_min"] * 100) if r["price_min"] else None,
            "max_price_paise": int(r["price_max"] * 100) if r["price_max"] else None,
            "arrival_qty_tonnes": r["total_arrival_tonnes"],
            "market_count": r["market_count"],
        } for r in rows]
        f = forecaster.forecast_price(price_rows, crop=crop, district=district)
        if not f.get("available"):
            continue
        out.append({
            "crop_id": crop_id,
            "district": district,
            "state": "Maharashtra",
            # The date the forecast is FOR, not the date it was made.
            "price_date": (rows[-1]["date"] + timedelta(days=HORIZON_DAYS)).isoformat(),
            "modal_price_paise": int(round(f["predicted_price"] * 100)),
            "confidence_low_paise": int(round(f["lower_bound"] * 100)),
            "confidence_high_paise": int(round(f["upper_bound"] * 100)),
            "is_prediction": True,
            "horizon_days": HORIZON_DAYS,
            "method": "REAL",
            "data_source": DATA_SOURCE,
            "model_run_id": model_run_id,
        })
    return out


def record_model_run(admin):
    """Register this training run so forecasts can be traced back to it."""
    from .forecaster import model_info
    info = model_info()
    if not info.get("available"):
        return None
    m = info["metrics"]
    res = admin.table("model_runs").insert({
        "model_name": info["model"],
        "model_version": info["model_version"],
        "method": "REAL",
        "metric_name": "MAE_rs_per_quintal_7d",
        "metric_value": m["test"]["MAE"],
        "baseline_metric_value": m["test_baseline_naive"]["MAE"],
        "data_source": DATA_SOURCE,
        "row_count": info["training"]["n_train"],
        "notes": (f"{info['algorithm']}; train {info['training']['train_start']}"
                  f"..{info['training']['train_end']}; "
                  f"{m['improvement_vs_naive_pct']}% better MAE than naive last-value"),
    }).execute()
    return (res.data or [{}])[0].get("id")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually write. Without it this is a dry run.")
    ap.add_argument("--panel", default=PANEL)
    args = ap.parse_args()

    from ..db.admin_client import admin_client
    admin = admin_client()
    by_name, by_code = _crop_map(admin)

    observed, unmapped = build_observed_rows(args.panel, by_name, by_code)
    print(f"observed rows ready : {len(observed)}")
    if unmapped:
        # Reported rather than silently skipped: an unmapped crop means the
        # panel has data the platform has no crop record for.
        print(f"  UNMAPPED crops (skipped): {sorted(unmapped)}")

    if not args.apply:
        forecasts = build_forecast_rows(args.panel, by_name, by_code)
        print(f"forecast rows ready : {len(forecasts)}")
        existing = (admin.table("prices").select("id", count="exact")
                    .limit(1).execute()).count
        print(f"\nDRY RUN. `prices` currently holds {existing} rows.")
        print("Re-run with --apply to write.")
        return

    run_id = record_model_run(admin)
    print(f"model_run: {run_id}")

    # uq_prices_observed is a PARTIAL unique index (`where is_prediction =
    # false`), which ON CONFLICT cannot target through PostgREST. Replacing
    # each ingested crop's observed rows outright is simpler than working
    # around that, and is idempotent in the way that actually matters: running
    # this twice leaves the same rows, not duplicates.
    crop_ids = sorted({r["crop_id"] for r in observed})
    for cid in crop_ids:
        (admin.table("prices").delete()
         .eq("crop_id", cid).eq("state", "Maharashtra")
         .eq("is_prediction", False).eq("data_source", DATA_SOURCE).execute())

    written = 0
    for i in range(0, len(observed), 500):
        chunk = observed[i:i + 500]
        admin.table("prices").insert(chunk).execute()
        written += len(chunk)
        print(f"  observed {written}/{len(observed)}", end="\r")
    print(f"\nobserved inserted   : {written}")

    forecasts = build_forecast_rows(args.panel, by_name, by_code, run_id)
    for f in forecasts:
        # Replace this series' forecast at this horizon rather than stacking a
        # new guess on top of a superseded one.
        (admin.table("prices").delete()
         .eq("crop_id", f["crop_id"]).eq("district", f["district"])
         .eq("is_prediction", True).eq("horizon_days", HORIZON_DAYS).execute())
    if forecasts:
        admin.table("prices").insert(forecasts).execute()
    print(f"forecasts written   : {len(forecasts)}")


if __name__ == "__main__":
    main()
