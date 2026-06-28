"""Tests for clustered buyer profile enrichment used by recommendation cards."""
from src.gold_contract import ALLOWED_TABLES, is_safe_table
from src.opportunity_scoring import calculate_single_bidder_probability, score_opportunity
from src.retrieval import build_clustered_buyer_lookup, find_buyer_profile
from src.ui_components import prepare_profile_treemap_data


def test_clustered_tables_allowed_and_old_tables_rejected():
    assert "buyer_profiles_clustered" in ALLOWED_TABLES
    assert "cluster_profiles" in ALLOWED_TABLES
    assert is_safe_table("workspace.gold.buyer_profiles_clustered")
    assert is_safe_table("workspace.gold.cluster_profiles")
    assert not is_safe_table("workspace.gold.rag_documents")
    assert not is_safe_table("workspace.gold.ml_contract_features")


def test_cluster_label_becomes_profile_type():
    lookup = build_clustered_buyer_lookup(
        [{"buyer_name": "Instituto X", "buyer_country": "PRT", "cluster_id": 1}],
        [{"cluster_id": 1, "cluster_label": "Single-bidder health buyers"}],
    )
    hit = find_buyer_profile({"buyer_name": "Instituto X", "buyer_country": "PRT"}, lookup)
    assert hit["profile_type"] == "Single-bidder health buyers"
    assert hit["cluster_id"] == "1"


def test_unmatched_buyer_scores_as_unclustered():
    res = score_opportunity({"notice_kind": "CN", "buyer_name": "Unknown", "project_title": "cloud"})
    assert res.evidence["profile_type"] == "Unclustered buyer"


def test_single_bidder_probability_uses_buyer_rate():
    notice = {"notice_kind": "CN", "project_title": "cloud", "num_tenders": None}
    buyer = {"single_bidder_rate": 0.8, "cluster_label": "High single-bidder buyers", "cluster_id": 2}
    prob, reasons = calculate_single_bidder_probability(notice, buyer)
    assert prob > 65
    assert any("single-bidder rate" in r for r in reasons)


def test_single_bidder_probability_direct_single_bidder_is_100():
    prob, reasons = calculate_single_bidder_probability({"num_tenders": 1}, {"single_bidder_rate": 0.1})
    assert prob == 100
    assert "one recorded tender" in reasons[0].lower()


def test_treemap_groups_by_profile_type():
    rows = prepare_profile_treemap_data([
        {"profile_type": "National centralised agencies", "opportunity_score": 80, "amount_value": 1000, "single_bidder_probability": 40},
        {"profile_type": "National centralised agencies", "opportunity_score": 60, "amount_value": 2000, "single_bidder_probability": 60},
        {"profile_type": "Cross-border buyers", "opportunity_score": 90, "amount_value": 500, "single_bidder_probability": 30},
    ])
    by_name = {r["Profile Type"]: r for r in rows}
    assert by_name["National centralised agencies"]["Count"] == 2
    assert by_name["National centralised agencies"]["Total value"] == 3000
    assert by_name["National centralised agencies"]["Average opportunity score"] == 70
    assert by_name["Cross-border buyers"]["Count"] == 1


def test_single_bidder_probability_uses_cn_predictions_for_open_notices():
    notice = {"notice_kind": "CN", "project_title": "cloud", "single_bidder_prob": 0.82, "num_tenders": None}
    buyer = {"single_bidder_rate": 0.20, "cluster_label": "Open competition buyers", "cluster_id": 4}
    prob, reasons = calculate_single_bidder_probability(notice, buyer)
    assert 65 <= prob <= 82
    assert any("ML model predicts" in r for r in reasons)


def test_single_bidder_probability_ml_output_accepts_percent_scale():
    notice = {"notice_kind": "CN", "project_title": "cloud", "single_bidder_prob": 73}
    prob, reasons = calculate_single_bidder_probability(notice, None)
    assert prob == 73
    assert any("ML model predicts 73/100" in r for r in reasons)


def test_unclustered_cards_still_create_profile_mix_using_opportunity_fallback():
    rows = prepare_profile_treemap_data([
        {
            "profile_type": "Unclustered buyer",
            "opportunity_profile_type": "Cloud & Azure",
            "treemap_profile_type": "Cloud & Azure",
            "treemap_profile_source": "Opportunity profile fallback",
            "is_clustered_profile": False,
            "opportunity_score": 82,
            "amount_value": 500000,
            "single_bidder_probability": 42,
        },
        {
            "profile_type": "Unclustered buyer",
            "opportunity_profile_type": "Cybersecurity",
            "treemap_profile_type": "Cybersecurity",
            "treemap_profile_source": "Opportunity profile fallback",
            "is_clustered_profile": False,
            "opportunity_score": 76,
            "amount_value": 300000,
            "single_bidder_probability": 55,
        },
    ])
    by_name = {r["Profile Type"]: r for r in rows}
    assert "Cloud & Azure" in by_name
    assert "Cybersecurity" in by_name
    assert "Unclustered buyer" not in by_name
    assert by_name["Cloud & Azure"]["Source"] == "Opportunity profile fallback"
    assert by_name["Cloud & Azure"]["Fallback profiles"] == 1


def test_clustered_profile_remains_primary_for_treemap_when_available():
    rows = prepare_profile_treemap_data([
        {
            "profile_type": "National centralised agencies",
            "opportunity_profile_type": "Cloud & Azure",
            "treemap_profile_type": "National centralised agencies",
            "treemap_profile_source": "Clustered buyer persona",
            "is_clustered_profile": True,
            "opportunity_score": 80,
            "amount_value": 1000,
            "single_bidder_probability": 40,
        }
    ])
    assert rows[0]["Profile Type"] == "National centralised agencies"
    assert rows[0]["Source"] == "Clustered buyer persona"
    assert rows[0]["Clustered matches"] == 1
