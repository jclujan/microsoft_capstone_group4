"""Tests for the OR-based technology filter SQL construction (no Databricks)."""
from unittest.mock import patch

from src.config import load_config
from src import data_access as da


def _capture_query(**kwargs):
    """Call fetch_notice_candidates with _run_query mocked, return (sql, params)."""
    captured = {}

    def fake_run(cfg, query, params=None):
        captured["query"] = query
        captured["params"] = params or []
        return []

    cfg = load_config()
    with patch.object(da, "_run_query", side_effect=fake_run):
        da.fetch_notice_candidates(cfg, **kwargs)
    return captured["query"], captured["params"]


def test_tech_terms_use_or_logic():
    sql, params = _capture_query(
        cpv_divisions=["72", "48"],
        tech_terms=["cloud", "azure"],
        limit=100,
    )
    # The technology block must be a single OR group, not separate AND filters.
    assert " OR " in sql
    assert "cpv_division` IN (?, ?)" in sql
    assert sql.count("LIKE ?") == 4  # cloud + azure, each on title+description
    assert "%cloud%" in params and "%azure%" in params


def test_country_and_amount_are_and_filters():
    sql, params = _capture_query(country="ESP", min_amount=500000, tech_terms=["cloud"])
    assert "buyer_country`) = ?" in sql
    assert "amount` >= ?" in sql
    assert "ESP" in params and 500000.0 in params


def test_no_select_star_and_only_gold():
    sql, _ = _capture_query(tech_terms=["cloud"])
    assert "SELECT *" not in sql
    assert "`workspace`.`gold`.`notices_unified`" in sql


def test_empty_filters_still_valid():
    sql, params = _capture_query(limit=50)
    assert "notices_unified" in sql
    assert "LIMIT 50" in sql
