# Price & demand forecasting

Seven-day mandi price forecasting for the Market Decision Center, and the
honest position on demand.

Everything below is measured on the attached datasets. Where a number is not
measured, it says so.

---

## 1. Data sources

Agmarknet "Daily Price Arrival Report" CSV exports, one per commodity.

| file | crop | rows | states | Maharashtra rows |
|---|---|---:|---:|---:|
| `data/raw/cabbage_20251107_20260906.csv` | Cabbage | 122,245 | 29 | 7,813 |
| `data/raw/brinjal_20251107_20260906.csv` | Brinjal | 162,761 | 29 | 8,545 |
| `data/raw/spinach_20251107_20260906.csv` | Spinach | 21,068 | 16 | 4,703 |

**All three cover 2025-11-07 → 2026-09-06: 304 calendar days with no gaps.**
That is roughly ten months. It is not multiple years, and nothing in this
system claims seasonal knowledge beyond that window.

Two identical Spinach uploads were received (same MD5); the duplicate is
ignored. Tomato, Bitter Gourd, Potato and Green Chilli were named in the brief
but not supplied, so they are not modelled.

`data/raw/` and `data/processed/` are gitignored — 45 MB of source CSV does not
belong in application history.

## 2. Audit findings

Run `python -m backend.app.ml.data` to regenerate
`data/processed/cleaning_report.json`.

The source is unusually clean:

- zero missing values in any price or arrival column
- zero non-numeric price/arrival values
- zero invalid dates
- zero exact duplicate rows
- zero duplicate `(date, market, crop, variety, grade)` observation keys
- `Price Unit` is `Rs./Quintal` on 100% of rows
- `Arrival Unit` is `Metric Tonnes` on 100% of rows

Because the observation key is unique across all 306,074 rows, the duplicate
policy in the brief (same date + crop is legitimate when market/variety/grade
differ) never had to discard anything.

## 3. Cleaning

Each source file has a junk title row above the real header; it is skipped.
Dates are `DD-MM-YYYY`. Prices arrive comma-formatted (`"4,000.00"`).

Rows are **quarantined** — written to `data/processed/quarantined_rows.csv`
with a reason, never silently dropped:

| reason | rows | why |
|---|---:|---|
| `implausible_price_floor` | 1,990 | modal < ₹100/quintal (= ₹1/kg) |
| `min_gt_modal` | 5 | modal outside its own band |
| `min_gt_max` | 2 | internally contradictory |
| **total** | **1,997** | of 306,074 read (0.65%) |

### The price floor is a unit check, not outlier trimming

573 Maharashtra panel days had Spinach under ₹100/quintal, concentrated in
Ahilyanagar (279), Pune (226) and Solapur (57). Median Spinach print in those
districts was ~₹58/quintal against a **national Spinach median of ₹1,100**.
A crop trading at 5% of its national median in three districts for most of the
year is a unit error at source — leafy greens are commonly quoted per bundle —
not a market.

Left in, they produced farmer-facing forecasts like *"Spinach: ₹8/quintal"*.

Extreme-but-coherent prices are **kept**, including a ₹28,000/quintal Brinjal
print. Real price shocks are the most informative rows a forecaster has.

Missing values are never converted to zero. `arrival_quantity == 0` is treated
as a real zero because the source writes `0.00` explicitly rather than leaving
the field blank.

## 4. Panel construction

Grain: **crop + district + date**, Maharashtra (`panel_maharashtra.csv`,
9,858 rows, 48 series). The national panel (`panel_national.csv`, 143,380 rows)
is written too, so expanding beyond Maharashtra is a filter change rather than
a re-ingest.

District price is **arrival-weighted**:

```
weighted_modal = sum(modal x arrival) / sum(arrival)
```

This is valid *because* the unit audit came back uniform. When a district's
arrivals sum to zero the weights carry no information, so it falls back to the
unweighted mean and flags `price_is_weighted = 0`. On the current data that
fallback never fires.

Preserved as features rather than averaged away: `market_count`,
`observation_count`, `total_arrival_tonnes`, `price_min`, `price_max`,
`price_spread`.

## 5. Target and features

**Target:** `modal_price` at `t + 7 days`, in ₹/quintal. When that calendar day
has no observation the sample is dropped — interpolating the target would be
inventing the number the model is graded on.

**Features (13).** Deliberately few: ten months over 48 series does not support
a hundred features.

```
price_lag_1, price_lag_7, price_lag_14
roll_mean_7, roll_mean_14, roll_std_7
price_change_7
arrival_lag_1, arrival_roll_7
spread_ratio, market_count
dow, month
```

Lags are taken on the **calendar date**, not row position. A district may
report on 283 of 304 days, so a positional lag would silently mean "7
observations ago" — a vaguer and inconsistent quantity.

`week_of_year` and `quarter` were dropped: within a single 10-month window they
are near-duplicates of `month` with more levels to overfit.

**Leakage.** Features for a row at `t` come from `series[:i+1]`; the target
comes from `series[i+horizon]`. A future value cannot reach a feature even by
accident, and `test_feature_row_never_sees_a_future_price` pins it.

## 6. Validation

Chronological, split by **date** — never by row.

| fold | dates | samples |
|---|---|---:|
| train | … → 2026-06-04 | 5,053 |
| validation | → 2026-07-17 | 1,093 |
| test | 2026-07-18 → 2026-09-06 | 1,228 |

A training sample whose *target* date lands after `train_end` is excluded, so a
training row can never be labelled with a validation-period price.

## 7. Model comparison

Full test fold, n=1,228 (`python -m backend.app.ml.backtest`):

| model | MAE ₹/qtl | RMSE | sMAPE | notes |
|---|---:|---:|---:|---|
| naive (last value) | 380.39 | 580.86 | 20.13% | the number to beat |
| seasonal naive (lag-7) | 456.37 | 681.52 | 23.95% | weak weekly seasonality |
| moving average 7 | 370.53 | 547.49 | 19.91% | |
| ridge on levels | 351.44 | 518.37 | 19.08% | |
| ridge on ratio | 360.22 | 529.61 | 19.40% | rejected, see below |
| **ridge in log space** | **341.27** | **503.74** | **18.61%** | **shipped** |
| LightGBM | 403.21 | 568.11 | 21.91% | **worse than naive** |
| LightGBM on ratio | 398.18 | 566.90 | 21.43% | worse than naive |

Head-to-head against the pretrained foundation model, on an identical
400-point subsample of the same test fold
(`python -m backend.app.ml.chronos_challenger`):

| model | MAE | RMSE | sMAPE |
|---|---:|---:|---:|
| naive | 370.11 | 555.55 | 19.80% |
| ridge on levels | 342.73 | 511.64 | 18.86% |
| **ridge in log space (shipped)** | **334.39** | **493.66** | **18.61%** |
| Chronos-2 zero-shot | 341.68 | 500.79 | 18.86% |
| LightGBM | 404.12 | 578.47 | 22.13% |

### What was rejected, and why

**LightGBM loses to the naive baseline.** Not hidden — investigated. It is not
an extrapolation failure: 0% of test targets exceed the training maximum. It is
**bias**: mean signed error on test was **+158 ₹/quintal** for LightGBM against
−26 for ridge and +61 for naive. Trees fit the training regime's conditional
mean, and the test window's mean price sits ~20% above the training window's
(₹1,433 → ₹1,725). Ridge tracks that shift linearly; trees do not. On the rare
high-price 4% slice LightGBM is genuinely better (MAE 883 vs ridge 1,186), but
the bulk dominates.

**Ratio target rejected.** Predicting `price_{t+7} / price_now` was tried to
normalise across crops, and made things worse: multiplying a noisy multiplier
back through `price_now` amplifies error on exactly the expensive series it was
meant to help.

**Chronos-2 evaluated properly and not selected.** It genuinely beats naive
(MAE 341.68 vs 370.11) and its 80% interval measured 79.5% coverage zero-shot,
which is impressive. It still loses to the shipped ridge on all three metrics,
most likely because it is univariate — it sees the price series only, while
ridge also sees arrival, spread and market count.

Cost, measured on this machine:

| | shipped ridge | Chronos-2 |
|---|---|---|
| artifact | 4 KB JSON | 456 MB weights |
| runtime deps | numpy (already shipped) | torch, transformers, accelerate |
| disk | ~0 | ~1.0 GB |
| RSS at inference | ~0 above FastAPI | **517 MB** |
| latency | <1 ms | ~26 ms/point CPU |

The backend runs on a Render **free instance with 512 MB total**. Chronos alone
exceeds the whole budget before FastAPI loads. But no tradeoff was actually
required: **the deployable model is also the more accurate one.**

**Fine-tuning Chronos was not attempted.** 31 usable series over ten months is
far below what fine-tuning a pretrained TSFM needs, and none of the brief's own
preconditions (demonstrated backtest gain, justified deployment cost) hold.

### Why log space

Mandi prices span roughly ₹100–12,000/quintal across these crops. Fitted on
rupee levels, a model minimises absolute error on the expensive series and
degrades the cheap ones — visible as the level model's sMAPE (19.08%) sitting
worse than its own log variant. In log space a 10% error on Spinach counts the
same as a 10% error on Brinjal, and the shipped model beats naive on MAE, RMSE
**and** sMAPE simultaneously. It is the only candidate that does.

## 8. Uncertainty

The band is **calibrated, not decorative**. Residuals are taken on the
validation fold, in log space, so the interval is a **multiplicative factor**
(currently ×1.393) — the same relative uncertainty on a ₹400 Spinach print and
a ₹4,000 Brinjal one.

Coverage is then measured on the **test fold**, which neither fitting nor
calibration touched:

- target coverage: **80%**
- measured coverage: **84.5%**

That measured figure is what the API returns and what the UI shows. It is
described as "the true price landed inside this range 84% of the time in
testing", never as a confidence percentage.

`trend` is only called RISING/FALLING when the move exceeds half the band
width; inside that it reports STABLE. A ₹20 move on a series with a ₹600 band
is rounding, not a market direction.

## 9. Demand — the honest position

Measured on the live database:

```
orders            19
buyer_requests     2
```

Nineteen orders is not a demand time series. It cannot support lags, a 7-day
target, or a backtest.

So **no trained demand model ships**, and specifically:

> **Mandi arrival quantity is NOT demand.** It is a supply signal. Labelling it
> demand would produce a confident number describing the opposite of what it
> claims to describe.

What ships instead: the interface, a runtime data-sufficiency gate
(`assess_demand_data`, thresholds 400 orders / 120 distinct days), and a
clearly-labelled SYNTHETIC demonstration signal derived from recent market
activity. It is stamped `method: SYNTHETIC`, `is_real: false`, carries a
disclaimer, and reports arrival under its real name `market_arrival_tonnes`.

When real order volume clears the threshold, `forecast_demand` switches to the
real branch automatically. Switching is a data threshold, not an architecture
change.

## 10. Data provenance labels

Reusing the existing project convention:

| label | means |
|---|---|
| `REAL` | observed Agmarknet history, or a model trained on it |
| `SYNTHETIC` | generated for demonstration; never a measurement |
| `ALGORITHMIC` | deterministic computation (net exit, sale window) |
| `HEURISTIC` | rule of thumb |

The price forecast is `REAL`. The demand signal is `SYNTHETIC`. Every forecast
response also carries `observed_data_status`, which reports whether the
underlying `prices` rows are REAL, SYNTHETIC or MIXED on **that** deployment —
a model trained on real history can still be fed seeded rows, and saying so is
the difference between provenance and decoration.

## 11. API

| endpoint | returns |
|---|---|
| `GET /api/forecast/price` | point estimate, calibrated interval, trend, provenance |
| `GET /api/forecast/demand` | demand outlook + data-sufficiency counts |
| `GET /api/forecast/summary` | both, in one request, for the Decision Center card |
| `GET /api/forecast/model` | model registry entry: version, training window, metrics |

Query: `?crop_id=<uuid>|crop_code=<code>&district=<name>&horizon=7`

Read-only and additive — nothing that works today calls them, so a failure here
cannot take a dashboard down. `available: false` with a stated `reason`
(`insufficient_history`, `model_unavailable`, `unsupported_horizon`,
`unstable_prediction`) is a normal response, not an error.

## 12. Frontend

`ForecastCard` renders in the farmer **Market Decision Center**
(`/farmer/decisions`), directly above the Risk-Adjusted Sale Window — it is the
evidence that decision rests on.

Shows today's price, the 7-day forecast, the range drawn to scale with today's
price marked on it, trend, demand level, the honesty badge and data age. Model
internals (version, training window, MAE vs baseline) live in a collapsed
`<details>` so a judge can audit the claim while a farmer is never asked to
read it. Full en/hi/mr parity.

## 13. Decision engine integration

No rewrite of `sale_window.py`, `net_exit.py` or `decisions.py` was needed.

Those already read forecasts from the `prices` table, keyed by `horizon_days`
and carrying `confidence_low_paise` / `confidence_high_paise`. The Risk-Adjusted
Sale Window already charges the forecast's own downside band as the price of
waiting. So integration is **writing real model output where synthetic rows
currently sit** — the decision engine upgrades automatically, and the risk
penalty starts being computed from a calibrated band instead of a generated one.

## 14. Retraining and refresh

```bash
# 1. clean + rebuild the panel from data/raw/
python -m backend.app.ml.data

# 2. compare every model on the chronological split
python -m backend.app.ml.backtest

# 3. fit + calibrate the shipped artifact
python -m backend.app.ml.train

# 4. optional: pretrained challenger (needs torch + chronos-forecasting)
python -m backend.app.ml.chronos_challenger

# 5. load observed history + forecasts into the database
python -m backend.app.ml.ingest            # dry run
python -m backend.app.ml.ingest --apply    # writes
```

Training and inference are separate. The API **never** retrains, never imports
torch, and loads the artifact lazily on first request — so import does no file
I/O and a missing artifact degrades the forecast endpoint rather than
preventing startup.

Mandi data is daily; a daily refresh is sufficient. Nothing here is real-time
and nothing claims to be.

## 15. Limitations

Stated plainly:

1. **~10 months of history.** Annual seasonality cannot be learned from a
   single incomplete cycle. No claim of multi-year capability.
2. **Three crops** (Cabbage, Brinjal, Spinach), not the seven named in the
   brief — the other four were not supplied.
3. **Cabbage is not yet ingestible**: the platform's `crops` table has no
   Cabbage row (it has Cauliflower). Adding it is a one-row insert.
4. **Maharashtra only** for modelling, by design. National panel is retained.
5. **The model beats naive by 10.3% MAE.** Real, measured, and modest —
   7-day mandi prices are close to a random walk. Anyone claiming much better
   on this data should be asked how.
6. **Typical error is ~₹341/quintal** against a test-period mean of ~₹1,725.
   That is roughly 20%. The interval is wide because the uncertainty is real.
7. **Demand is SYNTHETIC.** See §9.
8. **31 series clear 180 days.** Small. Per-crop or per-district models are not
   justified at this size; one pooled model is.
9. **No live Agmarknet feed.** Refresh means dropping new CSVs into
   `data/raw/` and re-running the pipeline.
