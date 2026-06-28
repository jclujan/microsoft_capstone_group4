"""Microsoft Opportunity Score — deterministic 0-100 bid-prioritization engine.

This module contains NO Databricks dependencies so it is fully unit-testable.

The score combines six KPI components, each normalised to 0-100, then blended
with fixed weights into a final `opportunity_score`. Every component also emits
human-readable reason codes, risks and a recommended next action so the UI and
the (optional) LLM layer can explain *why* a tender is ranked where it is.

KPI components
--------------
1. strategic_fit       - alignment with Microsoft cloud/AI/security/data domains
2. commercial_value    - normalised contract value (log-damped)
3. win_probability      - realistic chance Microsoft could compete
4. buyer_attractiveness - strategic appeal of the buyer (from buyer_profiles)
5. urgency             - actionability / deadline pressure
6. data_confidence     - completeness of the underlying record
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Weights (must sum to 1.0)
# ---------------------------------------------------------------------------
WEIGHTS: Dict[str, float] = {
    "strategic_fit": 0.30,
    "commercial_value": 0.15,
    "win_probability": 0.20,
    "buyer_attractiveness": 0.15,
    "urgency": 0.10,
    "data_confidence": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "WEIGHTS must sum to 1.0"

# ---------------------------------------------------------------------------
# Microsoft strategic keyword map (term -> weight)
# ---------------------------------------------------------------------------
MS_KEYWORDS: Dict[str, float] = {
    "cloud": 3.0,
    "azure": 4.0,
    "software": 2.0,
    "cyber": 3.0,
    "cybersecurity": 3.5,
    "security": 2.0,
    "artificial intelligence": 4.0,
    " ai ": 3.0,
    "machine learning": 3.0,
    "data": 2.0,
    "analytics": 2.5,
    "digital transformation": 3.0,
    "infrastructure": 2.0,
    "it services": 3.0,
    "information technology": 2.5,
    "saas": 3.0,
    "crm": 2.5,
    "erp": 2.5,
    "migration": 2.0,
    "licen": 2.0,            # licence / license / licensing
    "public sector": 1.5,
    "education": 1.5,
    "healthcare": 1.5,
    "server": 1.5,
    "datacenter": 2.5,
    "data center": 2.5,
    "network": 1.5,
    "microsoft": 2.5,
    "office 365": 3.0,
    "microsoft 365": 3.5,
    "windows": 2.0,
    "copilot": 3.5,
}

# CPV divisions especially relevant to Microsoft, with a fit boost (0-100 scale).
CPV_DIVISION_BOOST: Dict[str, float] = {
    "48": 40.0,   # Software package and information systems
    "72": 40.0,   # IT services: consulting, software development, Internet, support
    "30": 25.0,   # Office and computing machinery / equipment
    "32": 20.0,   # Telecommunications / communications equipment
    "31": 8.0,    # Electrical machinery (some IT overlap)
    "35": 6.0,    # Security / defence equipment (cyber overlap)
}

# Opportunity-category fallback used when an open tender buyer has no historical
# clustered buyer persona. This keeps the UI/treemap useful while preserving the
# rule that true Buyer Profile Type comes from buyer_profiles_clustered +
# cluster_profiles when a buyer match exists.
OPPORTUNITY_PROFILE_RULES = [
    ("Cybersecurity", ["cybersecurity", "cyber", "security", "firewall", "identity", "protection", "soc", "siem"]),
    ("Cloud & Azure", ["cloud", "azure", "migration", "infrastructure", "data center", "datacenter", "hosting"]),
    ("AI, Data & Analytics", ["artificial intelligence", "machine learning", "analytics", "data platform", "business intelligence", "big data", " ai "]),
    ("Software & Licensing", ["software", "license", "licence", "licensing", "saas", "application", "platform", "crm", "erp"]),
    ("IT Services & Consulting", ["it services", "consulting", "implementation", "support", "managed services", "maintenance"]),
    ("Computing Hardware", ["hardware", "devices", "equipment", "laptop", "server", "desktop", "workstation"]),
    ("Telecommunications", ["telecommunication", "telecom", "network", "radio", "communication"]),
]

CPV_PROFILE_FALLBACK = {
    "48": "Software & Licensing",
    "72": "IT Services & Consulting",
    "30": "Computing Hardware",
    "32": "Telecommunications",
    "35": "Cybersecurity",
}

# Score bands (lower-bound inclusive, evaluated high -> low).
BANDS: List[tuple] = [
    (80.0, "High-priority bid"),
    (60.0, "Worth evaluating"),
    (45.0, "Monitor"),
    (25.0, "Low fit"),
    (0.0, "Market intelligence only"),
]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class ScoreResult:
    opportunity_score: float
    band: str
    components: Dict[str, float] = field(default_factory=dict)
    reason_codes: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    next_action: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_score": round(self.opportunity_score, 1),
            "band": self.band,
            "components": {k: round(v, 1) for k, v in self.components.items()},
            "reason_codes": list(self.reason_codes),
            "risks": list(self.risks),
            "next_action": self.next_action,
            "evidence": dict(self.evidence),
        }


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------
def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _text_of(notice: Dict[str, Any]) -> str:
    parts = [
        notice.get("project_title"),
        notice.get("description"),
        notice.get("cpv_code"),
    ]
    return " " + " ".join(str(p) for p in parts if p).lower() + " "


def parse_amount(value: Any) -> Optional[float]:
    """Parse a contract value that may be a number or a messy string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if math.isfinite(v) and v >= 0 else None
    s = str(value).strip()
    if not s:
        return None
    # Strip currency symbols / spaces but keep digits, separators and minus.
    s = re.sub(r"[^0-9.,\-]", "", s)
    if not s or s in {"-", ".", ",", "-.", "-,"}:
        return None
    has_dot = "." in s
    has_comma = "," in s
    if has_dot and has_comma:
        # The right-most separator is the decimal; the other is a thousands sep.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # European: 1.234,56
        else:
            s = s.replace(",", "")                       # US: 1,234.56
    elif has_comma:
        # Comma only: decimal if it looks like one (1-2 trailing digits), else thousands.
        if re.search(r",\d{1,2}$", s):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    # dot-only: leave as-is (treated as decimal point)
    if not s or s in {"-", ".", "-."}:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) and v >= 0 else None


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()[:10]
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def band_for(score: float) -> str:
    for lower, label in BANDS:
        if score >= lower:
            return label
    return BANDS[-1][1]


# ---------------------------------------------------------------------------
# KPI component scorers (each returns 0-100)
# ---------------------------------------------------------------------------
def strategic_fit_score(notice: Dict[str, Any]) -> tuple:
    """Return (score, reasons, matched_terms)."""
    text = _text_of(notice)
    matched: List[str] = []
    keyword_points = 0.0
    for term, weight in MS_KEYWORDS.items():
        if term in text:
            keyword_points += weight
            matched.append(term.strip())
    # Diminishing returns on keyword stacking.
    keyword_component = 100.0 * (1.0 - math.exp(-keyword_points / 6.0))

    division = str(notice.get("cpv_division") or "").strip()[:2]
    cpv_boost = CPV_DIVISION_BOOST.get(division, 0.0)

    score = _clamp(0.65 * keyword_component + cpv_boost)

    reasons: List[str] = []
    if cpv_boost >= 40:
        reasons.append(f"CPV division {division} is core Microsoft territory (software / IT services).")
    elif cpv_boost > 0:
        reasons.append(f"CPV division {division} has partial IT/technology overlap.")
    if matched:
        top = ", ".join(sorted(set(matched))[:5])
        reasons.append(f"Tender language matches Microsoft themes: {top}.")
    if not matched and cpv_boost == 0:
        reasons.append("No clear Microsoft technology signal in title, description or CPV.")
    return score, reasons, matched


def commercial_value_score(notice: Dict[str, Any]) -> tuple:
    """Log-damped value score so huge contracts don't dominate everything."""
    amount = parse_amount(notice.get("amount"))
    if amount is None:
        return 35.0, ["Contract value not disclosed; treated as neutral-low."], None
    if amount <= 0:
        return 30.0, ["Contract value is zero or unparseable."], amount
    # log scale: ~50k -> ~30, ~500k -> ~55, ~5M -> ~80, >=50M -> ~100
    score = _clamp(18.0 * math.log10(amount + 1.0) - 30.0)
    reasons = [f"Estimated/awarded value approximately {amount:,.0f}."]
    if amount >= 1_000_000:
        reasons.append("High-value opportunity (>= 1M).")
    elif amount < 50_000:
        reasons.append("Low-value opportunity; limited commercial upside.")
    return score, reasons, amount


def win_probability_score(notice: Dict[str, Any]) -> tuple:
    """Estimate realistic chance Microsoft could compete. Returns (score, reasons, risks)."""
    reasons: List[str] = []
    risks: List[str] = []
    score = 55.0  # neutral baseline

    kind = str(notice.get("notice_kind") or "").upper()
    result_code = str(notice.get("result_code") or "").lower()
    if kind == "CAN" or result_code:
        score -= 35.0
        risks.append("This is an awarded contract notice (CAN); it is not an open bid.")
    else:
        score += 10.0
        reasons.append("Open contract notice (CN) — potentially still biddable.")

    procedure = str(notice.get("procedure_type") or "").lower()
    if procedure in {"open"}:
        score += 12.0
        reasons.append("Open procedure favours new entrants like Microsoft.")
    elif procedure in {"restricted", "comp-dial", "innovation"}:
        score += 4.0
        reasons.append(f"{procedure} procedure is competitive but accessible.")
    elif procedure in {"neg-wo-call", "direct"}:
        score -= 15.0
        risks.append("Negotiated-without-call / direct award limits open competition.")

    num_tenders = notice.get("num_tenders")
    try:
        nt = int(num_tenders) if num_tenders is not None else None
    except (ValueError, TypeError):
        nt = None
    if nt is not None:
        if nt == 1:
            score -= 8.0
            risks.append("Single-bidder pattern suggests an incumbent advantage.")
        elif nt >= 5:
            score -= 5.0
            risks.append(f"Crowded field ({nt} tenders) lowers per-bidder odds.")
        else:
            score += 4.0

    # Penalise tenders that look too generic / off-strategy for Microsoft.
    fit, _, matched = strategic_fit_score(notice)
    if fit < 20 and not matched:
        score -= 10.0
        risks.append("Weak strategic fit reduces realistic win probability.")

    return _clamp(score), reasons, risks


def buyer_attractiveness_score(buyer_profile: Optional[Dict[str, Any]]) -> tuple:
    """Score a buyer's strategic appeal from a buyer_profiles row. Returns (score, reasons)."""
    if not buyer_profile:
        return 50.0, ["No buyer profile available; treated as neutral."]
    reasons: List[str] = []
    score = 40.0

    total_contracts = buyer_profile.get("total_contracts") or 0
    try:
        total_contracts = float(total_contracts)
    except (ValueError, TypeError):
        total_contracts = 0.0
    if total_contracts >= 50:
        score += 18.0
        reasons.append(f"Recurring buyer ({int(total_contracts)} historical contracts).")
    elif total_contracts >= 10:
        score += 10.0
        reasons.append(f"Active buyer ({int(total_contracts)} contracts).")
    elif total_contracts > 0:
        score += 3.0

    avg_val = buyer_profile.get("avg_award_value_eur")
    avg_val = parse_amount(avg_val)
    if avg_val:
        if avg_val >= 1_000_000:
            score += 14.0
            reasons.append(f"High average award value (~{avg_val:,.0f} EUR).")
        elif avg_val >= 200_000:
            score += 7.0

    top_cpv = str(buyer_profile.get("top_cpv_division") or "").strip()[:2]
    if top_cpv in {"48", "72", "30", "32"}:
        score += 15.0
        reasons.append(f"Buyer concentrates spend in IT-relevant CPV {top_cpv}.")

    sbr = buyer_profile.get("single_bidder_rate")
    try:
        sbr = float(sbr) if sbr is not None else None
    except (ValueError, TypeError):
        sbr = None
    if sbr is not None:
        if sbr >= 0.6:
            score -= 10.0
            reasons.append(f"High single-bidder rate ({sbr:.0%}) signals incumbency.")
        elif sbr <= 0.2:
            score += 6.0
            reasons.append(f"Low single-bidder rate ({sbr:.0%}) signals open competition.")

    cbr = buyer_profile.get("cross_border_rate")
    try:
        cbr = float(cbr) if cbr is not None else None
    except (ValueError, TypeError):
        cbr = None
    if cbr is not None and cbr >= 0.1:
        score += 5.0
        reasons.append(f"Buyer awards cross-border ({cbr:.0%}); open to non-domestic vendors.")

    return _clamp(score), reasons


def urgency_score(notice: Dict[str, Any], today: Optional[date] = None) -> tuple:
    """Actionability / deadline pressure. Returns (score, reasons, risks)."""
    today = today or date.today()
    reasons: List[str] = []
    risks: List[str] = []

    kind = str(notice.get("notice_kind") or "").upper()
    if kind == "CAN" or notice.get("result_code"):
        return 5.0, ["Awarded contract — informational only, no action window."], []

    deadline = _parse_date(notice.get("submission_deadline"))
    if deadline is None:
        return 45.0, ["No submission deadline parsed; verify the action window manually."], []

    days_left = (deadline - today).days
    if days_left < 0:
        risks.append(f"Submission deadline passed {abs(days_left)} day(s) ago.")
        return 8.0, [], risks
    if days_left <= 7:
        reasons.append(f"Closes in {days_left} day(s) — act immediately.")
        return 95.0, reasons, risks
    if days_left <= 21:
        reasons.append(f"Closes in {days_left} days — near-term action needed.")
        return 80.0, reasons, risks
    if days_left <= 60:
        reasons.append(f"Closes in {days_left} days — comfortable runway.")
        return 60.0, reasons, risks
    reasons.append(f"Closes in {days_left} days — plenty of lead time.")
    return 45.0, reasons, risks


def data_confidence_score(notice: Dict[str, Any]) -> tuple:
    """Penalise records with missing critical fields. Returns (score, risks)."""
    critical = {
        "project_title": notice.get("project_title"),
        "buyer_name": notice.get("buyer_name"),
        "cpv_code": notice.get("cpv_code"),
        "buyer_country": notice.get("buyer_country"),
        "amount": notice.get("amount"),
    }
    # description and deadline only expected for CN notices.
    if str(notice.get("notice_kind") or "").upper() != "CAN":
        critical["description"] = notice.get("description")
        critical["submission_deadline"] = notice.get("submission_deadline")

    present = sum(1 for v in critical.values() if v not in (None, "", "null"))
    total = len(critical)
    score = 100.0 * present / total if total else 50.0
    missing = [k for k, v in critical.items() if v in (None, "", "null")]
    risks: List[str] = []
    if missing:
        risks.append("Incomplete record; missing: " + ", ".join(missing) + ".")
    return _clamp(score), risks


# ---------------------------------------------------------------------------
# Buyer profile / competition enrichment
# ---------------------------------------------------------------------------
def _as_probability(value: Any) -> Optional[float]:
    """Coerce a rate that may be 0-1 or 0-100 into a 0-100 probability."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    if 0.0 <= v <= 1.0:
        return _clamp(v * 100.0)
    return _clamp(v)


def profile_type_from_buyer_profile(buyer_profile: Optional[Dict[str, Any]]) -> str:
    """Return the clustered buyer persona label used as Profile Type."""
    if not buyer_profile:
        return "Unclustered buyer"
    label = buyer_profile.get("cluster_label") or buyer_profile.get("profile_type")
    if label:
        return str(label).strip() or "Unclustered buyer"
    cluster_id = buyer_profile.get("cluster_id")
    if cluster_id not in (None, ""):
        return f"Cluster {cluster_id}"
    return "Unclustered buyer"


def has_clustered_buyer_profile(buyer_profile: Optional[Dict[str, Any]]) -> bool:
    """True only when the row came from the clustered buyer-persona output."""
    if not buyer_profile:
        return False
    if buyer_profile.get("cluster_label") or buyer_profile.get("profile_type"):
        return True
    return buyer_profile.get("cluster_id") not in (None, "")


def opportunity_profile_type(notice: Dict[str, Any]) -> str:
    """Classify the opportunity itself as a fallback for unclustered buyers.

    This is not a replacement for clustered Buyer Profile Type. It is used only
    for display/treemap continuity when an open-tender buyer has no historical
    row in buyer_profiles_clustered, which can happen because clustered buyer
    personas are built from historical awards.
    """
    text = _text_of(notice)
    for label, terms in OPPORTUNITY_PROFILE_RULES:
        for term in terms:
            needle = term.lower()
            if needle.startswith(" ") or needle.endswith(" "):
                if needle in text:
                    return label
            elif needle in text:
                return label
    cpv_division = str(notice.get("cpv_division") or "").strip()[:2]
    if not cpv_division:
        cpv_code = str(notice.get("cpv_code") or "").strip()
        cpv_division = cpv_code[:2]
    if cpv_division in CPV_PROFILE_FALLBACK:
        return CPV_PROFILE_FALLBACK[cpv_division]
    return "Other / Unclassified"


def display_profile_fields(
    notice: Dict[str, Any],
    buyer_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return profile fields used by cards and treemap.

    `profile_type` remains the clustered buyer persona. `treemap_profile_type`
    uses that clustered persona when available; otherwise it falls back to the
    opportunity category so the treemap remains informative instead of hiding.
    """
    buyer_profile_type = profile_type_from_buyer_profile(buyer_profile)
    opp_profile = opportunity_profile_type(notice)
    clustered = has_clustered_buyer_profile(buyer_profile)
    if clustered and buyer_profile_type != "Unclustered buyer":
        return {
            "profile_type": buyer_profile_type,
            "profile_source": "Clustered buyer persona",
            "opportunity_profile_type": opp_profile,
            "treemap_profile_type": buyer_profile_type,
            "treemap_profile_source": "Clustered buyer persona",
            "is_clustered_profile": True,
        }
    return {
        "profile_type": "Unclustered buyer",
        "profile_source": "No clustered buyer match",
        "opportunity_profile_type": opp_profile,
        "treemap_profile_type": opp_profile,
        "treemap_profile_source": "Opportunity profile fallback",
        "is_clustered_profile": False,
    }


def calculate_single_bidder_probability(
    notice: Dict[str, Any],
    buyer_profile: Optional[Dict[str, Any]] = None,
) -> tuple:
    """Estimate probability that a similar award is single-bidder, 0-100.

    Priority of evidence:
    1. Direct award/notice `num_tenders` evidence when known, especially for CAN.
    2. ML probability from `workspace.gold.cn_predictions` for Contract Notices
       (`single_bidder_prob`).
    3. Clustered buyer historical `single_bidder_rate`.
    4. Cluster average `avg_single_bidder_rate`.
    Missing data returns a neutral value rather than a false zero.
    """
    reasons: List[str] = []
    kind = str(notice.get("notice_kind") or "").upper()

    # ML model output from workspace.gold.cn_predictions. The source notebook
    # writes probabilities in 0-1, but _as_probability also accepts 0-100.
    ml_prob = _as_probability(
        notice.get("single_bidder_prob")
        if notice.get("single_bidder_prob") is not None
        else notice.get("ml_single_bidder_prob")
    )
    if ml_prob is not None:
        reasons.append(f"ML model predicts {ml_prob:.0f}/100 single-bidder probability.")

    # Direct award/notice evidence, when present, is the strongest signal.
    notice_prob: Optional[float] = None
    nt = notice.get("num_tenders")
    try:
        nt_i = int(nt) if nt is not None else None
    except (TypeError, ValueError):
        nt_i = None
    if nt_i is not None:
        if nt_i <= 1:
            return 100, ["Award/notice has one recorded tender."]
        # Two bidders is still relatively low competition; many bidders is low probability.
        notice_prob = _clamp(90.0 - (nt_i - 1) * 15.0, 8.0, 80.0)
        reasons.append(f"Award/notice records {nt_i} tenders.")

    buyer_prob = None
    cluster_prob = None
    if buyer_profile:
        buyer_prob = _as_probability(buyer_profile.get("single_bidder_rate"))
        cluster_prob = _as_probability(buyer_profile.get("avg_single_bidder_rate"))
        if buyer_prob is not None:
            reasons.append(f"Clustered buyer history has {buyer_prob:.0f}/100 single-bidder rate.")
        elif cluster_prob is not None:
            reasons.append(f"Buyer cluster average single-bidder rate is {cluster_prob:.0f}/100.")

    # For open CN recommendations, the ML prediction is the best direct signal.
    # Blend it with buyer/cluster history to avoid relying on only one source.
    if kind == "CN" and ml_prob is not None and buyer_prob is not None:
        prob = 0.80 * ml_prob + 0.20 * buyer_prob
    elif kind == "CN" and ml_prob is not None and cluster_prob is not None:
        prob = 0.85 * ml_prob + 0.15 * cluster_prob
    elif kind == "CN" and ml_prob is not None:
        prob = ml_prob
    elif notice_prob is not None and buyer_prob is not None:
        prob = 0.65 * notice_prob + 0.35 * buyer_prob
    elif notice_prob is not None and cluster_prob is not None:
        prob = 0.70 * notice_prob + 0.30 * cluster_prob
    elif notice_prob is not None:
        prob = notice_prob
    elif buyer_prob is not None:
        prob = 0.75 * buyer_prob + 0.25 * 50.0
    elif cluster_prob is not None:
        prob = 0.65 * cluster_prob + 0.35 * 50.0
    else:
        prob = 50.0
        reasons.append("Limited competition data available.")

    return int(round(_clamp(prob))), reasons


# ---------------------------------------------------------------------------
# Recommended next action
# ---------------------------------------------------------------------------
def _recommend_action(band: str, notice: Dict[str, Any]) -> str:
    kind = str(notice.get("notice_kind") or "").upper()
    if kind == "CAN" or notice.get("result_code"):
        return ("Use as market intelligence: study the winner, value and buyer to "
                "inform future positioning. This is not an open bid.")
    mapping = {
        "High-priority bid": "Assign a capture team now and begin bid/no-bid qualification this week.",
        "Worth evaluating": "Route to the sales lead for a fit assessment and partner check.",
        "Monitor": "Add to the watchlist and re-evaluate if scope or buyer signals strengthen.",
        "Low fit": "Deprioritise unless a partner-led angle emerges.",
        "Market intelligence only": "Log for trend analysis; no active pursuit recommended.",
    }
    return mapping.get(band, "Review manually.")


# ---------------------------------------------------------------------------
# Top-level scorer
# ---------------------------------------------------------------------------
def score_opportunity(
    notice: Dict[str, Any],
    buyer_profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
    weights: Optional[Dict[str, float]] = None,
) -> ScoreResult:
    """Compute the full Microsoft Opportunity Score for one notice."""
    weights = weights or WEIGHTS

    fit, fit_reasons, _matched = strategic_fit_score(notice)
    value, value_reasons, amount = commercial_value_score(notice)
    win, win_reasons, win_risks = win_probability_score(notice)
    buyer, buyer_reasons = buyer_attractiveness_score(buyer_profile)
    urg, urg_reasons, urg_risks = urgency_score(notice, today=today)
    conf, conf_risks = data_confidence_score(notice)

    components = {
        "strategic_fit": fit,
        "commercial_value": value,
        "win_probability": win,
        "buyer_attractiveness": buyer,
        "urgency": urg,
        "data_confidence": conf,
    }

    final = sum(components[k] * weights.get(k, 0.0) for k in components)
    final = _clamp(final)
    band = band_for(final)

    reasons: List[str] = []
    reasons.extend(fit_reasons)
    reasons.extend(value_reasons)
    reasons.extend(win_reasons)
    reasons.extend(buyer_reasons)
    reasons.extend(urg_reasons)

    risks: List[str] = []
    risks.extend(win_risks)
    risks.extend(urg_risks)
    risks.extend(conf_risks)

    single_bidder_probability, single_bidder_reasons = calculate_single_bidder_probability(
        notice, buyer_profile=buyer_profile
    )
    profile_fields = display_profile_fields(notice, buyer_profile)

    return ScoreResult(
        opportunity_score=final,
        band=band,
        components=components,
        reason_codes=reasons,
        risks=risks,
        next_action=_recommend_action(band, notice),
        evidence={
            "notice_id": notice.get("notice_id"),
            "notice_kind": notice.get("notice_kind"),
            "amount": amount,
            "buyer_name": notice.get("buyer_name"),
            "cpv_division": notice.get("cpv_division"),
            "cluster_id": buyer_profile.get("cluster_id") if buyer_profile else None,
            "cluster_label": buyer_profile.get("cluster_label") if buyer_profile else None,
            **profile_fields,
            "buyer_type": buyer_profile.get("buyer_type") if buyer_profile else notice.get("buyer_type"),
            "buyer_single_bidder_rate": buyer_profile.get("single_bidder_rate") if buyer_profile else None,
            "buyer_cross_border_rate": buyer_profile.get("cross_border_rate") if buyer_profile else None,
            "buyer_total_contracts": buyer_profile.get("total_contracts") if buyer_profile else None,
            "buyer_total_awarded_value_eur": buyer_profile.get("total_awarded_value_eur") if buyer_profile else None,
            "buyer_top_cpv_division": buyer_profile.get("top_cpv_division") if buyer_profile else None,
            "single_bidder_probability": single_bidder_probability,
            "single_bidder_reasons": single_bidder_reasons,
            "ml_single_bidder_probability": _as_probability(notice.get("single_bidder_prob")),
            "cn_prediction_scored_at": notice.get("cn_prediction_scored_at"),
            "single_bidder_prediction_source": notice.get("cn_prediction_source"),
        },
    )
