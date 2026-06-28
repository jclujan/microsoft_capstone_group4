"""Tests for cn_predictions ML probability integration."""
from src.config import AppConfig
from src.gold_contract import ALLOWED_TABLES, is_safe_table, CN_PREDICTION_COLUMNS
from src import data_access as da
from src.opportunity_scoring import score_opportunity


def test_cn_predictions_contract_allowed():
    assert "cn_predictions" in ALLOWED_TABLES
    assert is_safe_table("workspace.gold.cn_predictions")
    assert "single_bidder_prob" in CN_PREDICTION_COLUMNS


def test_score_evidence_includes_ml_single_bidder_probability():
    notice = {
        "notice_kind": "CN",
        "notice_id": "CN-1",
        "project_title": "Azure cloud migration",
        "description": "cloud platform",
        "cpv_division": "72",
        "amount": 500000,
        "single_bidder_prob": 0.91,
        "cn_prediction_scored_at": "2026-01-01T00:00:00Z",
        "cn_prediction_source": "workspace.gold.cn_predictions",
    }
    res = score_opportunity(notice)
    assert res.evidence["single_bidder_probability"] == 91
    assert res.evidence["ml_single_bidder_probability"] == 91
    assert res.evidence["single_bidder_prediction_source"] == "workspace.gold.cn_predictions"


def test_fetch_cn_predictions_selects_by_notice_ids(monkeypatch):
    cfg = AppConfig(server_hostname="x", warehouse_id="y", access_token="z")

    def fake_available_columns(_cfg, table_name):
        assert table_name == "workspace.gold.cn_predictions"
        return list(CN_PREDICTION_COLUMNS)

    calls = {}

    def fake_run_query(_cfg, query, params=None):
        calls["query"] = query
        calls["params"] = params
        return [{"notice_id": "N1", "single_bidder_prob": 0.7}]

    monkeypatch.setattr(da, "_available_columns", fake_available_columns)
    monkeypatch.setattr(da, "_run_query", fake_run_query)

    rows = da.fetch_cn_predictions(cfg, notice_ids=["N1", "N2"])
    assert rows[0]["notice_id"] == "N1"
    assert "workspace`.`gold`.`cn_predictions" in calls["query"]
    assert calls["params"] == ["N1", "N2"]
