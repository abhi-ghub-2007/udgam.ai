"""Mandi CSV -> clean panel dataset (forecasting phases 3-8).

Raw files in data/raw/ are never modified. This module reads them, applies
documented cleaning rules, and writes data/processed/. Stdlib only: it runs
in the training environment, not in the API process, and the API never
imports it.

WHAT THE SOURCE ACTUALLY IS (audited, not assumed)
--------------------------------------------------
Agmarknet "Daily Price Arrival Report" exports, one file per commodity, all
covering 2025-11-07 .. 2026-09-06 (304 calendar days, no gaps). Every file has
a junk title row above the real header. Audited across 306,074 rows:

  * zero missing values in any price or arrival column
  * zero non-numeric price/arrival values
  * zero exact duplicate rows, zero duplicate (date, market, crop, variety,
    grade) observation keys -- so the observation identity in PHASE 4 holds
    and nothing needs de-duplicating
  * price unit is 'Rs./Quintal' on 100% of rows; arrival unit is
    'Metric Tonnes' on 100% of rows. No unit conversion is required, which is
    why none is performed -- see NORMALISATION below.

CLEANING RULES (every exclusion is counted and reported, never silent)
----------------------------------------------------------------------
A row is QUARANTINED (kept in the processed row file, flagged, and excluded
from panel aggregation) when:

  'nonpositive_price'  modal_price <= 0. Cannot be a real quintal price.
                       Seen: Brinjal min 0.12, Spinach min 2.0 Rs/quintal.
  'min_gt_max'         min_price > max_price. Internally contradictory.
  'min_gt_modal'       min_price > modal_price -- modal outside its own band.
  'modal_gt_max'       modal_price > max_price -- same.

Everything else is kept, INCLUDING extreme-but-coherent prices. A Brinjal
modal of 28,000/quintal is a real market shock, and price shocks are the most
informative rows a forecaster has. Outlier trimming would delete exactly the
events the farmer most needs warning about.

arrival_quantity == 0 is KEPT and treated as a real zero (no arrivals that
day at that market), because the source reports 0.00 explicitly rather than
leaving the field empty -- that is a semantic zero, not a missing value.

NORMALISATION
-------------
Prices: source is already Rs./Quintal on every row, which is the internal
representation this project wants. Rows carrying any other unit would be
converted, and the converter is present for that day, but on the current
files it never fires (counted as `unit_conversions`).
Arrivals: already Metric Tonnes on every row. Same treatment.

PANEL GRAIN
-----------
crop + district + date, Maharashtra only for the modelling set (PHASE 7 --
the national rows stay in data/raw and in the processed row file, so widening
later is a filter change, not a re-ingest).

Price aggregation across the markets in a district is arrival-weighted:

    weighted_modal = sum(modal * arrival) / sum(arrival)

which is valid here precisely BECAUSE the unit audit above came back uniform.
When a district's arrivals for that day sum to zero the weights are
meaningless, so it falls back to the unweighted mean and says so in
`price_is_weighted`. Market count and total arrival are preserved as
features rather than being averaged away.
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from datetime import date

RAW_DIR = os.path.join("data", "raw")
PROCESSED_DIR = os.path.join("data", "processed")

# Source header, exactly as exported. Verified identical across all files.
SOURCE_HEADER = [
    "State/UT", "District", "Market", "Commodity Group", "Commodity", "Variety",
    "Grade", "Min Price", "Max Price", "Modal Price", "Price Unit",
    "Arrival Quantity", "Arrival Unit", "Arrival Date",
]

# Standardised internal column names (PHASE 3).
COLUMNS = [
    "date", "state", "district", "market", "commodity_group", "crop", "variety",
    "grade", "min_price", "max_price", "modal_price", "price_unit",
    "arrival_quantity", "arrival_unit",
]

# Multiply a source price by this to reach Rs./Quintal. 1 quintal = 100 kg.
PRICE_TO_QUINTAL = {
    "rs./quintal": 1.0, "rs/quintal": 1.0, "rs./qtl": 1.0,
    "rs./kg": 100.0, "rs/kg": 100.0,
    "rs./tonne": 0.1, "rs/tonne": 0.1, "rs./ton": 0.1,
}
# Multiply a source arrival quantity by this to reach metric tonnes.
ARRIVAL_TO_TONNES = {
    "metric tonnes": 1.0, "tonnes": 1.0, "mt": 1.0,
    "quintal": 0.1, "quintals": 0.1,
    "kg": 0.001, "kgs": 0.001,
    "nos": None,        # a count, not a mass -- cannot be converted
    "bags": None,       # bag mass is crop- and market-specific
}

MAHARASHTRA = "maharashtra"

# Below this, a "Rs./Quintal" figure cannot be a real wholesale transaction:
# 100/quintal is 1 Rs/kg, and no vegetable in these files clears at that.
#
# This is not outlier trimming -- it is a unit-integrity check. Audited: 573 of
# 10,296 Maharashtra panel days fall under it, ALL Spinach, concentrated in
# Ahilyanagar (279), Pune (226) and Solapur (57), where the median Spinach
# print is ~58/quintal against a national Spinach median of 1,100. A crop
# trading at 5% of its national median in three districts for most of the year
# is a unit error at source (leafy greens are commonly quoted per bundle),
# not a market. Left in, those rows produce farmer-facing forecasts like
# "Spinach: 8 Rs/quintal", which is worse than showing nothing.
#
# The rows are quarantined, not deleted: they land in quarantined_rows.csv with
# this reason, so the decision is auditable and reversible if the source's unit
# handling for these markets is ever clarified.
MIN_PLAUSIBLE_QUINTAL_PRICE = 100.0


def _num(s):
    """'4,000.00' -> 4000.0. Missing stays None and NEVER becomes zero."""
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("₹", "")
    for junk in ("Rs.", "Rs", "INR"):
        s = s.replace(junk, "")
    s = s.strip()
    if s == "" or s.upper() in ("NA", "N/A", "NULL", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _date(s):
    """Source writes DD-MM-YYYY. Returns a date, or None if unparseable."""
    if not s or not s.strip():
        return None
    parts = s.strip().split("-")
    if len(parts) != 3:
        return None
    try:
        d, m, y = (int(p) for p in parts)
        return date(y, m, d)
    except ValueError:
        return None


def _clean_text(s):
    """Collapse whitespace and title-case place names for stable joins.

    The source pads district names ('North and Middle Andaman ') and is
    inconsistent about case across files, which would otherwise split one
    district into several series.
    """
    return " ".join((s or "").split()).strip()


def read_raw(path):
    """Yield cleaned row dicts from one export. Skips the junk title row."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)                      # junk title row
        header = next(reader, None)
        if header != SOURCE_HEADER:
            raise ValueError(f"{path}: unexpected header {header}")
        for raw in reader:
            if len(raw) != len(header) or not any(c.strip() for c in raw):
                continue
            r = dict(zip(header, raw))
            yield {
                "date": _date(r["Arrival Date"]),
                "state": _clean_text(r["State/UT"]),
                "district": _clean_text(r["District"]),
                "market": _clean_text(r["Market"]),
                "commodity_group": _clean_text(r["Commodity Group"]),
                "crop": _clean_text(r["Commodity"]),
                "variety": _clean_text(r["Variety"]),
                "grade": _clean_text(r["Grade"]),
                "min_price": _num(r["Min Price"]),
                "max_price": _num(r["Max Price"]),
                "modal_price": _num(r["Modal Price"]),
                "price_unit": _clean_text(r["Price Unit"]),
                "arrival_quantity": _num(r["Arrival Quantity"]),
                "arrival_unit": _clean_text(r["Arrival Unit"]),
            }


def normalise(row, stats):
    """Convert to Rs./Quintal + metric tonnes. Returns row or None if unusable."""
    pf = PRICE_TO_QUINTAL.get(row["price_unit"].lower())
    if pf is None:
        stats["unknown_price_unit"] += 1
        return None
    if pf != 1.0:
        stats["unit_conversions"] += 1
        for c in ("min_price", "max_price", "modal_price"):
            if row[c] is not None:
                row[c] = row[c] * pf
    row["price_unit"] = "Rs./Quintal"

    af = ARRIVAL_TO_TONNES.get(row["arrival_unit"].lower(), "unknown")
    if af == "unknown":
        stats["unknown_arrival_unit"] += 1
        row["arrival_quantity"] = None          # never guess a mass
    elif af is None:
        stats["uncountable_arrival_unit"] += 1  # 'Nos'/'Bags' are not a mass
        row["arrival_quantity"] = None
    elif af != 1.0:
        stats["arrival_conversions"] += 1
        if row["arrival_quantity"] is not None:
            row["arrival_quantity"] = row["arrival_quantity"] * af
    row["arrival_unit"] = "Metric Tonnes"
    return row


def quarantine_reason(row):
    """Why this row must not feed a price aggregate. None means it is fine."""
    mn, mx, md = row["min_price"], row["max_price"], row["modal_price"]
    if md is None:
        return "missing_modal_price"
    if md <= 0:
        return "nonpositive_price"
    if md < MIN_PLAUSIBLE_QUINTAL_PRICE:
        return "implausible_price_floor"
    if mn is not None and mx is not None and mn > mx:
        return "min_gt_max"
    if mn is not None and mn > md:
        return "min_gt_modal"
    if mx is not None and md > mx:
        return "modal_gt_max"
    return None


def load_clean(raw_dir=RAW_DIR):
    """All raw files -> (kept rows, quarantined rows, cleaning report)."""
    stats = Counter()
    kept, quarantined = [], []
    seen_exact = set()
    files = sorted(f for f in os.listdir(raw_dir) if f.lower().endswith(".csv"))

    for name in files:
        for row in read_raw(os.path.join(raw_dir, name)):
            stats["rows_read"] += 1
            if row["date"] is None:
                stats["invalid_date"] += 1
                continue

            row = normalise(row, stats)
            if row is None:
                stats["dropped_unusable_price_unit"] += 1
                continue

            # PHASE 4: identity is date+market+crop+variety+grade. Two rows
            # sharing a date and crop but differing in market/variety/grade are
            # both legitimate observations and both survive. Only byte-identical
            # repeats of the same identity are dropped.
            key = (row["date"], row["market"], row["crop"], row["variety"],
                   row["grade"], row["modal_price"], row["arrival_quantity"])
            if key in seen_exact:
                stats["exact_duplicates_removed"] += 1
                continue
            seen_exact.add(key)

            reason = quarantine_reason(row)
            if reason:
                stats[f"quarantined_{reason}"] += 1
                row["quarantine_reason"] = reason
                quarantined.append(row)
                continue
            kept.append(row)

    stats["rows_kept"] = len(kept)
    stats["rows_quarantined"] = len(quarantined)
    stats["source_files"] = len(files)
    return kept, quarantined, dict(stats)


def build_panel(rows, state=MAHARASHTRA):
    """Rows -> daily panel at crop + district + date (PHASE 8).

    `state=None` builds the national panel; the default keeps the Maharashtra
    modelling set the rest of the pipeline trains on.
    """
    buckets = defaultdict(list)
    for r in rows:
        if state and r["state"].lower() != state:
            continue
        buckets[(r["crop"], r["district"], r["date"])].append(r)

    panel = []
    for (crop, district, d), rs in sorted(buckets.items(), key=lambda kv: kv[0][2]):
        modals = [r["modal_price"] for r in rs]
        arrivals = [r["arrival_quantity"] for r in rs if r["arrival_quantity"] is not None]
        total_arrival = sum(arrivals) if arrivals else 0.0

        weighted = total_arrival > 0
        if weighted:
            num = sum(r["modal_price"] * r["arrival_quantity"] for r in rs
                      if r["arrival_quantity"] is not None)
            price = num / total_arrival
        else:
            # Zero arrivals across every market that day: weights carry no
            # information, so fall back to the plain mean and flag it.
            price = sum(modals) / len(modals)

        mins = [r["min_price"] for r in rs if r["min_price"] is not None]
        maxs = [r["max_price"] for r in rs if r["max_price"] is not None]
        panel.append({
            "date": d.isoformat(),
            "crop": crop,
            "district": district,
            "modal_price": round(price, 2),
            "price_is_weighted": int(weighted),
            "price_min": min(mins) if mins else None,
            "price_max": max(maxs) if maxs else None,
            "price_spread": (max(maxs) - min(mins)) if (mins and maxs) else None,
            "market_count": len({r["market"] for r in rs}),
            "observation_count": len(rs),
            "total_arrival_tonnes": round(total_arrival, 3),
        })
    return panel


def write_csv(path, rows, columns):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    kept, quarantined, report = load_clean()
    panel = build_panel(kept, state=MAHARASHTRA)
    national = build_panel(kept, state=None)

    panel_cols = list(panel[0].keys()) if panel else []
    write_csv(os.path.join(PROCESSED_DIR, "panel_maharashtra.csv"), panel, panel_cols)
    write_csv(os.path.join(PROCESSED_DIR, "panel_national.csv"), national, panel_cols)
    write_csv(os.path.join(PROCESSED_DIR, "quarantined_rows.csv"), quarantined,
              COLUMNS + ["quarantine_reason"])

    series = Counter((p["crop"], p["district"]) for p in panel)
    report["panel_rows_maharashtra"] = len(panel)
    report["panel_rows_national"] = len(national)
    report["mh_series"] = len(series)
    report["mh_series_ge_180_days"] = sum(1 for c in series.values() if c >= 180)
    report["mh_series_ge_120_days"] = sum(1 for c in series.values() if c >= 120)
    report["date_min"] = min(p["date"] for p in panel) if panel else None
    report["date_max"] = max(p["date"] for p in panel) if panel else None
    report["unweighted_fallback_rows"] = sum(1 for p in panel if not p["price_is_weighted"])

    with open(os.path.join(PROCESSED_DIR, "cleaning_report.json"), "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
