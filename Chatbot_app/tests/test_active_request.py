"""Tests for the redesigned interaction model:

* QUERY_PRESETS as the single source of truth for quick questions
* ActiveRequest creation from presets and from manual queries
* manual-query + advanced-filter merge rules
* graceful fallback plan construction
* no stale quick-question state (presets fully reset the request)
* no old/forbidden Gold table references in the app or src
"""
import re
from pathlib import Path

import pytest

from src.retrieval import (
    BROAD_TECH_LABEL,
    FALLBACK_BROADEN_TECH,
    FALLBACK_INFER_BUYERS,
    FALLBACK_LOWER_AMOUNT,
    FALLBACK_LOWEST_COMPETITION,
    FALLBACK_REMOVE_COUNTRY,
    QUERY_PRESETS,
    QUICK_QUESTIONS,
    ROUTE_AWARDED,
    ROUTE_BUYERS,
    ROUTE_OPPORTUNITIES,
    SOURCE_ADVANCED,
    SOURCE_MANUAL,
    SOURCE_PRESET,
    active_request_from_preset,
    build_active_request,
    build_fallback_plan,
    get_preset,
    infer_buyers_from_notices,
    new_active_request,
)

APP_DIR = Path(__file__).resolve().parent.parent


# --------------------------- presets: single source of truth ---------------------------
def test_all_seven_presets_present():
    expected = {
        "Top Microsoft-fit opportunities",
        "Cloud opportunities above 500k",
        "Cybersecurity opportunities",
        "Best opportunities in Spain",
        "High-value open tenders",
        "Which buyers should Microsoft prioritize?",
        "Awarded contracts with low competition",
    }
    assert expected == set(QUICK_QUESTIONS)


def test_each_preset_is_fully_specified():
    required = {"label", "query", "route", "technology", "country",
                "min_amount", "scope", "sort", "low_competition", "fallback_strategy"}
    for name, p in QUERY_PRESETS.items():
        assert required <= set(p.keys()), f"{name} missing keys"
        assert p["route"] in (ROUTE_OPPORTUNITIES, ROUTE_BUYERS, ROUTE_AWARDED)
        assert isinstance(p["fallback_strategy"], list)


@pytest.mark.parametrize("name,route", [
    ("Top Microsoft-fit opportunities", ROUTE_OPPORTUNITIES),
    ("Cloud opportunities above 500k", ROUTE_OPPORTUNITIES),
    ("Cybersecurity opportunities", ROUTE_OPPORTUNITIES),
    ("Best opportunities in Spain", ROUTE_OPPORTUNITIES),
    ("High-value open tenders", ROUTE_OPPORTUNITIES),
    ("Which buyers should Microsoft prioritize?", ROUTE_BUYERS),
    ("Awarded contracts with low competition", ROUTE_AWARDED),
])
def test_preset_routes(name, route):
    assert QUERY_PRESETS[name]["route"] == route


def test_preset_specifics():
    cloud = QUERY_PRESETS["Cloud opportunities above 500k"]
    assert cloud["technology"] == "Cloud & Azure" and cloud["min_amount"] == 500_000
    assert FALLBACK_LOWER_AMOUNT in cloud["fallback_strategy"]

    cyber = QUERY_PRESETS["Cybersecurity opportunities"]
    assert cyber["technology"] == "Cybersecurity"

    spain = QUERY_PRESETS["Best opportunities in Spain"]
    assert spain["country"] == "ESP" and FALLBACK_REMOVE_COUNTRY in spain["fallback_strategy"]

    awarded = QUERY_PRESETS["Awarded contracts with low competition"]
    assert awarded["scope"] == "Awarded contracts" and awarded["low_competition"] is True
    assert FALLBACK_LOWEST_COMPETITION in awarded["fallback_strategy"]

    buyers = QUERY_PRESETS["Which buyers should Microsoft prioritize?"]
    assert FALLBACK_INFER_BUYERS in buyers["fallback_strategy"]


def test_get_preset_unknown_returns_none():
    assert get_preset("nope") is None


# --------------------------- active request from preset ---------------------------
def test_active_request_from_preset_is_complete():
    req = active_request_from_preset("Cloud opportunities above 500k", top_n=8, fast_mode=False)
    assert req["source"] == SOURCE_PRESET
    assert req["route"] == ROUTE_OPPORTUNITIES
    assert req["technology"] == "Cloud & Azure"
    assert req["min_amount"] == 500_000
    assert req["scope"] == "Open tenders only"
    assert req["sort"] == "Microsoft Opportunity Score"
    assert req["top_n"] == 8 and req["fast_mode"] is False
    assert req["fallback_strategy"]  # cloud has a fallback


def test_preset_click_does_not_leak_previous_state():
    # Clicking Spain after Cloud must NOT keep Cloud's tech/amount.
    cloud = active_request_from_preset("Cloud opportunities above 500k")
    spain = active_request_from_preset("Best opportunities in Spain")
    assert cloud["technology"] == "Cloud & Azure"
    assert spain["technology"] == "Any technology"   # not Cloud
    assert spain["min_amount"] == 0                   # not 500k
    assert spain["country"] == "ESP"


def test_unknown_preset_falls_back_to_manual_request():
    req = active_request_from_preset("totally made up question")
    assert req["source"] in (SOURCE_MANUAL, SOURCE_ADVANCED)
    assert req["query"] == "totally made up question"


# --------------------------- manual query -> active request ---------------------------
def test_manual_query_infers_everything():
    req = build_active_request(query="Show cloud opportunities above 500k in Spain")
    assert req["technology"] == "Cloud & Azure"
    assert req["min_amount"] == 500_000
    assert req["country"] == "ESP"
    assert req["scope"] == "Open tenders only"
    assert req["route"] == ROUTE_OPPORTUNITIES


def test_manual_awarded_low_competition():
    req = build_active_request(query="Awarded contracts with low competition")
    assert req["route"] == ROUTE_AWARDED
    assert req["scope"] == "Awarded contracts"
    assert req["low_competition"] is True


def test_manual_buyers_route():
    req = build_active_request(query="Which buyers should Microsoft prioritize?")
    assert req["route"] == ROUTE_BUYERS


def test_advanced_filter_only_overrides_when_touched():
    # Untouched advanced filters must not override inferred intent.
    values = {"technology": "Cybersecurity", "country": None, "min_amount": 0,
              "scope": "Open tenders only", "sort": "Recommended"}
    untouched = {"technology": False}
    req = build_active_request(query="cloud opportunities", advanced_filters=values,
                              advanced_touched=untouched)
    assert req["technology"] == "Cloud & Azure"  # intent wins, advanced untouched

    touched = {"technology": True}
    req2 = build_active_request(query="cloud opportunities", advanced_filters=values,
                               advanced_touched=touched)
    assert req2["technology"] == "Cybersecurity"  # explicit advanced wins


def test_new_active_request_normalises_types():
    req = new_active_request(country="esp", min_amount="500000", top_n="5", low_competition=1)
    assert req["country"] == "ESP"
    assert req["min_amount"] == 500000.0
    assert req["top_n"] == 5
    assert req["low_competition"] is True


# --------------------------- fallback plans ---------------------------
def test_cloud_fallback_lowers_amount_then_broadens_tech():
    req = active_request_from_preset("Cloud opportunities above 500k")
    plan = build_fallback_plan(req)
    assert len(plan) == 2
    # step 1: amount dropped, tech still cloud
    assert plan[0]["request"]["min_amount"] == 0
    assert plan[0]["request"]["technology"] == "Cloud & Azure"
    # step 2 (cumulative): tech broadened to IT services
    assert plan[1]["request"]["technology"] == BROAD_TECH_LABEL
    assert plan[1]["request"]["min_amount"] == 0
    for step in plan:
        assert step["note"]


def test_spain_fallback_removes_country():
    req = active_request_from_preset("Best opportunities in Spain")
    plan = build_fallback_plan(req)
    assert plan and plan[-1]["request"]["country"] is None


def test_highvalue_fallback_lowers_amount():
    req = active_request_from_preset("High-value open tenders")
    plan = build_fallback_plan(req)
    assert plan and plan[0]["request"]["min_amount"] == 0


def test_top_fit_has_no_fallback_steps():
    req = active_request_from_preset("Top Microsoft-fit opportunities")
    assert build_fallback_plan(req) == []


def test_fallback_keeps_other_filters_intact():
    # Lowering amount must not wipe the country.
    req = new_active_request(country="FRA", min_amount=500_000, technology="Cloud & Azure",
                             fallback_strategy=[FALLBACK_LOWER_AMOUNT])
    plan = build_fallback_plan(req)
    assert plan[0]["request"]["country"] == "FRA"
    assert plan[0]["request"]["min_amount"] == 0


# --------------------------- infer buyers from notices (fallback) ---------------------------
def test_infer_buyers_from_notices():
    notices = [
        {"buyer_name": "Min Digital", "buyer_country": "ESP", "buyer_type": "ministry",
         "amount": 2_000_000, "cpv_division": "72", "num_tenders": 3},
        {"buyer_name": "Min Digital", "buyer_country": "ESP", "buyer_type": "ministry",
         "amount": 1_500_000, "cpv_division": "72", "num_tenders": 4},
        {"buyer_name": "Town Hall", "buyer_country": "ESP", "buyer_type": "local",
         "amount": 20_000, "cpv_division": "90", "num_tenders": 1},
    ]
    ranked = infer_buyers_from_notices(notices, top_n=5)
    assert ranked[0]["buyer_name"] == "Min Digital"
    assert ranked[0]["total_contracts"] == 2
    assert ranked[0]["top_cpv_division"] == "72"
    assert ranked[0]["buyer_attractiveness"] >= ranked[1]["buyer_attractiveness"]


# --------------------------- backend safety: no old tables ---------------------------
def _all_py_text(exclude=("gold_contract.py",)):
    text = []
    for p in (APP_DIR / "app.py",):
        text.append(p.read_text())
    for p in (APP_DIR / "src").glob("*.py"):
        if p.name in exclude:
            continue
        text.append(p.read_text())
    return "\n".join(text)


def test_no_forbidden_table_references():
    # gold_contract.py legitimately names these in its deny-list; everywhere
    # else must never reference them.
    blob = _all_py_text()
    assert "rag_documents" not in blob
    assert "ml_contract_features" not in blob


def test_primary_table_is_notices_unified():
    from src.config import load_config
    cfg = load_config()
    assert cfg.primary_table.endswith("notices_unified")


def test_no_silver_or_bronze_reads():
    blob = _all_py_text()
    # No direct reads from silver/bronze/raw schemas.
    assert "workspace.silver" not in blob
    assert "workspace.bronze" not in blob


def test_app_imports_cleanly():
    import importlib
    import src.retrieval as r
    importlib.reload(r)
    assert hasattr(r, "build_active_request")
    assert hasattr(r, "build_fallback_plan")
    assert hasattr(r, "active_request_from_preset")


def test_no_sidebar_anywhere():
    # The left sidebar must not exist: no st.sidebar usage in app or src.
    blob = _all_py_text(exclude=())
    assert "st.sidebar" not in blob
    assert ".sidebar." not in blob
