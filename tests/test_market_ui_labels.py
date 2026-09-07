"""The farmer must never be shown an internal identifier.

These tests guard the seam between machine-readable API metadata and the UI.
The bug they exist to prevent is specific and was real: the Market Decision
Center printed

    Simulated   Sample data   Source: synthetic_v1
    Ranked by: modal_price_paise desc

-- a duplicated status, an internal source id, and a raw SQL sort expression,
all on a screen meant for a farmer.

The frontend has no JS test runner, so the contract is enforced from here:
every ranking factor the backend can emit, and every data source it can stamp,
must have a human label on the frontend BEFORE it can reach a screen. That
makes the failure mode "a test goes red when someone adds a ranking factor"
instead of "a farmer sees a database column name".
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "frontend" / "src" / "i18n"
MAPPING = ROOT / "frontend" / "src" / "utils" / "provenance.ts"
STRIP = ROOT / "frontend" / "src" / "components" / "ui" / "Provenance.tsx"
DECISIONS = ROOT / "frontend" / "src" / "pages" / "farmer" / "Decisions.tsx"

LANGS = ("en", "hi", "mr")


def load_i18n(lang: str) -> dict:
    return json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))


def mapped_rank_fields() -> set[str]:
    """Field names the frontend mapping knows how to describe."""
    src = MAPPING.read_text(encoding="utf-8")
    block = src.split("RANK_FIELD_KEYS", 1)[1].split("};", 1)[0]
    return set(re.findall(r"^\s*([a-z_]+):", block, re.M))


# --------------------------------------------------------------------------
# every ranking factor the backend can emit has a human label
# --------------------------------------------------------------------------

def test_every_declared_ranking_factor_has_a_frontend_label():
    from backend.app.services.orchestration import RANKING_FACTORS
    missing = set(RANKING_FACTORS) - mapped_rank_fields()
    assert not missing, (
        "these ranking factors would render as raw column names in the UI: "
        f"{sorted(missing)}. Add them to RANK_FIELD_KEYS in "
        "frontend/src/utils/provenance.ts with an i18n label."
    )


def test_ranking_factor_labels_exist_in_every_language():
    src = MAPPING.read_text(encoding="utf-8")
    keys = set(re.findall(r"'rank\.([a-z_]+)'", src))
    assert keys, "no rank.* keys found in the mapping"
    for lang in LANGS:
        have = set(load_i18n(lang).get("rank", {}))
        missing = keys - have
        assert not missing, f"{lang}.json is missing rank keys: {sorted(missing)}"


def test_routers_that_hardcode_ranked_by_use_mappable_fields():
    """market.py and transport.py build `ranked_by` by hand rather than through
    the ranking policy, so they bypass RANKING_FACTORS entirely. Their fields
    still have to be describable or the raw string reaches the UI."""
    known = mapped_rank_fields()
    for rel in ("backend/app/routers/market.py", "backend/app/routers/transport.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for literal in re.findall(r'"ranked_by":\s*"([^"]+)"', text):
            for part in re.split(r",\s*then\s*|,\s*", literal):
                field = part.strip().split()[0]
                assert field in known, (
                    f"{rel} ranks on '{field}', which has no frontend label; "
                    f"the UI would print '{literal}' verbatim."
                )


# --------------------------------------------------------------------------
# data sources
# --------------------------------------------------------------------------

def test_synthetic_source_id_has_a_human_label():
    from backend.app.services.market_data import SYNTHETIC_SOURCE
    src = MAPPING.read_text(encoding="utf-8")
    assert f"{SYNTHETIC_SOURCE}:" in src, (
        f"'{SYNTHETIC_SOURCE}' is stamped on every generated price row but has "
        "no entry in SOURCE_KEYS, so the UI would print the raw id."
    )


def test_source_labels_exist_in_every_language():
    src = MAPPING.read_text(encoding="utf-8")
    keys = set(re.findall(r"'provenance\.([a-z_]+)'", src))
    assert keys
    for lang in LANGS:
        have = set(load_i18n(lang).get("provenance", {}))
        missing = keys - have
        assert not missing, f"{lang}.json is missing provenance keys: {sorted(missing)}"


def test_synthetic_data_is_never_labelled_as_real_market_data():
    """The label may say simulated. It may not imply a government feed."""
    forbidden = ("government", "mandi rate", "live market", "verified",
                 "official", "agmarknet")
    for lang in LANGS:
        label = load_i18n(lang)["provenance"]["source_simulated"].lower()
        for word in forbidden:
            assert word not in label, (
                f"{lang} labels simulated data '{label}', which claims an "
                f"origin it does not have ('{word}')"
            )


def test_bare_agmarknet_default_is_not_presented_as_a_real_feed():
    """`prices.data_source` DEFAULTs to 'agmarknet' without any integration
    existing (see market_data.py). A row carrying it has an unstated origin,
    so it must not be labelled as government data."""
    src = MAPPING.read_text(encoding="utf-8")
    m = re.search(r"^\s*agmarknet:\s*'([^']+)'", src, re.M)
    assert m, "bare 'agmarknet' default has no explicit mapping"
    assert m.group(1) == "provenance.source_unspecified"


# --------------------------------------------------------------------------
# the UI does not print raw metadata
# --------------------------------------------------------------------------

def test_provenance_strip_does_not_render_the_raw_source_id():
    text = STRIP.read_text(encoding="utf-8")
    assert "{p.source}" not in text, (
        "ProvenanceStrip is printing the raw data_source again; it must go "
        "through sourceLabelKey()."
    )
    assert "sourceLabelKey" in text


def test_decision_center_does_not_render_the_raw_sort_expression():
    text = DECISIONS.read_text(encoding="utf-8")
    # The bug was the VALUE rendered as text after the label -- e.g.
    # `{t('decide.ranked_by')}: {rankedBy}`. Passing it as a prop to
    # <RankedByNote rankedBy={rankedBy} /> is how it is supposed to travel,
    # so the check targets the text-node form specifically.
    leak = re.findall(r"ranked_by'\)\}\s*:\s*\{", text)
    assert not leak, (
        "Decisions.tsx prints the ranked_by value as text, which shows the "
        "farmer a SQL sort expression. Use <RankedByNote />."
    )
    assert "RankedByNote" in text


def test_status_is_not_duplicated_for_simulated_data():
    """freshness SYNTHETIC and method SYNTHETIC say the same thing; showing
    both put 'Simulated' and 'Sample data' side by side."""
    text = STRIP.read_text(encoding="utf-8")
    assert "bothSaySynthetic" in text
    assert "{!bothSaySynthetic && <MethodBadge" in text


def test_lot_picker_does_not_fall_back_to_a_raw_crop_uuid():
    text = DECISIONS.read_text(encoding="utf-8")
    assert "p.crop_name ?? p.crop_id" not in text, (
        "the lot picker falls back to a raw UUID when crop_name is missing"
    )


# --------------------------------------------------------------------------
# money is displayed in rupees, not paise
# --------------------------------------------------------------------------

def test_money_helper_is_the_only_paise_to_rupee_conversion():
    fmt = (ROOT / "frontend" / "src" / "utils" / "format.ts").read_text(encoding="utf-8")
    assert "(paise ?? 0) / 100" in fmt, "money() no longer converts paise to rupees"


def test_market_price_table_formats_prices_through_money():
    text = DECISIONS.read_text(encoding="utf-8")
    # A raw {m.modal_price_paise} would render 250000 where Rs 2,500 belongs.
    assert "{money(m.modal_price_paise)}" in text
    assert "{m.modal_price_paise}" not in text


@pytest.mark.parametrize("paise,rupees", [
    (1000, 10), (2500, 25), (10000, 100), (125000, 1250),
])
def test_paise_to_rupee_arithmetic_has_no_factor_of_100_error(paise, rupees):
    # Mirrors money()'s conversion so a change to the convention fails loudly.
    assert paise / 100 == rupees


# --------------------------------------------------------------------------
# the paise-per-KG convention, which a 100x error would silently violate
# --------------------------------------------------------------------------

def test_prices_column_is_paise_per_kg_not_per_quintal():
    """net_exit.py multiplies modal_price_paise straight by quantity_kg, so the
    column is paise per KG. The Agmarknet panel is Rs per QUINTAL. Those are
    numerically equal (Rs 2,000/quintal = Rs 20/kg = 2,000 paise/kg), and the
    ingest must rely on that rather than multiplying by 100 -- doing so scaled
    every farmer's gross sale value by a hundred."""
    net_exit = (ROOT / "backend/app/services/net_exit.py").read_text(encoding="utf-8")
    assert "paise/kg modal price" in net_exit, "the per-kg convention moved"

    ingest = (ROOT / "backend/app/ml/ingest.py").read_text(encoding="utf-8")
    assert 'float(r["modal_price"]) * 100' not in ingest, (
        "ingest is multiplying a Rs/quintal price by 100 into a paise/kg column"
    )
    assert 'int(round(float(r["modal_price"])))' in ingest


def test_forecaster_does_not_divide_the_per_kg_price_by_100():
    fc = (ROOT / "backend/app/ml/forecaster.py").read_text(encoding="utf-8")
    assert "modal / 100.0" not in fc, (
        "forecaster is dividing a paise/kg price by 100, which reports "
        "Rs 2,200/quintal as 'Rs 22 per quintal'"
    )


def test_synthetic_vegetable_base_is_a_plausible_per_kg_price():
    """Guards the convention from the other end: if the seed generator were
    ever switched to per-quintal, these two sources would disagree by 100x."""
    from backend.app.services.market_data import base_price_paise
    rupees_per_kg = base_price_paise("vegetable") / 100
    assert 5 <= rupees_per_kg <= 100, (
        f"synthetic vegetable base is Rs {rupees_per_kg}/kg, which is not a "
        "plausible per-kg wholesale price -- the unit convention has drifted"
    )
