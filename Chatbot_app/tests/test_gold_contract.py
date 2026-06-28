"""Tests for the revised-Gold schema contract and table-name safety."""
import pytest

from src.gold_contract import (
    ALLOWED_TABLES,
    FORBIDDEN_TABLES,
    PRIMARY_TABLE,
    UnsafeTableError,
    is_safe_table,
    missing_columns,
    qualified,
    safe_table_identifier,
)


def test_primary_table_is_notices_unified():
    assert PRIMARY_TABLE == "workspace.gold.notices_unified"
    assert "notices_unified" in ALLOWED_TABLES
    assert "cn_predictions" in ALLOWED_TABLES


def test_allows_revised_gold_tables():
    for t in ALLOWED_TABLES:
        assert is_safe_table(f"workspace.gold.{t}")


def test_rejects_silver_and_bronze():
    assert not is_safe_table("workspace.silver.contract_notices")
    assert not is_safe_table("workspace.bronze.raw_xml")
    assert not is_safe_table("workspace.raw.notices")


def test_rejects_legacy_tables():
    assert "rag_documents" in FORBIDDEN_TABLES
    assert "ml_contract_features" in FORBIDDEN_TABLES
    assert not is_safe_table("workspace.gold.rag_documents")
    assert not is_safe_table("workspace.gold.ml_contract_features")


def test_rejects_injection_patterns():
    assert not is_safe_table("workspace.gold.notices_unified; DROP TABLE x")
    assert not is_safe_table("workspace.gold.notices_unified--")
    assert not is_safe_table("workspace.gold.`notices_unified`")
    assert not is_safe_table("workspace.gold.notices unified")
    assert not is_safe_table("workspace.gold.notices_unified /* x */")
    assert not is_safe_table("workspace.gold.'notices'")


def test_rejects_unknown_gold_table():
    assert not is_safe_table("workspace.gold.some_other_table")
    assert not is_safe_table("workspace.gold")
    assert not is_safe_table("notices_unified")


def test_safe_identifier_quotes_and_raises():
    assert safe_table_identifier("workspace.gold.notices_unified") == "`workspace`.`gold`.`notices_unified`"
    with pytest.raises(UnsafeTableError):
        safe_table_identifier("workspace.silver.contract_notices")
    with pytest.raises(UnsafeTableError):
        safe_table_identifier("workspace.gold.rag_documents")


def test_qualified_helper():
    assert qualified("buyer_profiles") == "workspace.gold.buyer_profiles"
    with pytest.raises(UnsafeTableError):
        qualified("rag_documents")


def test_missing_columns():
    assert missing_columns(["a", "b"], ["a", "b", "c"]) == ["c"]
    assert missing_columns(["A", "B"], ["a"]) == []

def test_allows_cn_predictions_table():
    assert is_safe_table("workspace.gold.cn_predictions")
    assert qualified("cn_predictions") == "workspace.gold.cn_predictions"
