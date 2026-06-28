"""Optional LLM explanation layer with strict grounding guardrails.

Providers
---------
* ``none``       (default) — no LLM; deterministic summaries are used.
* ``databricks`` — Databricks Foundation Model / serving endpoint.
* ``ollama``     — local Ollama server.

The LLM is ONLY an explanation layer over already-retrieved, already-scored
evidence. It must not invent notice IDs, buyers, amounts, winners, dates,
deadlines or countries. These rules live in :data:`SYSTEM_GUARDRAILS` and are
asserted by the test-suite.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROVIDER_NONE = "none"
PROVIDER_DATABRICKS = "databricks"
PROVIDER_OLLAMA = "ollama"

SYSTEM_GUARDRAILS = (
    "You are the Microsoft Bid Prioritization Assistant for public-sector sales users. "
    "You explain bid recommendations for European public procurement (TED) tenders.\n"
    "STRICT RULES:\n"
    "1. Use ONLY the provided Gold-table context below. Do not use outside knowledge.\n"
    "2. Do NOT invent notice IDs, buyers, amounts, winners, dates, deadlines or countries. "
    "Every figure you state must appear verbatim in the context.\n"
    "3. If the context is insufficient to answer, say so plainly.\n"
    "4. Always preserve and cite the source notice IDs you rely on.\n"
    "5. Write in clear business English for a non-technical Microsoft sales audience.\n"
    "6. Explain why an opportunity fits Microsoft, why it may be winnable, the key risks, "
    "and the recommended next action. Never fabricate evidence."
)


def get_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or PROVIDER_NONE).strip().lower()


def is_enabled() -> bool:
    return get_provider() in {PROVIDER_DATABRICKS, PROVIDER_OLLAMA}


def build_prompt(query: str, evidence_block: str, deterministic_summary: str) -> str:
    """Assemble the grounded user prompt. Context is the ONLY source of truth."""
    return (
        f"USER REQUEST:\n{query}\n\n"
        f"RETRIEVED GOLD-TABLE EVIDENCE (the only facts you may use):\n"
        f"{evidence_block}\n\n"
        f"DETERMINISTIC SUMMARY (already verified, you may refine its wording):\n"
        f"{deterministic_summary}\n\n"
        "Write a concise executive briefing (max ~180 words) that recommends which "
        "opportunities Microsoft should prioritize and why. Cite notice IDs. "
        "If evidence is thin, say so."
    )


def explain(
    query: str,
    evidence_block: str,
    deterministic_summary: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Return {'text', 'provider', 'used_llm', 'error'} — never raises."""
    provider = get_provider()
    if provider == PROVIDER_NONE:
        return {"text": deterministic_summary, "provider": provider, "used_llm": False, "error": None}

    prompt = build_prompt(query, evidence_block, deterministic_summary)
    try:
        if provider == PROVIDER_DATABRICKS:
            text = _call_databricks(prompt, timeout)
        elif provider == PROVIDER_OLLAMA:
            text = _call_ollama(prompt, timeout)
        else:
            return {"text": deterministic_summary, "provider": provider, "used_llm": False,
                    "error": f"Unknown provider '{provider}'."}
        if not text or not text.strip():
            raise ValueError("Empty LLM response.")
        return {"text": text.strip(), "provider": provider, "used_llm": True, "error": None}
    except Exception as exc:  # graceful fallback
        logger.info("LLM explanation failed, falling back: %s", exc)
        return {
            "text": deterministic_summary,
            "provider": provider,
            "used_llm": False,
            "error": "LLM unavailable; showing deterministic summary.",
        }


def _call_databricks(prompt: str, timeout: int) -> str:
    import requests  # local import keeps tests dependency-free

    host = os.getenv("DATABRICKS_SERVER_HOSTNAME", "").strip()
    token = os.getenv("DATABRICKS_TOKEN", "").strip()
    endpoint = os.getenv("DATABRICKS_LLM_ENDPOINT", "databricks-meta-llama-3-1-70b-instruct").strip()
    if not host:
        raise ValueError("DATABRICKS_SERVER_HOSTNAME not set.")
    if not host.startswith("http"):
        host = f"https://{host}"
    url = f"{host}/serving-endpoints/{endpoint}/invocations"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_GUARDRAILS},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 400,
        "temperature": 0.1,
    }
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_ollama(prompt: str, timeout: int) -> str:
    import requests

    base = os.getenv("OLLAMA_HOST", "http://localhost:11434").strip().rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.1").strip()
    url = f"{base}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": 0.1},
        "messages": [
            {"role": "system", "content": SYSTEM_GUARDRAILS},
            {"role": "user", "content": prompt},
        ],
    }
    resp = requests.post(url, data=json.dumps(payload), timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get("message", {}).get("content", "")
