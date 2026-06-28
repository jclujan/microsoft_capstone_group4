"""Microsoft Bid Prioritization Assistant — Databricks App (Streamlit).

Browser-ready Streamlit app that scores, ranks and explains European public
procurement opportunities for Microsoft, grounded in the revised Gold tables.

Run locally:    streamlit run app.py
In Databricks:  configured via app.yaml (command: streamlit run app.py)

Interaction model
-----------------
The app is a clean Microsoft-style recommendation assistant. There is no
sidebar anywhere; all controls live in an in-page "Advanced filters" expander.
Every analysis is driven by ONE unified ``active_request`` object built from:
  * a clicked business preset (full request, not just text), or
  * a typed question (intent inferred, merged with explicitly-changed filters).
If the exact request returns nothing, a declared fallback plan progressively
broadens the search and the UI clearly labels the fallback.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config  # noqa: E402
from src import data_access as da  # noqa: E402
from src import formatting as fmt  # noqa: E402
from src import llm as llm_mod  # noqa: E402
from src import ui_components as ui  # noqa: E402
from src.retrieval import (  # noqa: E402
    Priorities,
    QUICK_QUESTIONS,
    ROUTE_AWARDED,
    ROUTE_BUYERS,
    ROUTE_OPPORTUNITIES,
    SORT_MODES,
    TECH_AREAS,
    TECH_AREA_LABELS,
    active_request_from_preset,
    build_active_request,
    build_clustered_buyer_lookup,
    build_fallback_plan,
    infer_buyers_from_notices,
    rank_buyers,
    rank_opportunities,
)

st.set_page_config(
    page_title="Microsoft Bid Prioritization Assistant",
    page_icon="🟦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Session-state: single source of truth
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "active_request": None,   # the unified request that drives analysis
    "did_analyze": False,     # whether to render results this run
    "query_input": "",        # bound to the text box
    # advanced-filter widget state (the expander reads/writes these keys)
    "f_country": "",
    "f_tech": "Any technology",
    "f_min_amount": 0,
    "f_scope": "Open tenders only",
    "f_risk": "Balanced",
    "f_top_n": 10,
    "f_sort": "Recommended",
    "f_low_comp": False,
    "f_fast": True,
}


def _init_state(cfg):
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if not st.session_state.get("_seeded_topn"):
        st.session_state["f_top_n"] = cfg.default_top_n
        st.session_state["_seeded_topn"] = True


# ---------------------------------------------------------------------------
# Cached backend calls (unchanged data layer)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_config():
    return load_config()


@st.cache_data(show_spinner=False, ttl=300)
def cached_health(_cfg_key: str):
    return da.health_check(get_config())


@st.cache_data(show_spinner=False, ttl=600)
def cached_buyer_lookup(_cfg_key: str, country):
    try:
        rows = da.fetch_buyer_profiles(get_config(), country=country, limit=500)
    except da.DataAccessError:
        return {}
    return {str(r.get("buyer_name") or "").strip().lower(): r for r in rows if r.get("buyer_name")}


@st.cache_data(show_spinner=False, ttl=600)
def cached_clustered_buyer_lookup(_cfg_key: str, country):
    """Load clustered buyer personas and return lookup for opportunity scoring.

    If the clustered tables are unavailable or not yet granted as App resources,
    return an empty lookup so the app continues with unclustered labels.
    """
    try:
        clustered = da.fetch_buyer_profiles_clustered(get_config(), country=country, limit=10000)
        profiles = da.fetch_cluster_profiles(get_config(), limit=100)
        return build_clustered_buyer_lookup(clustered, profiles)
    except da.DataAccessError:
        return {}


@st.cache_data(show_spinner=False, ttl=600)
def cached_cn_prediction_lookup(_cfg_key: str, notice_ids):
    """Load ML single-bidder probabilities for the current candidate notices.

    The cn_predictions table is optional. If the App lacks SELECT on it, the
    recommendation engine falls back to notice/buyer/cluster competition signals.
    """
    ids = tuple(str(x).strip() for x in (notice_ids or []) if str(x or "").strip())
    if not ids:
        return {}
    try:
        rows = da.fetch_cn_predictions(get_config(), notice_ids=list(ids), limit=len(ids))
    except da.DataAccessError:
        return {}
    out = {}
    for row in rows:
        nid = str(row.get("notice_id") or "").strip()
        if not nid:
            continue
        # If duplicated, keep the most recent row returned by scored_at DESC.
        out.setdefault(nid, row)
    return out


def _attach_cn_predictions(candidates, prediction_lookup):
    """Attach ML prediction fields to candidate notices by notice_id."""
    if not candidates or not prediction_lookup:
        return candidates
    enriched = []
    for row in candidates:
        item = dict(row)
        nid = str(item.get("notice_id") or "").strip()
        pred = prediction_lookup.get(nid)
        if pred:
            item["single_bidder_prob"] = pred.get("single_bidder_prob")
            item["cn_prediction_scored_at"] = pred.get("scored_at")
            item["cn_prediction_source"] = "workspace.gold.cn_predictions"
        enriched.append(item)
    return enriched


@st.cache_data(show_spinner=False, ttl=300)
def cached_candidates(_cfg_key, country, min_amount, notice_kind, cpv_divisions, tech_terms, limit):
    return da.fetch_notice_candidates(
        get_config(),
        country=country,
        min_amount=min_amount if min_amount else None,
        notice_kind=notice_kind,
        cpv_divisions=list(cpv_divisions) if cpv_divisions else None,
        tech_terms=list(tech_terms) if tech_terms else None,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Advanced-filter helpers
# ---------------------------------------------------------------------------
def _read_advanced():
    """Read advanced-filter widget state into a (values, touched) pair."""
    country = (st.session_state.f_country or "").strip().upper() or None
    min_amount = float(st.session_state.f_min_amount) if st.session_state.f_min_amount else 0
    tech = st.session_state.f_tech
    scope = st.session_state.f_scope
    sort = st.session_state.f_sort
    low_comp = bool(st.session_state.f_low_comp)
    values = {
        "country": country,
        "technology": tech,
        "min_amount": min_amount,
        "scope": scope,
        "sort": sort,
        "risk": st.session_state.f_risk,
        "top_n": int(st.session_state.f_top_n),
        "low_competition": low_comp,
        "fast_mode": bool(st.session_state.f_fast),
    }
    touched = {
        "country": bool(country),
        "technology": tech != "Any technology",
        "min_amount": bool(min_amount),
        "scope": scope != "Open tenders only",
        "sort": sort != "Recommended",
        "low_competition": low_comp,
    }
    return values, touched


# ---------------------------------------------------------------------------
# Callbacks (keep state changes atomic and rerun-safe)
# ---------------------------------------------------------------------------
def _on_quick_question(question: str):
    """A preset click builds a COMPLETE active request, never just text."""
    req = active_request_from_preset(
        question,
        top_n=int(st.session_state.f_top_n),
        fast_mode=bool(st.session_state.f_fast),
        risk=st.session_state.f_risk,
    )
    st.session_state.active_request = req
    st.session_state.query_input = question
    st.session_state.did_analyze = True
    # Reflect the preset in the advanced controls so they stay consistent.
    st.session_state.f_tech = req["technology"]
    st.session_state.f_country = req["country"] or ""
    st.session_state.f_min_amount = int(req["min_amount"] or 0)
    st.session_state.f_scope = req["scope"]
    st.session_state.f_sort = req["sort"]
    st.session_state.f_low_comp = bool(req["low_competition"])


def _on_analyze():
    """A typed query merges inferred intent with explicitly-changed filters."""
    query = (st.session_state.query_input or "").strip()
    if not query:
        st.session_state.did_analyze = False
        st.session_state.active_request = None
        return
    values, touched = _read_advanced()
    req = build_active_request(
        query=query,
        advanced_filters=values,
        advanced_touched=touched,
        top_n=values["top_n"],
        fast_mode=values["fast_mode"],
        risk=values["risk"],
    )
    st.session_state.active_request = req
    st.session_state.did_analyze = True


def _on_reset():
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v
    st.session_state.did_analyze = False
    st.session_state["_seeded_topn"] = False


def _scope_to_kind(scope: str):
    if scope == "Open tenders only":
        return "CN"
    if scope == "Awarded contracts":
        return "CAN"
    return None


def _priorities(active):
    risk = active.get("risk", "Balanced")
    sort = active.get("sort", "Recommended")
    return Priorities(
        high_value=(sort == "Commercial Value"),
        high_win=(sort == "Win Probability"),
        strategic_fit=(sort in ("Strategic Fit", "Microsoft Opportunity Score", "Recommended")),
        relevance_weight=0.55 if risk == "Aggressive" else (0.35 if risk == "Conservative" else 0.45),
    )


# ---------------------------------------------------------------------------
# Retrieval with graceful fallback
# ---------------------------------------------------------------------------
def _fetch_for_request(cfg, cfg_key, req):
    """Fetch candidate notices for one request variant. Returns list or raises."""
    tech = TECH_AREAS.get(req.get("technology") or "Any technology", {"divisions": [], "terms": []})
    notice_kind = _scope_to_kind(req.get("scope"))
    return cached_candidates(
        cfg_key,
        req.get("country"),
        req.get("min_amount"),
        notice_kind,
        tuple(tech["divisions"]),
        tuple(tech["terms"]),
        cfg.candidate_limit,
    )


def handle_opportunities(cfg, active):
    cfg_key = f"{cfg.server_hostname}:{cfg.warehouse_id}"
    query = active.get("query", "")
    fallback_note = ""
    used_request = active

    with st.spinner("Querying revised Gold tables and scoring opportunities…"):
        try:
            candidates = _fetch_for_request(cfg, cfg_key, active)
        except da.DataAccessError as exc:
            st.warning(f"Could not load opportunities: {exc}")
            return active, ""

        # Graceful fallback: try declared broadening steps until results appear.
        if not candidates:
            for step in build_fallback_plan(active):
                try:
                    candidates = _fetch_for_request(cfg, cfg_key, step["request"])
                except da.DataAccessError:
                    continue
                if candidates:
                    used_request = step["request"]
                    fallback_note = f"Broadened the search: {step['note']}."
                    break

        # Prefer clustered buyer personas for Profile Type and single-bidder probability.
        # Fall back to the legacy buyer_profiles table if clustered outputs are unavailable.
        buyer_lookup = cached_clustered_buyer_lookup(cfg_key, used_request.get("country"))
        if not buyer_lookup:
            buyer_lookup = cached_buyer_lookup(cfg_key, used_request.get("country"))

        notice_ids = tuple(sorted({str(c.get("notice_id") or "").strip() for c in candidates if c.get("notice_id")}))
        prediction_lookup = cached_cn_prediction_lookup(cfg_key, notice_ids)
        candidates = _attach_cn_predictions(candidates, prediction_lookup)

    ui.active_request_bar(st, used_request, fallback_note=fallback_note)

    if not candidates:
        applied = _applied_summary(active)
        ui.empty_state(
            st,
            "No opportunities matched even after broadening the search. "
            f"Filters applied: {applied}. Try clearing the country, lowering the "
            "minimum amount, or selecting 'Any technology'.",
        )
        return used_request, fallback_note

    ranked = rank_opportunities(
        query=query,
        notices=candidates,
        buyer_lookup=buyer_lookup,
        priorities=_priorities(used_request),
        top_n=used_request.get("top_n", 10),
        fast_mode=used_request.get("fast_mode", True),
        sort_mode=used_request.get("sort", "Recommended"),
    )
    cards = [fmt.source_card(r) for r in ranked]
    summary = fmt.executive_summary(cards, ROUTE_OPPORTUNITIES, query)
    if fallback_note:
        summary = (
            "No exact matches were found for the original request. " + fallback_note + " " + summary
        )

    evidence = fmt.build_evidence_block(cards)
    explanation = llm_mod.explain(query, evidence, summary)

    ui.exec_summary(st, explanation["text"], deterministic=not explanation.get("used_llm"))
    if explanation.get("error"):
        st.caption(explanation["error"])

    ui.opportunity_overview(st, cards)
    ui.section_title(
        st,
        "Ranked pursuit list",
        f"Top {len(cards)} recommendations",
        "Cards are ordered by the selected strategy and include score drivers, buyer persona and ML competition probability.",
    )
    for card in cards:
        ui.render_opportunity_card(st, card)
    ui.render_profile_treemap(st, cards)
    return used_request, fallback_note


def handle_buyers(cfg, active):
    cfg_key = f"{cfg.server_hostname}:{cfg.warehouse_id}"
    fallback_note = ""
    with st.spinner("Ranking strategically attractive buyers…"):
        buyers = []
        try:
            buyers = da.fetch_buyer_profiles(cfg, country=active.get("country"), limit=300)
        except da.DataAccessError:
            buyers = []
        ranked = []
        if buyers:
            ranked = rank_buyers(buyers, top_n=active.get("top_n", 10))
        else:
            # Fallback: infer buyer attractiveness from notices_unified.
            try:
                notices = _fetch_for_request(cfg, cfg_key, {**active, "scope": "Both"})
            except da.DataAccessError as exc:
                st.warning(f"Could not load buyer data: {exc}")
                ui.active_request_bar(st, active)
                return active, ""
            if notices:
                ranked = infer_buyers_from_notices(notices, top_n=active.get("top_n", 10))
                fallback_note = ("Buyer profiles were unavailable, so attractiveness was "
                                 "derived from recent notices.")

    ui.active_request_bar(st, active, fallback_note=fallback_note)
    ui.buyer_route_note(st)

    if not ranked:
        ui.empty_state(st, "No buyer data available for this filter. Try removing the country filter.")
        return active, fallback_note

    buyer_cards = [fmt.format_buyer_card(b, i) for i, b in enumerate(ranked, start=1)]
    ui.buyer_overview(st, buyer_cards)
    ui.section_title(
        st,
        "Account targeting",
        "Buyers Microsoft should prioritize",
        "Ranked by recurring spend, technology concentration and openness to competition.",
    )
    for b in buyer_cards:
        ui.render_buyer_card(st, b)
    return active, fallback_note


def handle_awarded(cfg, active):
    query = active.get("query", "")
    tech = TECH_AREAS.get(active.get("technology") or "Any technology", {"divisions": [], "terms": []})
    single_only = bool(active.get("low_competition"))
    fallback_note = ""
    used = active

    with st.spinner("Loading awarded contracts (market intelligence)…"):
        try:
            awards = da.fetch_awards(
                cfg,
                country=active.get("country"),
                cpv_divisions=tech["divisions"] or None,
                min_amount=active.get("min_amount") or None,
                single_bidder_only=single_only,
                limit=active.get("top_n", 10) * 3,
            )
        except da.DataAccessError as exc:
            st.warning(f"Could not load awarded contracts: {exc}")
            ui.active_request_bar(st, active)
            return active, ""

        # Fallback: no single-bidder rows -> lowest available competition.
        if not awards and single_only:
            try:
                awards = da.fetch_awards(
                    cfg,
                    country=active.get("country"),
                    cpv_divisions=tech["divisions"] or None,
                    min_amount=active.get("min_amount") or None,
                    single_bidder_only=False,
                    order_by_competition=True,
                    limit=active.get("top_n", 10) * 3,
                )
            except da.DataAccessError:
                awards = []
            if awards:
                used = {**active, "low_competition": False}
                fallback_note = ("No single-bidder awards were found, so the least-contested "
                                 "awarded contracts are shown instead.")

    ui.active_request_bar(st, used, fallback_note=fallback_note)
    st.info("These are **awarded contracts** — market intelligence, not open bids.")

    if not awards:
        ui.empty_state(st, "No awarded contracts match these filters. Try a broader scope or lower amount.")
        return used, fallback_note

    shown_awards = awards[: active.get("top_n", 10)]
    ui.market_intel_overview(st, shown_awards)
    ui.section_title(
        st,
        "Competitive intelligence",
        "Awarded contracts with competition signals",
        "Use these awards to understand incumbents, buyer behaviour and low-competition patterns.",
    )
    for a in shown_awards:
        amount = fmt.format_amount(a.get("award_value_eur"), "EUR")
        ui.market_intel_card(st, a, amount)
    return used, fallback_note


def _applied_summary(active):
    bits = []
    if active.get("technology") and active["technology"] != "Any technology":
        bits.append(active["technology"])
    if active.get("country"):
        bits.append(active["country"])
    if active.get("min_amount"):
        bits.append(f"≥ €{float(active['min_amount']):,.0f}")
    bits.append(active.get("scope") or "Open tenders only")
    return ", ".join(bits)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    cfg = get_config()
    _init_state(cfg)
    ui.inject_css(st)
    ui.hero(st)

    cfg_key = f"{cfg.server_hostname}:{cfg.warehouse_id}"
    health = cached_health(cfg_key)
    ui.status_chips(st, health, cfg.llm_provider)

    ui.command_center(st)

    # Business presets — clicking builds a full active request via callback.
    ui.quick_question_header(st)
    cols = st.columns(4)
    for i, q in enumerate(QUICK_QUESTIONS):
        cols[i % 4].button(q, key=f"qq_{i}", use_container_width=True,
                           on_click=_on_quick_question, args=(q,))

    st.text_input(
        "Your question",
        key="query_input",
        placeholder="e.g. Show cloud opportunities above 500k in Spain",
        label_visibility="collapsed",
    )
    c1, c2 = st.columns([1.25, 5])
    c1.button("Analyze", type="primary", on_click=_on_analyze, use_container_width=True)
    c2.caption("Tip: try 'show cybersecurity opportunities in Spain above 500k' or use the presets above.")

    # Advanced filters live in-page (no sidebar anywhere in the app).
    ui.advanced_filters(st, {"top_n": st.session_state.f_top_n}, TECH_AREA_LABELS,
                        SORT_MODES, _on_reset)

    active = st.session_state.active_request
    if not (st.session_state.did_analyze and active):
        ui.section_title(
            st,
            "Ready when you are",
            "Pick a preset or ask a custom question",
            "Results will appear here as polished recommendation cards with score drivers and next actions.",
        )
        st.stop()

    if not health.get("ok"):
        ui.active_request_bar(st, active)
        st.error(
            "Not connected to the SQL Warehouse, so live scoring is unavailable. "
            "Verify the bound 'sql_warehouse' resource and SELECT grants on the revised Gold tables."
        )
        st.stop()

    route = active.get("route", ROUTE_OPPORTUNITIES)
    if route == ROUTE_BUYERS:
        handle_buyers(cfg, active)
    elif route == ROUTE_AWARDED:
        handle_awarded(cfg, active)
    else:
        handle_opportunities(cfg, active)


if __name__ == "__main__":
    main()
