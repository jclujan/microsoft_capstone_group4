"""Tests for query-intent parsing, filter merging, sorting and quick questions."""
from datetime import date

import pytest

from src.retrieval import (
    QUICK_QUESTION_MAP,
    QUICK_QUESTIONS,
    ROUTE_AWARDED,
    ROUTE_BUYERS,
    SORT_MODES,
    TECH_AREAS,
    apply_sort,
    infer_query_intent,
    merge_sidebar_and_query_intent,
    quick_question_filters,
    rank_opportunities,
)


# ----------------------------- intent: technology -----------------------------
@pytest.mark.parametrize("q,expected", [
    ("cloud migration to azure", "Cloud & Azure"),
    ("infrastructure modernization", "Cloud & Azure"),
    ("cybersecurity and firewall protection", "Cybersecurity"),
    ("identity and security services", "Cybersecurity"),
    ("artificial intelligence and analytics", "AI, Data & Analytics"),
    ("machine learning platform", "AI, Data & Analytics"),
    ("software licensing and saas", "Software & Licensing"),
    ("it services and consulting", "IT Services"),
    ("hardware and devices", "Computing Hardware"),
])
def test_infer_technology(q, expected):
    assert infer_query_intent(q)["technology"] == expected


# ----------------------------- intent: country -----------------------------
@pytest.mark.parametrize("q,code", [
    ("opportunities in Spain", "ESP"),
    ("tenders in España", "ESP"),
    ("French public sector", "FRA"),
    ("German market", "DEU"),
    ("contracts in Italy", "ITA"),
    ("Portugal tenders", "PRT"),
    ("Dutch government", "NLD"),
    ("Belgium", "BEL"),
    ("Ireland", "IRL"),
])
def test_infer_country(q, code):
    assert infer_query_intent(q)["country"] == code


def test_no_country_when_absent():
    assert infer_query_intent("cloud opportunities")["country"] is None


# ----------------------------- intent: amount -----------------------------
@pytest.mark.parametrize("q,amt", [
    ("cloud above 500k", 500000),
    ("over 500k", 500000),
    ("more than 1m", 1000000),
    ("over 1 million", 1000000),
    ("2.5m contracts", 2500000),
    ("above 500,000", 500000),
    ("above 500.000", 500000),
])
def test_infer_amount(q, amt):
    assert infer_query_intent(q)["min_amount"] == amt


def test_no_amount_when_absent():
    assert infer_query_intent("cybersecurity tenders")["min_amount"] is None


# ----------------------------- intent: scope -----------------------------
def test_infer_scope():
    assert infer_query_intent("awarded contracts")["scope"] == "Awarded contracts"
    assert infer_query_intent("who won the cloud deal")["scope"] == "Awarded contracts"
    assert infer_query_intent("open tenders to pursue")["scope"] == "Open tenders only"
    assert infer_query_intent("show me both")["scope"] == "Both"


# ----------------------------- intent: competition -----------------------------
def test_infer_low_competition():
    assert infer_query_intent("awarded contracts with low competition")["low_competition"] is True
    assert infer_query_intent("single bidder deals")["low_competition"] is True
    assert infer_query_intent("cloud opportunities")["low_competition"] is None


# ----------------------------- intent: sort -----------------------------
def test_infer_sort():
    assert infer_query_intent("highest value tenders")["sort"] == "Commercial Value"
    assert infer_query_intent("most winnable bids")["sort"] == "Win Probability"
    assert infer_query_intent("closing soon")["sort"] == "Deadline Soonest"
    assert infer_query_intent("strategic buyer focus")["sort"] == "Buyer Attractiveness"
    assert infer_query_intent("best microsoft fit")["sort"] == "Microsoft Opportunity Score"


# ----------------------------- merge -----------------------------
def _base_sidebar(**over):
    base = {"technology": "Any technology", "country": None, "min_amount": None,
            "scope": "Open tenders only", "low_competition": False, "sort": "Recommended"}
    base.update(over)
    return base


def test_merge_query_fills_defaults():
    sb = _base_sidebar()
    intent = infer_query_intent("Cloud opportunities above 500k in Spain")
    m = merge_sidebar_and_query_intent(sb, intent)
    assert m["technology"] == "Cloud & Azure"
    assert m["min_amount"] == 500000
    assert m["country"] == "ESP"


def test_merge_sidebar_wins_when_set():
    sb = _base_sidebar(technology="Cybersecurity", country="FRA", min_amount=1000000)
    intent = infer_query_intent("cloud in Spain above 500k")
    m = merge_sidebar_and_query_intent(sb, intent)
    # user explicitly chose these in the sidebar -> respected
    assert m["technology"] == "Cybersecurity"
    assert m["country"] == "FRA"
    assert m["min_amount"] == 1000000


def test_merge_low_competition_is_or():
    sb = _base_sidebar(low_competition=False)
    intent = infer_query_intent("awarded with low competition")
    assert merge_sidebar_and_query_intent(sb, intent)["low_competition"] is True


def test_merge_scope_override():
    sb = _base_sidebar()
    intent = infer_query_intent("awarded contracts")
    assert merge_sidebar_and_query_intent(sb, intent)["scope"] == "Awarded contracts"


# ----------------------------- quick questions -----------------------------
def test_quick_questions_list_matches_spec():
    expected = [
        "Top Microsoft-fit opportunities",
        "Cloud opportunities above 500k",
        "Cybersecurity opportunities",
        "Which buyers should Microsoft prioritize?",
        "High-value open tenders",
        "Awarded contracts with low competition",
        "Best opportunities in Spain",
    ]
    assert QUICK_QUESTIONS == expected


def test_quick_question_filters_distinct():
    cloud = quick_question_filters("Cloud opportunities above 500k")
    assert cloud["technology"] == "Cloud & Azure" and cloud["min_amount"] == 500000
    cyber = quick_question_filters("Cybersecurity opportunities")
    assert cyber["technology"] == "Cybersecurity"
    buyers = quick_question_filters("Which buyers should Microsoft prioritize?")
    assert buyers["route"] == ROUTE_BUYERS
    awarded = quick_question_filters("Awarded contracts with low competition")
    assert awarded["route"] == ROUTE_AWARDED and awarded["low_competition"] is True
    spain = quick_question_filters("Best opportunities in Spain")
    assert spain["country"] == "ESP"
    hv = quick_question_filters("High-value open tenders")
    assert hv["min_amount"] == 1000000 and hv["sort"] == "Commercial Value"


def test_quick_question_unknown_returns_empty():
    assert quick_question_filters("not a real question") == {}


# ----------------------------- sorting -----------------------------
def _notices():
    return [
        {"notice_kind": "CN", "notice_id": "big", "project_title": "Generic supply",
         "description": "", "cpv_code": "30", "cpv_division": "30", "procedure_type": "open",
         "amount": 9_000_000, "currency": "EUR", "buyer_name": "A", "buyer_country": "ESP",
         "submission_deadline": "2099-12-31", "num_tenders": 5},
        {"notice_kind": "CN", "notice_id": "fit", "project_title": "Azure cloud cybersecurity AI platform",
         "description": "data analytics digital transformation", "cpv_code": "72", "cpv_division": "72",
         "procedure_type": "open", "amount": 500_000, "currency": "EUR", "buyer_name": "B",
         "buyer_country": "ESP", "submission_deadline": "2099-01-05", "num_tenders": 3},
        {"notice_kind": "CN", "notice_id": "soon", "project_title": "IT support services",
         "description": "support", "cpv_code": "72", "cpv_division": "72", "procedure_type": "open",
         "amount": 200_000, "currency": "EUR", "buyer_name": "C", "buyer_country": "ESP",
         "submission_deadline": "2025-01-10", "num_tenders": 2},
    ]


def test_sort_commercial_value_first():
    r = rank_opportunities("opportunities", _notices(), top_n=3, fast_mode=True,
                           sort_mode="Commercial Value", today=date(2025, 1, 1))
    assert r[0].notice["notice_id"] == "big"


def test_sort_strategic_fit_first():
    r = rank_opportunities("opportunities", _notices(), top_n=3, fast_mode=True,
                           sort_mode="Strategic Fit", today=date(2025, 1, 1))
    assert r[0].notice["notice_id"] == "fit"


def test_sort_deadline_soonest():
    r = rank_opportunities("opportunities", _notices(), top_n=3, fast_mode=True,
                           sort_mode="Deadline Soonest", today=date(2025, 1, 1))
    assert r[0].notice["notice_id"] == "soon"
    assert [x.rank for x in r] == [1, 2, 3]


def test_sort_modes_never_crash_on_missing_fields():
    sparse = [{"notice_kind": "CN", "notice_id": "x", "project_title": None}]
    for mode in SORT_MODES:
        r = rank_opportunities("q", sparse, top_n=1, fast_mode=True, sort_mode=mode)
        assert len(r) == 1


def test_recommended_keeps_blended_order():
    notices = _notices()
    r = rank_opportunities("azure cloud cybersecurity", notices, top_n=3, fast_mode=True,
                           sort_mode="Recommended", today=date(2025, 1, 1))
    # strong-fit relevant notice should lead the blended ranking
    assert r[0].notice["notice_id"] == "fit"


# ----------------------------- tech area config -----------------------------
def test_tech_areas_have_terms_and_divisions():
    for label in ["Cloud & Azure", "Cybersecurity", "Software & Licensing", "IT Services"]:
        assert TECH_AREAS[label]["terms"]
        assert TECH_AREAS[label]["divisions"]
    assert TECH_AREAS["Any technology"]["terms"] == []
