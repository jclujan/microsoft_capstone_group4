"""Tests for the optional LLM explanation layer and its guardrails."""
import os

from src.llm import (
    PROVIDER_NONE,
    SYSTEM_GUARDRAILS,
    build_prompt,
    explain,
    get_provider,
    is_enabled,
)


def test_default_provider_none(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert get_provider() == PROVIDER_NONE
    assert not is_enabled()


def test_guardrails_present():
    g = SYSTEM_GUARDRAILS.lower()
    # Must forbid inventing each critical entity type
    for term in ["notice id", "buyer", "amount", "winner", "date", "deadline", "countr"]:
        assert term in g
    assert "only" in g  # only provided context
    assert "english" in g


def test_prompt_includes_context_and_query():
    prompt = build_prompt("which cloud bids?", "[#1] id=42 ...", "summary text")
    assert "which cloud bids?" in prompt
    assert "id=42" in prompt
    assert "summary text" in prompt


def test_explain_none_provider_returns_deterministic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    out = explain("q", "evidence", "deterministic summary")
    assert out["used_llm"] is False
    assert out["text"] == "deterministic summary"
    assert out["error"] is None


def test_explain_bad_provider_falls_back(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "databricks")
    monkeypatch.delenv("DATABRICKS_SERVER_HOSTNAME", raising=False)
    out = explain("q", "evidence", "deterministic summary", timeout=1)
    # No host configured -> must fall back gracefully, never raise
    assert out["text"] == "deterministic summary"
    assert out["used_llm"] is False
