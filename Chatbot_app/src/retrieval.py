"""Retrieval and ranking for the Microsoft Bid Prioritization Assistant.

No Databricks dependency here — this operates on already-fetched candidate rows
so it is fully unit-testable. It does three things:

1. Route the user's query to an intent (opportunities / buyers / awarded).
2. Compute a text-relevance score for each candidate (keyword by default,
   optional TF-IDF when scikit-learn is available and Fast mode is off).
3. Blend relevance with the Microsoft Opportunity Score (and user priorities)
   into a final ranking.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from .opportunity_scoring import ScoreResult, score_opportunity

_TOKEN = re.compile(r"[a-z0-9]+")

# Intent route names
ROUTE_OPPORTUNITIES = "opportunities"
ROUTE_BUYERS = "buyers"
ROUTE_AWARDED = "awarded"

_BUYER_HINTS = ("buyer", "buyers", "customer", "contracting authority", "authorities", "agencies")
_AWARDED_HINTS = ("awarded", "winner", "winners", "won", "market intelligence", "who won", "award notice")
_OPP_HINTS = ("opportunit", "tender", "bid", "pursue", "rfp", "open", "should we")


def route_intent(query: str) -> str:
    """Classify the query into one of three routes."""
    q = (query or "").lower()
    if any(h in q for h in _BUYER_HINTS):
        return ROUTE_BUYERS
    if any(h in q for h in _AWARDED_HINTS):
        return ROUTE_AWARDED
    # default to opportunities
    return ROUTE_OPPORTUNITIES


# ---------------------------------------------------------------------------
# Technology areas: label -> (CPV divisions, OR-group search terms)
# Used by both query-intent inference and SQL candidate fetching.
# ---------------------------------------------------------------------------
TECH_AREAS: Dict[str, Dict[str, Any]] = {
    "Any technology": {"divisions": [], "terms": []},
    "Cloud & Azure": {
        "divisions": ["72", "48"],
        "terms": ["cloud", "azure", "migration", "infrastructure", "platform", "data center", "datacenter"],
    },
    "Cybersecurity": {
        "divisions": ["72", "48", "35"],
        "terms": ["cyber", "cybersecurity", "security", "firewall", "identity", "protection"],
    },
    "AI, Data & Analytics": {
        "divisions": ["72", "48"],
        "terms": ["ai", "artificial intelligence", "machine learning", "data", "analytics"],
    },
    "Software & Licensing": {
        "divisions": ["48"],
        "terms": ["software", "license", "licence", "licensing", "saas", "application", "platform"],
    },
    "IT Services": {
        "divisions": ["72"],
        "terms": ["it services", "consulting", "implementation", "support"],
    },
    "Computing Hardware": {
        "divisions": ["30", "32"],
        "terms": ["hardware", "devices", "equipment", "computing"],
    },
}

TECH_AREA_LABELS = list(TECH_AREAS.keys())

# Sort modes (label). "Recommended" keeps the blended ranking.
SORT_MODES = [
    "Recommended",
    "Microsoft Opportunity Score",
    "Strategic Fit",
    "Commercial Value",
    "Win Probability",
    "Buyer Attractiveness",
    "Urgency",
    "Deadline Soonest",
]

# Country phrase -> ISO3 code (matches dim_country in revised Gold).
_COUNTRY_MAP = {
    "spain": "ESP", "spanish": "ESP", "españa": "ESP", "espana": "ESP",
    "france": "FRA", "french": "FRA",
    "germany": "DEU", "german": "DEU",
    "italy": "ITA", "italian": "ITA",
    "portugal": "PRT", "portuguese": "PRT",
    "netherlands": "NLD", "dutch": "NLD",
    "belgium": "BEL", "belgian": "BEL",
    "ireland": "IRL", "irish": "IRL",
}

# Ordered technology matchers: (label, trigger terms). Security before cloud.
_TECH_TRIGGERS = [
    ("Cybersecurity", ["cybersecurity", "cyber", "security", "firewall", "identity", "protection"]),
    ("Cloud & Azure", ["cloud", "azure", "migration", "infrastructure", "data center", "datacenter"]),
    ("AI, Data & Analytics", ["artificial intelligence", " ai ", "machine learning", "analytics", "data "]),
    ("Software & Licensing", ["software", "license", "licence", "licensing", "saas", "application"]),
    ("IT Services", ["it services", "consulting", "implementation", "support"]),
    ("Computing Hardware", ["hardware", "devices", "equipment", "computing"]),
]


def _infer_amount(q: str) -> Optional[float]:
    """Parse a minimum amount from natural language."""
    # million forms: "2.5m", "1 million"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m\b|million|millones?|mn\b)", q)
    if m:
        return float(m.group(1).replace(",", ".")) * 1_000_000
    # thousand forms: "500k", "500 thousand"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:k\b|thousand|mil\b)", q)
    if m:
        return float(m.group(1).replace(",", ".")) * 1_000
    # explicit grouped numbers near a value cue: "above 500,000" / "over 500.000"
    m = re.search(r"(?:above|over|more than|at least|>=|min(?:imum)?)\s*[€$£]?\s*([\d.,]{4,})", q)
    if m:
        digits = re.sub(r"[.,]", "", m.group(1))
        if digits.isdigit():
            return float(digits)
    return None


def infer_query_intent(query: str) -> Dict[str, Any]:
    """Infer technology, country, amount, scope, competition and sort from text.

    Returns a dict with keys: technology, country, min_amount, scope,
    low_competition, sort. Unset values are None so a later merge step can
    decide whether sidebar or query intent wins.
    """
    q = f" {(query or '').lower()} "
    intent: Dict[str, Any] = {
        "technology": None,
        "country": None,
        "min_amount": None,
        "scope": None,
        "low_competition": None,
        "sort": None,
    }

    for label, terms in _TECH_TRIGGERS:
        if any(t in q for t in terms):
            intent["technology"] = label
            break

    for phrase, code in _COUNTRY_MAP.items():
        if phrase in q:
            intent["country"] = code
            break

    amt = _infer_amount(q)
    if amt is not None:
        intent["min_amount"] = amt

    if any(w in q for w in ["awarded", "winner", "won", "market intelligence", "award notice"]):
        intent["scope"] = "Awarded contracts"
    elif "both" in q or " all " in q:
        intent["scope"] = "Both"
    elif any(w in q for w in ["open", "tender", "bid", "pursue", "opportunit"]):
        intent["scope"] = "Open tenders only"

    if any(w in q for w in ["single bidder", "one bidder", "low competition", "few bidders", "single-bidder"]):
        intent["low_competition"] = True

    if any(w in q for w in ["highest value", "biggest", "largest", "high-value", "high value"]):
        intent["sort"] = "Commercial Value"
    elif any(w in q for w in ["most winnable", "win probability", "winnable"]):
        intent["sort"] = "Win Probability"
    elif any(w in q for w in ["urgent", "deadline", "closing soon", "closes soon"]):
        intent["sort"] = "Deadline Soonest"
    elif any(w in q for w in ["strategic buyer", "buyer attractiveness"]):
        intent["sort"] = "Buyer Attractiveness"
    elif any(w in q for w in ["best fit", "microsoft fit", "prioritize", "priority"]):
        intent["sort"] = "Microsoft Opportunity Score"

    return intent


def merge_sidebar_and_query_intent(
    sidebar_filters: Dict[str, Any],
    query_intent: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge sidebar filters (base) with query intent (fills defaults).

    Sidebar wins when the user manually set a non-default value. Query intent
    overrides only when the sidebar value is still the default ("Any"/0/None).
    """
    merged = dict(sidebar_filters)

    if sidebar_filters.get("technology", "Any technology") == "Any technology" and query_intent.get("technology"):
        merged["technology"] = query_intent["technology"]

    if not sidebar_filters.get("country") and query_intent.get("country"):
        merged["country"] = query_intent["country"]

    if not sidebar_filters.get("min_amount") and query_intent.get("min_amount"):
        merged["min_amount"] = query_intent["min_amount"]

    if query_intent.get("scope") and sidebar_filters.get("scope", "Open tenders only") == "Open tenders only":
        merged["scope"] = query_intent["scope"]

    if query_intent.get("low_competition"):
        merged["low_competition"] = True
    merged.setdefault("low_competition", bool(sidebar_filters.get("low_competition")))

    if query_intent.get("sort") and sidebar_filters.get("sort", "Recommended") == "Recommended":
        merged["sort"] = query_intent["sort"]
    merged.setdefault("sort", sidebar_filters.get("sort", "Recommended"))

    return merged


# ---------------------------------------------------------------------------
# QUERY PRESETS — the single source of truth for the quick-question buttons.
#
# Each preset is a full, self-contained request specification. Clicking a preset
# builds a complete ActiveRequest from this definition (never just text). Every
# preset declares a `fallback_strategy`: an ordered list of broadening steps the
# fallback planner can apply when an exact match returns nothing.
#
# Fallback step vocabulary (applied in order, one at a time, until results
# appear):
#   "lower_amount"       -> drop the minimum-amount filter to 0
#   "broaden_technology" -> widen the technology filter to IT-adjacent CPV 48/72
#   "remove_country"     -> drop the country filter
#   "lowest_competition" -> for awarded: use the lowest available num_tenders
#                           instead of requiring single-bidder (num_tenders == 1)
#   "infer_buyers"       -> for buyers: derive attractiveness from notices_unified
#                           when buyer_profiles is unavailable
# ---------------------------------------------------------------------------
FALLBACK_LOWER_AMOUNT = "lower_amount"
FALLBACK_BROADEN_TECH = "broaden_technology"
FALLBACK_REMOVE_COUNTRY = "remove_country"
FALLBACK_LOWEST_COMPETITION = "lowest_competition"
FALLBACK_INFER_BUYERS = "infer_buyers"

# Technology label used when broadening toward IT-adjacent CPV 48/72.
BROAD_TECH_LABEL = "IT Services"

QUERY_PRESETS: Dict[str, Dict[str, Any]] = {
    "Top Microsoft-fit opportunities": {
        "label": "Top Microsoft-fit opportunities",
        "query": "Top Microsoft-fit open opportunities to prioritize",
        "route": ROUTE_OPPORTUNITIES,
        "technology": "Any technology",
        "country": None,
        "min_amount": 0,
        "scope": "Open tenders only",
        "sort": "Microsoft Opportunity Score",
        "low_competition": False,
        "fallback_strategy": [],
    },
    "Cloud opportunities above 500k": {
        "label": "Cloud opportunities above 500k",
        "query": "Cloud and Azure opportunities above 500k",
        "route": ROUTE_OPPORTUNITIES,
        "technology": "Cloud & Azure",
        "country": None,
        "min_amount": 500_000,
        "scope": "Open tenders only",
        "sort": "Microsoft Opportunity Score",
        "low_competition": False,
        "fallback_strategy": [FALLBACK_LOWER_AMOUNT, FALLBACK_BROADEN_TECH],
    },
    "Cybersecurity opportunities": {
        "label": "Cybersecurity opportunities",
        "query": "Cybersecurity and security opportunities",
        "route": ROUTE_OPPORTUNITIES,
        "technology": "Cybersecurity",
        "country": None,
        "min_amount": 0,
        "scope": "Open tenders only",
        "sort": "Microsoft Opportunity Score",
        "low_competition": False,
        "fallback_strategy": [FALLBACK_BROADEN_TECH],
    },
    "Best opportunities in Spain": {
        "label": "Best opportunities in Spain",
        "query": "Best public-sector opportunities in Spain",
        "route": ROUTE_OPPORTUNITIES,
        "technology": "Any technology",
        "country": "ESP",
        "min_amount": 0,
        "scope": "Open tenders only",
        "sort": "Recommended",
        "low_competition": False,
        "fallback_strategy": [FALLBACK_REMOVE_COUNTRY],
    },
    "High-value open tenders": {
        "label": "High-value open tenders",
        "query": "High-value open tenders",
        "route": ROUTE_OPPORTUNITIES,
        "technology": "Any technology",
        "country": None,
        "min_amount": 1_000_000,
        "scope": "Open tenders only",
        "sort": "Commercial Value",
        "low_competition": False,
        "fallback_strategy": [FALLBACK_LOWER_AMOUNT],
    },
    "Which buyers should Microsoft prioritize?": {
        "label": "Which buyers should Microsoft prioritize?",
        "query": "Which buyers should Microsoft prioritize?",
        "route": ROUTE_BUYERS,
        "technology": "Any technology",
        "country": None,
        "min_amount": 0,
        "scope": "Open tenders only",
        "sort": "Buyer Attractiveness",
        "low_competition": False,
        "fallback_strategy": [FALLBACK_INFER_BUYERS],
    },
    "Awarded contracts with low competition": {
        "label": "Awarded contracts with low competition",
        "query": "Awarded contracts with low competition (market intelligence)",
        "route": ROUTE_AWARDED,
        "technology": "Any technology",
        "country": None,
        "min_amount": 0,
        "scope": "Awarded contracts",
        "sort": "Commercial Value",
        "low_competition": True,
        "fallback_strategy": [FALLBACK_LOWEST_COMPETITION],
    },
}

_PRESET_ORDER = [
    "Top Microsoft-fit opportunities",
    "Cloud opportunities above 500k",
    "Cybersecurity opportunities",
    "Which buyers should Microsoft prioritize?",
    "High-value open tenders",
    "Awarded contracts with low competition",
    "Best opportunities in Spain",
]
QUERY_PRESETS = {k: QUERY_PRESETS[k] for k in _PRESET_ORDER if k in QUERY_PRESETS}
QUICK_QUESTIONS = list(QUERY_PRESETS.keys())

# Back-compat: a thin overrides view of the presets (route + non-default fields).
QUICK_QUESTION_MAP: Dict[str, Dict[str, Any]] = {
    name: {
        k: v
        for k, v in {
            "route": p["route"] if p["route"] != ROUTE_OPPORTUNITIES else None,
            "technology": p["technology"] if p["technology"] != "Any technology" else None,
            "country": p["country"],
            "min_amount": p["min_amount"] if p["min_amount"] else None,
            "scope": p["scope"],
            "sort": p["sort"],
            "low_competition": True if p["low_competition"] else None,
        }.items()
        if v is not None
    }
    for name, p in QUERY_PRESETS.items()
}


def get_preset(question: str) -> Optional[Dict[str, Any]]:
    """Return the full preset definition for a quick question, or None."""
    p = QUERY_PRESETS.get(question)
    return dict(p) if p else None


def quick_question_filters(question: str) -> Dict[str, Any]:
    """Return filter overrides for a quick question (empty dict if unknown)."""
    return dict(QUICK_QUESTION_MAP.get(question, {}))


# ---------------------------------------------------------------------------
# Clustered buyer-profile matching. Profile Type for recommendations comes from
# workspace.gold.buyer_profiles_clustered + workspace.gold.cluster_profiles.
# These helpers stay Databricks-free so they can be unit-tested locally.
# ---------------------------------------------------------------------------
def normalize_buyer_name(value: Any) -> str:
    """Normalise buyer names for deterministic joins without slow fuzzy matching."""
    text = str(value or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _cluster_id_key(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        f = float(value)
        if f.is_integer():
            return str(int(f))
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def build_clustered_buyer_lookup(
    clustered_buyers: List[Dict[str, Any]],
    cluster_profiles: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build lookup by `normalised buyer|country` plus unique buyer-name fallback.

    The returned profile rows include `cluster_label` and `profile_type` from
    cluster_profiles whenever available. If a cluster lacks a label, the profile
    type becomes `Cluster {cluster_id}`.
    """
    cluster_profiles = cluster_profiles or []
    label_by_cluster: Dict[str, Dict[str, Any]] = {}
    for cp in cluster_profiles:
        cid = _cluster_id_key(cp.get("cluster_id"))
        if cid is not None:
            label_by_cluster[cid] = dict(cp)

    by_key: Dict[str, Dict[str, Any]] = {}
    by_name_candidates: Dict[str, List[Dict[str, Any]]] = {}

    for row in clustered_buyers or []:
        name_norm = normalize_buyer_name(row.get("buyer_name"))
        if not name_norm:
            continue
        country = str(row.get("buyer_country") or "").strip().upper()
        cid = _cluster_id_key(row.get("cluster_id"))
        enriched = dict(row)
        if cid and cid in label_by_cluster:
            enriched.update({k: v for k, v in label_by_cluster[cid].items() if v is not None})
        label = enriched.get("cluster_label")
        if label:
            enriched["profile_type"] = str(label).strip()
        elif cid:
            enriched["profile_type"] = f"Cluster {cid}"
        else:
            enriched["profile_type"] = "Unclustered buyer"
        if cid is not None:
            enriched["cluster_id"] = cid

        if country:
            by_key[f"{name_norm}|{country}"] = enriched
        by_name_candidates.setdefault(name_norm, []).append(enriched)

    # Add buyer-name-only fallback only when the name is unique.
    for name_norm, rows in by_name_candidates.items():
        unique_countries = {str(r.get("buyer_country") or "").strip().upper() for r in rows}
        if len(rows) == 1 or len(unique_countries) == 1:
            by_key[name_norm] = rows[0]
    return by_key


def find_buyer_profile(notice: Dict[str, Any], buyer_lookup: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find a clustered or legacy buyer profile for a notice."""
    if not buyer_lookup:
        return None
    name_norm = normalize_buyer_name(notice.get("buyer_name"))
    if not name_norm:
        return None
    country = str(notice.get("buyer_country") or "").strip().upper()
    if country:
        hit = buyer_lookup.get(f"{name_norm}|{country}")
        if hit:
            return hit
    # Backward compatible: previous app keyed buyer profiles by stripped lower name.
    return buyer_lookup.get(name_norm) or buyer_lookup.get(str(notice.get("buyer_name") or "").strip().lower())


# ---------------------------------------------------------------------------
# ActiveRequest — one unified object that drives retrieval, scoring, sorting and
# display. Presets, manual queries and advanced filters all collapse into this.
# ---------------------------------------------------------------------------
SOURCE_PRESET = "preset"
SOURCE_MANUAL = "manual"
SOURCE_ADVANCED = "advanced"

_ACTIVE_DEFAULTS: Dict[str, Any] = {
    "query": "",
    "route": ROUTE_OPPORTUNITIES,
    "technology": "Any technology",
    "country": None,
    "min_amount": 0,
    "scope": "Open tenders only",
    "sort": "Recommended",
    "low_competition": False,
    "risk": "Balanced",
    "top_n": 10,
    "fast_mode": True,
    "source": SOURCE_MANUAL,
    "fallback_strategy": [],
}


def new_active_request(**overrides: Any) -> Dict[str, Any]:
    """Build a fully-populated active request dict from defaults + overrides."""
    req = dict(_ACTIVE_DEFAULTS)
    req["fallback_strategy"] = []
    for k, v in overrides.items():
        if k in req or k in ("fallback_strategy", "source"):
            req[k] = v
    # Normalise types defensively so downstream never crashes.
    req["country"] = (str(req["country"]).strip().upper() or None) if req["country"] else None
    try:
        req["min_amount"] = float(req["min_amount"]) if req["min_amount"] else 0.0
    except (TypeError, ValueError):
        req["min_amount"] = 0.0
    req["low_competition"] = bool(req["low_competition"])
    req["fast_mode"] = bool(req["fast_mode"])
    try:
        req["top_n"] = int(req["top_n"])
    except (TypeError, ValueError):
        req["top_n"] = 10
    return req


def active_request_from_preset(
    question: str,
    *,
    top_n: int = 10,
    fast_mode: bool = True,
    risk: str = "Balanced",
) -> Dict[str, Any]:
    """Build a complete active request from a quick-question preset.

    Returns a manual-style request if the question is not a known preset, so the
    caller can always proceed safely.
    """
    preset = QUERY_PRESETS.get(question)
    if not preset:
        return build_active_request(query=question, top_n=top_n, fast_mode=fast_mode, risk=risk)
    return new_active_request(
        query=preset["query"],
        route=preset["route"],
        technology=preset["technology"],
        country=preset["country"],
        min_amount=preset["min_amount"],
        scope=preset["scope"],
        sort=preset["sort"],
        low_competition=preset["low_competition"],
        risk=risk,
        top_n=top_n,
        fast_mode=fast_mode,
        source=SOURCE_PRESET,
        fallback_strategy=list(preset["fallback_strategy"]),
    )


def build_active_request(
    *,
    query: str,
    advanced_filters: Optional[Dict[str, Any]] = None,
    advanced_touched: Optional[Dict[str, bool]] = None,
    top_n: int = 10,
    fast_mode: bool = True,
    risk: str = "Balanced",
) -> Dict[str, Any]:
    """Build an active request from a typed query, merging advanced filters.

    Intent is inferred from the text. Advanced-filter values only override that
    intent when the user has explicitly changed them (``advanced_touched``).
    Route is inferred from the text. The result is a complete request object.
    """
    advanced_filters = advanced_filters or {}
    advanced_touched = advanced_touched or {}
    intent = infer_query_intent(query)
    route = route_intent(query)

    def pick(field: str, intent_val: Any, default: Any) -> Any:
        # Advanced wins only if the user explicitly changed that control.
        if advanced_touched.get(field) and advanced_filters.get(field) is not None:
            return advanced_filters[field]
        if intent_val is not None:
            return intent_val
        if field in advanced_filters and advanced_filters[field] is not None:
            return advanced_filters[field]
        return default

    technology = pick("technology", intent.get("technology"), "Any technology")
    country = pick("country", intent.get("country"), None)
    min_amount = pick("min_amount", intent.get("min_amount"), 0)
    scope = pick("scope", intent.get("scope"), "Open tenders only")
    sort = pick("sort", intent.get("sort"), "Recommended")
    low_comp = bool(
        intent.get("low_competition")
        or (advanced_touched.get("low_competition") and advanced_filters.get("low_competition"))
    )

    if route == ROUTE_AWARDED:
        scope = "Awarded contracts"

    return new_active_request(
        query=query,
        route=route,
        technology=technology,
        country=country,
        min_amount=min_amount,
        scope=scope,
        sort=sort,
        low_competition=low_comp,
        risk=risk,
        top_n=top_n,
        fast_mode=fast_mode,
        source=SOURCE_ADVANCED if advanced_touched else SOURCE_MANUAL,
        fallback_strategy=[],
    )


# ---------------------------------------------------------------------------
# Fallback planning. Produces an ordered list of progressively-broadened
# request variants. The caller tries each in turn and stops at the first that
# yields results, surfacing a clear, labelled explanation to the user.
# ---------------------------------------------------------------------------
def build_fallback_plan(active: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a list of {request, note} broadening steps after the exact request.

    The exact request itself is NOT included — only the broadened alternatives,
    applied cumulatively in the preset's declared order. Each step keeps every
    other filter intact so we never silently drop the user's intent.
    """
    steps = active.get("fallback_strategy") or []
    plan: List[Dict[str, Any]] = []
    current = dict(active)
    for step in steps:
        nxt = dict(current)
        note: Optional[str] = None
        if step == FALLBACK_LOWER_AMOUNT and current.get("min_amount"):
            nxt["min_amount"] = 0.0
            note = "lowered the minimum-value threshold"
        elif step == FALLBACK_BROADEN_TECH and current.get("technology") not in (None, "Any technology", BROAD_TECH_LABEL):
            nxt["technology"] = BROAD_TECH_LABEL
            note = "broadened the technology filter to IT services / CPV 48 & 72"
        elif step == FALLBACK_REMOVE_COUNTRY and current.get("country"):
            nxt["country"] = None
            note = "removed the country filter and looked across Europe"
        elif step == FALLBACK_LOWEST_COMPETITION and current.get("low_competition"):
            nxt["low_competition"] = False
            nxt["_lowest_competition"] = True
            note = "used the lowest available number of bidders (no single-bidder rows found)"
        elif step == FALLBACK_INFER_BUYERS:
            nxt["_infer_buyers"] = True
            note = "derived buyer attractiveness from notices (buyer profiles unavailable)"
        if note:
            nxt["source"] = "fallback"
            plan.append({"request": nxt, "note": note})
            current = nxt
    return plan


def _tokenize(text: str) -> List[str]:
    return _TOKEN.findall((text or "").lower())


def keyword_relevance(query: str, notice: Dict[str, Any]) -> float:
    """Cheap, dependency-free 0-100 relevance from token overlap."""
    q_tokens = set(_tokenize(query))
    if not q_tokens:
        return 50.0  # no query -> neutral, let opportunity score dominate
    doc = " ".join(
        str(notice.get(f) or "")
        for f in ("project_title", "description", "buyer_name", "cpv_code", "cpv_division")
    )
    d_tokens = _tokenize(doc)
    if not d_tokens:
        return 0.0
    d_set = set(d_tokens)
    overlap = q_tokens & d_set
    if not overlap:
        return 0.0
    # weight title hits more by counting raw frequency
    title_tokens = _tokenize(str(notice.get("project_title") or ""))
    title_hits = sum(1 for t in title_tokens if t in q_tokens)
    coverage = len(overlap) / len(q_tokens)
    score = 100.0 * coverage * (1.0 + 0.15 * min(title_hits, 4))
    return min(100.0, score)


def tfidf_relevance(query: str, notices: List[Dict[str, Any]]) -> Optional[List[float]]:
    """Optional TF-IDF cosine relevance. Returns None if sklearn unavailable."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        from sklearn.metrics.pairwise import linear_kernel  # type: ignore
    except Exception:
        return None
    if not query or not notices:
        return None
    docs = [
        " ".join(
            str(n.get(f) or "")
            for f in ("project_title", "description", "buyer_name", "cpv_code")
        )
        for n in notices
    ]
    try:
        vec = TfidfVectorizer(stop_words="english", max_features=4000)
        matrix = vec.fit_transform(docs + [query])
        sims = linear_kernel(matrix[-1], matrix[:-1]).flatten()
    except Exception:
        return None
    if sims.max() <= 0:
        return [0.0] * len(notices)
    norm = sims / sims.max()
    return [float(100.0 * s) for s in norm]


@dataclass
class RankedOpportunity:
    notice: Dict[str, Any]
    score_result: ScoreResult
    relevance: float
    final_rank_score: float
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = self.score_result.to_dict()
        d.update(
            {
                "relevance": round(self.relevance, 1),
                "final_rank_score": round(self.final_rank_score, 1),
                "rank": self.rank,
                "notice": self.notice,
            }
        )
        return d


@dataclass
class Priorities:
    """User-tunable ranking priorities from the sidebar."""
    high_value: bool = False
    high_win: bool = False
    strategic_fit: bool = False
    relevance_weight: float = 0.45  # weight on text relevance vs opportunity score


def _blended_weights(priorities: Priorities) -> Dict[str, float]:
    """Return component multipliers reflecting user priority toggles."""
    w = {"opportunity": 1.0, "value": 0.0, "win": 0.0, "fit": 0.0}
    if priorities.high_value:
        w["value"] += 0.5
    if priorities.high_win:
        w["win"] += 0.5
    if priorities.strategic_fit:
        w["fit"] += 0.5
    return w


def _deadline_key(ranked: "RankedOpportunity"):
    """Sort key for Deadline Soonest: parsed deadline ascending, missing last."""
    from .opportunity_scoring import _parse_date
    d = _parse_date(ranked.notice.get("submission_deadline"))
    # date.max for missing so they sort last; return ordinal for comparability
    return d.toordinal() if d else 10**9


_SORT_COMPONENT = {
    "Microsoft Opportunity Score": lambda r: r.score_result.opportunity_score,
    "Strategic Fit": lambda r: r.score_result.components.get("strategic_fit", 0.0),
    "Commercial Value": lambda r: r.score_result.components.get("commercial_value", 0.0),
    "Win Probability": lambda r: r.score_result.components.get("win_probability", 0.0),
    "Buyer Attractiveness": lambda r: r.score_result.components.get("buyer_attractiveness", 0.0),
    "Urgency": lambda r: r.score_result.components.get("urgency", 0.0),
}


def apply_sort(ranked: List["RankedOpportunity"], sort_mode: str) -> List["RankedOpportunity"]:
    """Reorder ranked opportunities by the chosen sort mode and re-number ranks.

    'Recommended' keeps the existing blended order. Never crashes on missing fields.
    """
    mode = sort_mode or "Recommended"
    items = list(ranked)
    if mode == "Recommended":
        items.sort(key=lambda r: r.final_rank_score, reverse=True)
    elif mode == "Deadline Soonest":
        items.sort(key=_deadline_key)  # ascending; missing last
    elif mode in _SORT_COMPONENT:
        keyfn = _SORT_COMPONENT[mode]
        items.sort(key=keyfn, reverse=True)
    else:
        items.sort(key=lambda r: r.final_rank_score, reverse=True)
    for idx, r in enumerate(items, start=1):
        r.rank = idx
    return items


def rank_opportunities(
    query: str,
    notices: List[Dict[str, Any]],
    buyer_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    priorities: Optional[Priorities] = None,
    top_n: int = 10,
    fast_mode: bool = True,
    today: Optional[date] = None,
    sort_mode: str = "Recommended",
) -> List[RankedOpportunity]:
    """Score and rank candidate notices, blending relevance + opportunity score.

    The blended score always drives selection of the top_n; `sort_mode` then
    controls the *display order* of that selected set (so a chosen KPI sort
    visibly reorders the cards without dropping high-relevance matches).
    """
    priorities = priorities or Priorities()
    buyer_lookup = buyer_lookup or {}

    # Relevance: TF-IDF only when not in fast mode and query present.
    relevances: Optional[List[float]] = None
    if not fast_mode and query:
        relevances = tfidf_relevance(query, notices)

    ranked: List[RankedOpportunity] = []
    bonus_w = _blended_weights(priorities)
    rw = max(0.0, min(1.0, priorities.relevance_weight))

    for i, notice in enumerate(notices):
        bp = find_buyer_profile(notice, buyer_lookup) if buyer_lookup else None
        result = score_opportunity(notice, buyer_profile=bp, today=today)

        if relevances is not None:
            rel = relevances[i]
        else:
            rel = keyword_relevance(query, notice)

        # Base blend: relevance vs opportunity score.
        base = rw * rel + (1.0 - rw) * result.opportunity_score

        # Priority bonuses (nudges, capped).
        bonus = (
            bonus_w["value"] * result.components.get("commercial_value", 0.0)
            + bonus_w["win"] * result.components.get("win_probability", 0.0)
            + bonus_w["fit"] * result.components.get("strategic_fit", 0.0)
        )
        final = base + 0.30 * bonus
        final = max(0.0, min(150.0, final))

        ranked.append(
            RankedOpportunity(
                notice=notice,
                score_result=result,
                relevance=rel,
                final_rank_score=final,
            )
        )

    # Select top_n by blended score, then apply the requested display sort.
    ranked.sort(key=lambda r: r.final_rank_score, reverse=True)
    ranked = ranked[: max(1, top_n)]
    ranked = apply_sort(ranked, sort_mode)
    return ranked


def rank_buyers(
    buyers: List[Dict[str, Any]],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Rank buyer_profiles rows by strategic attractiveness."""
    from .opportunity_scoring import buyer_attractiveness_score

    scored = []
    for b in buyers:
        score, reasons = buyer_attractiveness_score(b)
        row = dict(b)
        row["buyer_attractiveness"] = round(score, 1)
        row["reasons"] = reasons
        scored.append(row)
    scored.sort(key=lambda r: r["buyer_attractiveness"], reverse=True)
    return scored[: max(1, top_n)]


def infer_buyers_from_notices(
    notices: List[Dict[str, Any]],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Derive buyer-attractiveness rows from notices_unified.

    Fallback used when buyer_profiles is unavailable: aggregate notices by buyer
    into pseudo-profiles (contract counts, average value, dominant CPV division,
    single-bidder rate) and score them with the same attractiveness function.
    """
    from collections import defaultdict
    from .opportunity_scoring import buyer_attractiveness_score, parse_amount

    agg: Dict[str, Dict[str, Any]] = {}
    cpv_counter: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for n in notices:
        name = (n.get("buyer_name") or "").strip()
        if not name:
            continue
        a = agg.setdefault(name, {
            "buyer_name": name,
            "buyer_country": n.get("buyer_country"),
            "buyer_type": n.get("buyer_type"),
            "_total": 0,
            "_value_sum": 0.0,
            "_value_n": 0,
            "_single": 0,
            "_nt_known": 0,
        })
        a["_total"] += 1
        val = parse_amount(n.get("amount"))
        if val:
            a["_value_sum"] += val
            a["_value_n"] += 1
        nt = n.get("num_tenders")
        try:
            nt = int(nt) if nt is not None else None
        except (TypeError, ValueError):
            nt = None
        if nt is not None:
            a["_nt_known"] += 1
            if nt == 1:
                a["_single"] += 1
        div = str(n.get("cpv_division") or "").strip()[:2]
        if div:
            cpv_counter[name][div] += 1

    profiles: List[Dict[str, Any]] = []
    for name, a in agg.items():
        top_div = ""
        if cpv_counter[name]:
            top_div = max(cpv_counter[name].items(), key=lambda kv: kv[1])[0]
        avg_val = (a["_value_sum"] / a["_value_n"]) if a["_value_n"] else None
        sbr = (a["_single"] / a["_nt_known"]) if a["_nt_known"] else None
        profiles.append({
            "buyer_name": name,
            "buyer_country": a["buyer_country"],
            "buyer_type": a["buyer_type"],
            "total_contracts": a["_total"],
            "total_awarded_value_eur": a["_value_sum"] or None,
            "avg_award_value_eur": avg_val,
            "top_cpv_division": top_div or None,
            "single_bidder_rate": sbr,
            "cross_border_rate": None,
        })

    scored = []
    for b in profiles:
        score, reasons = buyer_attractiveness_score(b)
        row = dict(b)
        row["buyer_attractiveness"] = round(score, 1)
        row["reasons"] = reasons
        scored.append(row)
    scored.sort(key=lambda r: r["buyer_attractiveness"], reverse=True)
    return scored[: max(1, top_n)]
