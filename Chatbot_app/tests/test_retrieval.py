"""Tests for intent routing, relevance and blended ranking."""
from src.retrieval import (
    Priorities,
    ROUTE_AWARDED,
    ROUTE_BUYERS,
    ROUTE_OPPORTUNITIES,
    keyword_relevance,
    rank_buyers,
    rank_opportunities,
    route_intent,
)


def test_route_intent():
    assert route_intent("Which buyers should Microsoft prioritize?") == ROUTE_BUYERS
    assert route_intent("Awarded contracts with low competition") == ROUTE_AWARDED
    assert route_intent("who won the cloud tender") == ROUTE_AWARDED
    assert route_intent("Top Microsoft-fit opportunities") == ROUTE_OPPORTUNITIES
    assert route_intent("cloud tenders above 500k") == ROUTE_OPPORTUNITIES


def test_keyword_relevance():
    n = {"project_title": "Azure cloud migration", "description": "cybersecurity",
         "buyer_name": "Ministry", "cpv_code": "72", "cpv_division": "72"}
    assert keyword_relevance("cloud azure", n) > keyword_relevance("vegetables", n)
    # empty query -> neutral
    assert keyword_relevance("", n) == 50.0


def _notices():
    return [
        {"notice_kind": "CN", "notice_id": "1", "project_title": "Azure cloud platform",
         "description": "cybersecurity AI", "cpv_code": "72", "cpv_division": "72",
         "procedure_type": "open", "amount": 2_000_000, "currency": "EUR",
         "buyer_name": "Min Digital", "buyer_country": "ESP",
         "submission_deadline": "2099-01-01"},
        {"notice_kind": "CN", "notice_id": "2", "project_title": "Office cleaning services",
         "description": "cleaning", "cpv_code": "90", "cpv_division": "90",
         "procedure_type": "open", "amount": 30_000, "currency": "EUR",
         "buyer_name": "Town", "buyer_country": "ESP", "submission_deadline": "2099-01-01"},
    ]


def test_ranking_combines_relevance_and_opportunity_score():
    ranked = rank_opportunities("cloud azure cybersecurity", _notices(), top_n=2, fast_mode=True)
    assert ranked[0].notice["notice_id"] == "1"
    assert ranked[0].rank == 1
    assert ranked[0].final_rank_score >= ranked[1].final_rank_score


def test_priorities_influence_ranking():
    notices = _notices()
    # Neutral query (matches neither notice literally) so the strategic-fit / win
    # priority bonus is the deciding factor rather than raw keyword overlap.
    pr = Priorities(strategic_fit=True, high_win=True)
    ranked = rank_opportunities("procurement", notices, priorities=pr, top_n=2, fast_mode=True)
    ids = [r.notice["notice_id"] for r in ranked]
    assert ids[0] == "1"


def test_buyer_lookup_join():
    notices = _notices()
    lookup = {"min digital": {"total_contracts": 80, "avg_award_value_eur": 2_000_000,
                              "top_cpv_division": "72", "single_bidder_rate": 0.1}}
    ranked = rank_opportunities("cloud", notices, buyer_lookup=lookup, top_n=2, fast_mode=True)
    top = ranked[0]
    assert top.score_result.components["buyer_attractiveness"] > 60


def test_rank_buyers():
    buyers = [
        {"buyer_name": "A", "total_contracts": 80, "avg_award_value_eur": 2_000_000,
         "top_cpv_division": "72", "single_bidder_rate": 0.1},
        {"buyer_name": "B", "total_contracts": 1, "avg_award_value_eur": 1000,
         "top_cpv_division": "15", "single_bidder_rate": 0.9},
    ]
    ranked = rank_buyers(buyers, top_n=2)
    assert ranked[0]["buyer_name"] == "A"
    assert ranked[0]["buyer_attractiveness"] >= ranked[1]["buyer_attractiveness"]
