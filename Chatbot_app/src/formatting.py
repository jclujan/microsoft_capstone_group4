"""Presentation formatting — turn scored evidence into clean business output.

No Streamlit dependency so it is unit-testable. The UI layer consumes these
plain dicts/strings; the LLM layer consumes the same grounded context.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .opportunity_scoring import parse_amount
from .retrieval import RankedOpportunity

_BAND_EMOJI = {
    "High-priority bid": "🟢",
    "Worth evaluating": "🔵",
    "Monitor": "🟡",
    "Low fit": "🟠",
    "Market intelligence only": "⚪",
}


def format_amount(amount: Any, currency: Optional[str] = None) -> str:
    val = parse_amount(amount)
    if val is None:
        return "Value not disclosed"
    cur = (currency or "EUR").strip().upper() or "EUR"
    return f"{val:,.0f} {cur}"


def format_notice_kind(notice: Dict[str, Any]) -> str:
    kind = str(notice.get("notice_kind") or "").upper()
    if kind == "CAN" or notice.get("result_code"):
        return "Awarded contract (market intelligence)"
    return "Open tender"


def source_card(ranked: RankedOpportunity) -> Dict[str, Any]:
    """Build a clean, render-ready source card from a ranked opportunity."""
    n = ranked.notice
    r = ranked.score_result
    title = n.get("project_title") or "(untitled notice)"
    ev = r.evidence or {}
    amount_value = parse_amount(n.get("amount"))
    single_prob = ev.get("single_bidder_probability")
    return {
        "rank": ranked.rank,
        "notice_id": n.get("notice_id"),
        "title": title,
        "kind": format_notice_kind(n),
        "buyer": n.get("buyer_name") or "Unknown buyer",
        "country": n.get("buyer_country") or "—",
        "cpv": n.get("cpv_code") or "—",
        "cpv_division": n.get("cpv_division") or "—",
        "amount": format_amount(n.get("amount"), n.get("currency")),
        "amount_value": amount_value,
        "deadline": n.get("submission_deadline") or "—",
        "procedure": n.get("procedure_type") or "—",
        "winner": n.get("winner_name") or None,
        "opportunity_score": round(r.opportunity_score, 1),
        "band": r.band,
        "band_emoji": _BAND_EMOJI.get(r.band, "•"),
        "components": {k: round(v, 1) for k, v in r.components.items()},
        "profile_type": ev.get("profile_type") or "Unclustered buyer",
        "profile_source": ev.get("profile_source") or "No clustered buyer match",
        "opportunity_profile_type": ev.get("opportunity_profile_type") or "Other / Unclassified",
        "treemap_profile_type": ev.get("treemap_profile_type") or ev.get("profile_type") or "Other / Unclassified",
        "treemap_profile_source": ev.get("treemap_profile_source") or "Opportunity profile fallback",
        "is_clustered_profile": bool(ev.get("is_clustered_profile")),
        "cluster_id": ev.get("cluster_id"),
        "cluster_label": ev.get("cluster_label"),
        "single_bidder_probability": int(single_prob) if single_prob is not None else 50,
        "single_bidder_reasons": list(ev.get("single_bidder_reasons") or []),
        "buyer_single_bidder_rate": ev.get("buyer_single_bidder_rate"),
        "buyer_cross_border_rate": ev.get("buyer_cross_border_rate"),
        "buyer_total_contracts": ev.get("buyer_total_contracts"),
        "buyer_total_awarded_value_eur": ev.get("buyer_total_awarded_value_eur"),
        "why": list(r.reason_codes),
        "risks": list(r.risks),
        "next_action": r.next_action,
        "relevance": round(ranked.relevance, 1),
    }


def build_evidence_block(cards: List[Dict[str, Any]]) -> str:
    """Compact, grounded text passed to the LLM (no invented facts)."""
    lines: List[str] = []
    for c in cards:
        lines.append(
            f"[#{c['rank']}] id={c['notice_id']} | {c['kind']} | score={c['opportunity_score']} "
            f"({c['band']}) | buyer_profile={c.get('profile_type', 'Unclustered buyer')} | "
            f"opportunity_profile={c.get('opportunity_profile_type', 'Other / Unclassified')} | "
            f"single_bidder_probability={c.get('single_bidder_probability', 50)}/100 | "
            f"buyer={c['buyer']} ({c['country']}) | CPV={c['cpv']} | "
            f"value={c['amount']} | deadline={c['deadline']}"
        )
        title = str(c["title"])[:160]
        lines.append(f"     title: {title}")
        if c["why"]:
            lines.append("     why: " + " ".join(c["why"][:3]))
        if c["risks"]:
            lines.append("     risks: " + " ".join(c["risks"][:3]))
    return "\n".join(lines)


def executive_summary(cards: List[Dict[str, Any]], route: str, query: str) -> str:
    """Deterministic, retrieval-only executive summary (LLM-free fallback)."""
    if not cards:
        return ("No matching records were found in the revised Gold tables for this "
                "request. Try broadening the filters or the technology area.")

    high = [c for c in cards if c["band"] == "High-priority bid"]
    awarded = [c for c in cards if c["kind"].startswith("Awarded")]
    top = cards[0]

    parts: List[str] = []
    if route == "awarded" or (awarded and len(awarded) == len(cards)):
        parts.append(
            f"These {len(cards)} records are awarded contracts and are not currently "
            "open for bidding. Treat them as market intelligence."
        )
    else:
        parts.append(
            f"Reviewed and scored {len(cards)} candidate opportunities for Microsoft fit, "
            "winnability, value and urgency."
        )
        if high:
            parts.append(f"{len(high)} qualify as high-priority bids.")

    parts.append(
        f"Top pick: '{str(top['title'])[:90]}' from {top['buyer']} "
        f"({top['country']}) scoring {top['opportunity_score']}/100 — {top['band']}."
    )
    if top["why"]:
        parts.append("Rationale: " + top["why"][0])
    return " ".join(parts)


def format_buyer_card(buyer: Dict[str, Any], rank: int) -> Dict[str, Any]:
    return {
        "rank": rank,
        "buyer": buyer.get("buyer_name") or "Unknown buyer",
        "country": buyer.get("buyer_country") or "—",
        "buyer_type": buyer.get("buyer_type") or "—",
        "total_contracts": buyer.get("total_contracts") or 0,
        "total_value": format_amount(buyer.get("total_awarded_value_eur"), "EUR"),
        "avg_value": format_amount(buyer.get("avg_award_value_eur"), "EUR"),
        "top_cpv_division": buyer.get("top_cpv_division") or "—",
        "single_bidder_rate": buyer.get("single_bidder_rate"),
        "attractiveness": buyer.get("buyer_attractiveness", 0.0),
        "reasons": buyer.get("reasons", []),
    }
