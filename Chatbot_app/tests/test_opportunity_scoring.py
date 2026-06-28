"""Tests for the deterministic Microsoft Opportunity Score engine."""
from datetime import date, timedelta

from src.opportunity_scoring import (
    BANDS,
    WEIGHTS,
    band_for,
    buyer_attractiveness_score,
    commercial_value_score,
    data_confidence_score,
    parse_amount,
    score_opportunity,
    strategic_fit_score,
    urgency_score,
    win_probability_score,
)


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_score_in_range_and_dict_shape():
    notice = {"notice_kind": "CN", "project_title": "Azure cloud migration", "cpv_division": "72",
              "amount": 500000, "currency": "EUR", "buyer_name": "Ministry",
              "buyer_country": "ESP", "cpv_code": "72000000", "description": "cloud",
              "submission_deadline": "2099-01-01"}
    res = score_opportunity(notice)
    assert 0.0 <= res.opportunity_score <= 100.0
    d = res.to_dict()
    assert set(d["components"].keys()) == set(WEIGHTS.keys())
    assert d["band"] in {b[1] for b in BANDS}


def test_microsoft_tech_fit_beats_irrelevant():
    ms = {"project_title": "Cloud cybersecurity and Azure migration", "cpv_division": "72",
          "cpv_code": "72000000", "description": "AI analytics"}
    junk = {"project_title": "Supply of fresh vegetables", "cpv_division": "15",
            "cpv_code": "15000000", "description": "tomatoes"}
    assert strategic_fit_score(ms)[0] > strategic_fit_score(junk)[0]
    assert strategic_fit_score(ms)[0] >= 60


def test_cpv_boost_applies():
    soft = {"project_title": "system", "cpv_division": "48", "cpv_code": "48000000"}
    other = {"project_title": "system", "cpv_division": "45", "cpv_code": "45000000"}
    assert strategic_fit_score(soft)[0] > strategic_fit_score(other)[0]


def test_value_parsing():
    assert parse_amount("1.234,56") == 1234.56 or parse_amount("1.234,56") == 1234.56
    assert parse_amount("500000") == 500000.0
    assert parse_amount(None) is None
    assert parse_amount("not a number") is None
    assert parse_amount(-5) is None
    assert parse_amount("€ 1 000 000") == 1000000.0


def test_commercial_value_monotonic_and_missing():
    low, _, _ = commercial_value_score({"amount": 10_000})
    high, _, _ = commercial_value_score({"amount": 5_000_000})
    assert high > low
    missing, reasons, _ = commercial_value_score({"amount": None})
    assert 0 <= missing <= 100 and reasons


def test_win_probability_awarded_lower_than_open():
    open_n = {"notice_kind": "CN", "procedure_type": "open", "project_title": "cloud"}
    awarded = {"notice_kind": "CAN", "result_code": "selec-w", "procedure_type": "open",
               "project_title": "cloud"}
    assert win_probability_score(open_n)[0] > win_probability_score(awarded)[0]


def test_win_probability_single_bidder_risk():
    n = {"notice_kind": "CN", "procedure_type": "open", "num_tenders": 1, "project_title": "cloud"}
    score, reasons, risks = win_probability_score(n)
    assert any("single" in r.lower() for r in risks)


def test_deadline_actionability_scoring():
    today = date(2025, 1, 1)
    soon = {"notice_kind": "CN", "submission_deadline": (today + timedelta(days=3)).isoformat()}
    far = {"notice_kind": "CN", "submission_deadline": (today + timedelta(days=120)).isoformat()}
    past = {"notice_kind": "CN", "submission_deadline": (today - timedelta(days=5)).isoformat()}
    assert urgency_score(soon, today=today)[0] > urgency_score(far, today=today)[0]
    assert urgency_score(past, today=today)[0] < 20
    awarded = {"notice_kind": "CAN", "result_code": "selec-w"}
    assert urgency_score(awarded, today=today)[0] < 20


def test_buyer_attractiveness_with_mock_profile():
    strong = {"total_contracts": 80, "avg_award_value_eur": 2_000_000,
              "top_cpv_division": "72", "single_bidder_rate": 0.1, "cross_border_rate": 0.2}
    weak = {"total_contracts": 1, "avg_award_value_eur": 5000,
            "top_cpv_division": "15", "single_bidder_rate": 0.9}
    assert buyer_attractiveness_score(strong)[0] > buyer_attractiveness_score(weak)[0]
    # no profile -> neutral
    assert 40 <= buyer_attractiveness_score(None)[0] <= 60


def test_data_confidence_penalizes_missing():
    full = {"notice_kind": "CAN", "project_title": "x", "buyer_name": "b",
            "cpv_code": "72", "buyer_country": "ESP", "amount": 100}
    empty = {"notice_kind": "CAN"}
    assert data_confidence_score(full)[0] > data_confidence_score(empty)[0]
    assert data_confidence_score(empty)[1]  # has risk messages


def test_band_thresholds():
    assert band_for(95) == "High-priority bid"
    assert band_for(65) == "Worth evaluating"
    assert band_for(50) == "Monitor"
    assert band_for(30) == "Low fit"
    assert band_for(5) == "Market intelligence only"


def test_full_score_high_fit_open_tender_scores_well():
    today = date(2025, 1, 1)
    notice = {
        "notice_kind": "CN", "project_title": "Azure cloud platform and cybersecurity migration",
        "description": "AI analytics data platform digital transformation",
        "cpv_code": "72000000", "cpv_division": "72", "procedure_type": "open",
        "amount": 3_000_000, "currency": "EUR", "buyer_name": "Ministry of Digital",
        "buyer_country": "ESP", "submission_deadline": (today + timedelta(days=20)).isoformat(),
        "num_tenders": 3,
    }
    buyer = {"total_contracts": 60, "avg_award_value_eur": 1_500_000, "top_cpv_division": "72",
             "single_bidder_rate": 0.15}
    res = score_opportunity(notice, buyer_profile=buyer, today=today)
    assert res.opportunity_score >= 60
    assert res.next_action
    assert res.reason_codes
