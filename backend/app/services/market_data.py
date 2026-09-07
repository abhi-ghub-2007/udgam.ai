"""Market data spine — provenance, freshness, and the synthetic price generator.

SIH26132 makes market intelligence central, so every figure this module
produces carries where it came from and how much to trust it. Nothing here
touches the database: the router reads rows and asks this module what they
mean, and scripts/seed_demo.py asks it what to write. That split is what makes
the whole thing testable without Supabase.

HONESTY (docs/ASSUMPTIONS.md A-15, PRD honesty labels)
------------------------------------------------------
There is no Agmarknet feed and no trained forecasting model in this tree:
backend/app/ml/ is empty and USE_MOCK_INTEGRATIONS defaults to true. Every row
this module generates is therefore stamped method='SYNTHETIC' and
data_source='synthetic_v1' — never 'agmarknet', which is the column default and
would silently claim an integration that does not exist. When a real feed is
connected it writes its own rows with method='REAL'; freshness_of() already
grades those correctly, so nothing here needs rewriting for that day.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# The label written into prices.data_source / model_runs.data_source for every
# generated row. Greppable, and obviously not a real vendor name.
SYNTHETIC_SOURCE = "synthetic_v1"
SYNTHETIC_MODEL = "udgam-market-synth"
SYNTHETIC_VERSION = "1.0.0"

# Freshness tiers (master prompt §10). ESTIMATED and SYNTHETIC describe where a
# number came from; LIVE/RECENT/STALE describe how old an observation is.
FRESH_LIVE = "LIVE"
FRESH_RECENT = "RECENT"
FRESH_STALE = "STALE"
FRESH_ESTIMATED = "ESTIMATED"
FRESH_SYNTHETIC = "SYNTHETIC"

LIVE_MAX_HOURS = 24
RECENT_MAX_HOURS = 72

# Real district-headquarter coordinates for the Maharashtra markets the demo
# data covers. Public reference geography, not invented market data — it only
# ever drives distance, never a price.
MARKET_DISTRICTS: dict[str, tuple[float, float, str]] = {
    "Nashik":      (19.9975, 73.7898, "Maharashtra"),
    "Pune":        (18.5204, 73.8567, "Maharashtra"),
    "Mumbai":      (19.0760, 72.8777, "Maharashtra"),
    "Nagpur":      (21.1458, 79.0882, "Maharashtra"),
    "Kolhapur":    (16.7050, 74.2433, "Maharashtra"),
    "Aurangabad":  (19.8762, 75.3433, "Maharashtra"),
    "Solapur":     (17.6599, 75.9064, "Maharashtra"),
    "Ratnagiri":   (16.9902, 73.3120, "Maharashtra"),
}

# Indicative wholesale price floor per crop category, in paise per kg. These set
# the *shape* of the synthetic series only; they are not quoted anywhere as an
# observed market price.
_CATEGORY_BASE_PAISE: dict[str, int] = {
    "vegetable": 2_200,
    "fruit": 4_500,
    "grain": 2_400,
    "oilseed": 5_500,
    "fibre": 7_000,
    "spice": 9_000,
    "cash": 350,
}
_DEFAULT_BASE_PAISE = 2_500


@dataclass(frozen=True)
class PricePoint:
    """One generated day of market observation, all money in integer paise."""

    price_date: date
    modal_price_paise: int
    min_price_paise: int
    max_price_paise: int
    arrival_qty_tonnes: float


def _seed_for(crop_code: str, district: str) -> int:
    """Stable across processes and Python versions — hash() is salted per run,
    so a deliberate sum keeps regenerated data identical run to run."""
    return sum(ord(c) for c in f"{crop_code.upper()}|{district.lower()}")


def base_price_paise(category: str | None) -> int:
    return _CATEGORY_BASE_PAISE.get((category or "").lower(), _DEFAULT_BASE_PAISE)


def synthesize_series(
    crop_code: str,
    district: str,
    *,
    category: str | None = None,
    days: int = 90,
    end: date | None = None,
) -> list[PricePoint]:
    """A deterministic, plausible daily price series ending at `end`.

    Deterministic on (crop_code, district) so the same inputs always produce the
    same series: reseeding the demo does not silently move every number, and the
    tests can assert on real values.

    Shape = base × annual seasonality × district premium × a bounded random walk.
    Arrival volume moves against price, which is the one genuine market
    relationship worth encoding: gluts depress prices.
    """
    if days < 1:
        return []
    end = end or date.today()
    rng = random.Random(_seed_for(crop_code, district))
    base = base_price_paise(category)

    # Districts sit within ±12% of each other — enough to make comparison
    # meaningful, never so wide that one market always wins.
    district_factor = 1.0 + ((rng.random() - 0.5) * 0.24)

    out: list[PricePoint] = []
    walk = 1.0
    for i in range(days):
        day = end - timedelta(days=days - 1 - i)

        # Annual seasonality: harvest gluts and lean seasons.
        seasonal = 1.0 + 0.18 * math.sin((day.timetuple().tm_yday / 365.0) * 2 * math.pi)
        # Bounded mean-reverting walk; clamped so a long series cannot drift away.
        walk = max(0.82, min(1.18, walk + (rng.random() - 0.5) * 0.05))

        modal = int(round(base * seasonal * district_factor * walk))
        spread = max(50, int(modal * 0.09))
        low = modal - spread
        high = modal + spread

        # Volume inversely tracks price deviation from the base.
        deviation = modal / (base * district_factor)
        arrivals = round(max(0.4, 14.0 / max(0.55, deviation)) * (0.85 + rng.random() * 0.3), 3)

        out.append(PricePoint(day, modal, low, high, arrivals))
    return out


def synthesize_forecast(
    series: list[PricePoint], *, horizon_days: int
) -> tuple[int, int, int, float]:
    """Project `horizon_days` ahead from the tail of an observed series.

    Returns (modal_paise, confidence_low_paise, confidence_high_paise, confidence).
    Linear extrapolation of the last two weeks, damped — a short window is a weak
    signal and should not be projected at full strength. The confidence band
    widens with the horizon and the interval is deliberately wide, because a
    narrow band on a synthetic forecast would be the dishonest part.
    """
    if not series:
        return (0, 0, 0, 0.0)
    window = series[-14:]
    latest = window[-1].modal_price_paise
    if len(window) < 2:
        slope = 0.0
    else:
        slope = (window[-1].modal_price_paise - window[0].modal_price_paise) / (len(window) - 1)

    damping = 0.45
    projected = int(round(latest + slope * horizon_days * damping))
    projected = max(1, projected)

    # ±4% per day of horizon, floored at 6%, capped at 45%.
    band_pct = min(0.45, max(0.06, 0.04 * horizon_days))
    low = max(1, int(round(projected * (1 - band_pct))))
    high = int(round(projected * (1 + band_pct)))

    return (projected, low, high, confidence_for_horizon(horizon_days))


def confidence_for_horizon(horizon_days: int | None) -> float | None:
    """Confidence decays with the horizon, capped at 0.6.

    The `prices` table has no scalar confidence column — it stores the interval
    instead — so the API derives this on read rather than adding a migration for
    a value that is a pure function of the horizon. Shared with
    synthesize_forecast() so the stored band and the reported confidence can
    never drift apart.

    The 0.6 ceiling is deliberate: this projects synthetic history with no
    trained model behind it, and must never read as validated model output.
    """
    if horizon_days is None:
        return None
    return round(max(0.15, min(0.6, 0.6 - 0.03 * horizon_days)), 3)


def _as_moment(observed_at: datetime | date | str) -> datetime | None:
    """Coerce whatever the row carried into an aware datetime, or None.

    PostgREST returns `price_date` as '2026-09-05' and `created_at` as an ISO
    timestamp STRING, never as Python date/datetime objects. That went
    unnoticed for as long as every row in `prices` was method='SYNTHETIC',
    because freshness_of returns before touching the date in that case -- the
    arithmetic below was effectively dead code. The first REAL observations
    reached it and it raised
    `TypeError: combine() argument 1 must be datetime.date, not str`,
    500ing /api/market/compare.

    Returns None for anything unparseable so the caller can grade the row
    STALE rather than fail the request: an ungradeable timestamp is a reason
    to distrust a number, not to deny the farmer the whole page.
    """
    if isinstance(observed_at, datetime):
        return observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=timezone.utc)
    if isinstance(observed_at, date):
        return datetime.combine(observed_at, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(observed_at, str):
        text = observed_at.strip()
        if not text:
            return None
        # Python < 3.11 cannot parse a trailing 'Z'.
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.combine(date.fromisoformat(text[:10]),
                                          datetime.min.time())
            except ValueError:
                return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def freshness_of(
    observed_at: datetime | date | str | None,
    *,
    method: str | None,
    is_prediction: bool = False,
    now: datetime | None = None,
) -> str:
    """Grade one row for how much weight a reader should give it.

    Order matters. SYNTHETIC wins over everything: a generated row is generated
    no matter how recently it was written, and must never be able to present
    itself as LIVE. A forecast is ESTIMATED. Only genuine observations get
    graded on age.
    """
    if (method or "").upper() == FRESH_SYNTHETIC:
        return FRESH_SYNTHETIC
    if is_prediction:
        return FRESH_ESTIMATED
    if observed_at is None:
        return FRESH_STALE

    now = now or datetime.now(timezone.utc)
    moment = _as_moment(observed_at)
    if moment is None:
        return FRESH_STALE

    age_hours = (now - moment).total_seconds() / 3600.0
    if age_hours < LIVE_MAX_HOURS:
        return FRESH_LIVE
    if age_hours < RECENT_MAX_HOURS:
        return FRESH_RECENT
    return FRESH_STALE


def provenance(row: dict, *, now: datetime | None = None) -> dict:
    """The provenance block attached to every market figure the API returns.

    Deliberately uniform, so the UI can render one component everywhere and a
    reader always gets the same six answers about any number on the screen.
    """
    method = (row.get("method") or "").upper() or None
    is_prediction = bool(row.get("is_prediction"))
    observed = row.get("price_date") or row.get("created_at")

    # A stored scalar confidence wins; otherwise a prediction derives one from
    # its horizon. An observation has no confidence to report and says so.
    confidence = row.get("confidence")
    if confidence is None and is_prediction:
        confidence = confidence_for_horizon(row.get("horizon_days"))

    return {
        "source": row.get("data_source"),
        "updated_at": row.get("created_at"),
        "observed_for": row.get("price_date"),
        "freshness": freshness_of(observed, method=method, is_prediction=is_prediction, now=now),
        "method": method,
        "confidence": confidence,
        "is_synthetic": method == FRESH_SYNTHETIC,
        "is_prediction": is_prediction,
    }


def trend_of(series: list[dict], *, key: str = "modal_price_paise") -> dict:
    """Direction over the supplied window, as a labelled percentage.

    'steady' covers ±2%, so ordinary noise is not dressed up as a trend.
    """
    points = [r for r in series if r.get(key) is not None]
    if len(points) < 2:
        return {"direction": "unknown", "change_pct": None, "window_days": len(points)}

    first, last = points[0][key], points[-1][key]
    if not first:
        return {"direction": "unknown", "change_pct": None, "window_days": len(points)}

    change_pct = round(((last - first) / first) * 100, 2)
    if change_pct > 2:
        direction = "rising"
    elif change_pct < -2:
        direction = "falling"
    else:
        direction = "steady"
    return {"direction": direction, "change_pct": change_pct, "window_days": len(points)}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance. Mirrors services/route_optimizer.haversine so the
    two never disagree; kept local to avoid a dependency between services."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(r * 2 * math.asin(math.sqrt(a)), 1)


def district_distance_km(a: str | None, b: str | None) -> float | None:
    """None when either district is outside the reference set — an unknown
    distance is reported as unknown rather than guessed as zero."""
    if not a or not b:
        return None
    pa, pb = MARKET_DISTRICTS.get(a), MARKET_DISTRICTS.get(b)
    if not pa or not pb:
        return None
    return haversine_km(pa[0], pa[1], pb[0], pb[1])
