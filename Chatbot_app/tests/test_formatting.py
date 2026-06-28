"""Tests for clean presentation formatting."""
from datetime import date

from src.formatting import (
    build_evidence_block,
    executive_summary,
    format_amount,
    format_buyer_card,
    format_notice_kind,
    source_card,
)
from src.retrieval import rank_opportunities


def _ranked():
    notices = [{
        "notice_kind": "CN", "notice_id": "42", "project_title": "Azure cloud migration",
        "description": "cybersecurity AI analytics", "cpv_code": "72000000", "cpv_division": "72",
        "procedure_type": "open", "amount": 1_500_000, "currency": "EUR",
        "buyer_name": "Ministry of Digital", "buyer_country": "ESP",
        "submission_deadline": "2099-01-01", "num_tenders": 3,
    }]
    return rank_opportunities("cloud azure", notices, top_n=1, fast_mode=True, today=date(2025, 1, 1))


def test_format_amount():
    assert format_amount(1_500_000, "EUR") == "1,500,000 EUR"
    assert format_amount(None) == "Value not disclosed"
    assert format_amount("1.234,56", "EUR").endswith("EUR")


def test_format_notice_kind():
    assert format_notice_kind({"notice_kind": "CN"}) == "Open tender"
    assert "intelligence" in format_notice_kind({"notice_kind": "CAN", "result_code": "selec-w"})


def test_source_card_is_clean():
    card = source_card(_ranked()[0])
    # No raw dict dumps — all the human-facing keys present
    for key in ("rank", "title", "buyer", "amount", "band", "opportunity_score",
                "why", "risks", "next_action", "components"):
        assert key in card
    assert card["notice_id"] == "42"
    assert isinstance(card["why"], list)
    assert card["amount"].endswith("EUR")
    assert 0 <= card["opportunity_score"] <= 100


def test_evidence_block_contains_ids_no_dict_repr():
    cards = [source_card(r) for r in _ranked()]
    block = build_evidence_block(cards)
    assert "id=42" in block
    assert "{" not in block  # no python dict repr leaking through


def test_executive_summary_non_empty():
    cards = [source_card(r) for r in _ranked()]
    summary = executive_summary(cards, "opportunities", "cloud azure")
    assert "Top pick" in summary
    assert summary.strip()
    # empty case
    assert "No matching" in executive_summary([], "opportunities", "x")


def test_format_buyer_card():
    b = {"buyer_name": "Min", "buyer_country": "ESP", "total_contracts": 50,
         "total_awarded_value_eur": 1_000_000, "avg_award_value_eur": 20000,
         "top_cpv_division": "72", "buyer_attractiveness": 88.0, "reasons": ["x"]}
    card = format_buyer_card(b, 1)
    assert card["rank"] == 1
    assert card["buyer"] == "Min"
    assert card["total_value"].endswith("EUR")
