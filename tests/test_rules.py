"""Unit tests for the deterministic checker and the data files.  Run: pytest -q"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from knowledge_base import load_schemes  # noqa: E402
from rules.criteria_check import check_scheme  # noqa: E402
from schemas import CitizenProfile  # noqa: E402

KB = load_schemes()


def verdict(sid, **profile):
    return check_scheme(KB[sid], CitizenProfile(**profile)).verdict


def test_kb_loads_and_ids_unique():
    raw = json.loads(config.SCHEMES_PATH.read_text(encoding="utf-8"))
    assert len(raw) == len(KB) >= 40


def test_persona_labels_reference_real_schemes():
    for p in json.loads(config.PERSONAS_PATH.read_text(encoding="utf-8")):
        for sid in p["expected_eligible"] + p.get("acceptable", []):
            assert sid in KB, (p["persona_id"], sid)


def test_age_bounds_are_inclusive():
    assert verdict("apy", age=40) == "eligible"
    assert verdict("apy", age=41) == "not_eligible"


def test_missing_value_gives_needs_info():
    assert verdict("apy") == "needs_info"


def test_tax_payer_excluded_from_pm_kisan():
    base = dict(occupation="farmer", owns_agricultural_land=True)
    assert verdict("pm_kisan", **base) == "eligible"
    assert verdict("pm_kisan", **base, is_income_tax_payer=True) == "not_eligible"


def test_state_scheme_needs_matching_state():
    p = dict(gender="female", education_level="class_9_10", annual_family_income=300000)
    assert verdict("gj_namo_lakshmi", state="Gujarat", **p) == "eligible"
    assert verdict("gj_namo_lakshmi", state="Bihar", **p) == "not_eligible"


def test_rural_urban_income_limits():
    p = dict(state="Gujarat", gender="female", marital_status="widowed", age=45)
    assert verdict("gj_ganga_swaroopa", area="urban", annual_family_income=140000, **p) == "eligible"
    assert verdict("gj_ganga_swaroopa", area="rural", annual_family_income=140000, **p) == "not_eligible"


def test_any_of_groups():
    p = dict(gender="female", is_pregnant_or_lactating=True)
    assert verdict("jsy", state="Gujarat", is_bpl=True, **p) == "eligible"
    assert verdict("jsy", state="Bihar", is_bpl=False, social_category="general", **p) == "eligible"
    assert verdict("jsy", state="Gujarat", is_bpl=False, social_category="general", **p) == "not_eligible"


def test_child_criteria():
    assert verdict("ssy", children=[{"age": 4, "gender": "female"}]) == "eligible"
    assert verdict("ssy", children=[{"age": 4, "gender": "male"}]) == "not_eligible"


def test_list_lookup_is_never_auto_eligible():
    assert verdict("pmjay", is_bpl=True) == "needs_info"
