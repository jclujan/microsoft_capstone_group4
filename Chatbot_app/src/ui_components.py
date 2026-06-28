"""Microsoft-styled Streamlit UI components.

This module is UI-only: no Databricks queries, scoring, or ranking logic.
It renders already-computed dictionaries for the Microsoft Bid Prioritization Assistant.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

# Microsoft corporate palette
MS_BLUE = "#0078D4"
MS_CYAN = "#00A4EF"
MS_GREEN = "#7FBA00"
MS_ORANGE = "#F25022"
MS_YELLOW = "#FFB900"
MS_PURPLE = "#8661C5"
MS_RED = "#D13438"

# Universal 0-100 score bands used by score rings, KPI bars, and score pills.
# <50 = dark red, 50-59 = dark orange, 60-69 = orange,
# 70-79 = yellow, 80-89 = light green, 90+ = dark green.
SCORE_DARK_GREEN = "#00bf63"
SCORE_LIGHT_GREEN = "#c1ff72"
SCORE_YELLOW = "#ffde59"
SCORE_ORANGE = "#ffbd59"
SCORE_DARK_ORANGE = "#ff914d"
SCORE_DARK_RED = "#ff3131"

# Distinct profile colours for treemap categories. These are categorical, not score-based.
TREEMAP_PALETTE = [
    "#0078D4", "#8661C5", "#107C10", "#D83B01", "#008575",
    "#C239B3", "#498205", "#5C2D91", "#CA5010", "#038387",
    "#E3008C", "#4F6BED", "#FFB900", "#69797E",
]

# Surfaces / text (dark navy enterprise theme)
BG_DARK = "#070D19"
BG_MID = "#0B1220"
SURFACE = "#111827"
SURFACE_2 = "#172033"
SURFACE_3 = "#1F2937"
SURFACE_GLASS = "rgba(17,24,39,0.78)"
BORDER = "#26344B"
BORDER_STRONG = "#345173"
TEXT = "#F8FAFC"
TEXT_MUTED = "#9AA8BC"
TEXT_SOFT = "#D8E0EC"

# Score band -> accent
BAND_COLORS = {
    "High-priority bid": MS_GREEN,
    "Worth evaluating": MS_CYAN,
    "Monitor": MS_YELLOW,
    "Low fit": MS_ORANGE,
    "Market intelligence only": "#64748B",
}

# Short labels for the six KPI bars
KPI_LABELS = {
    "strategic_fit": "Strategic fit",
    "commercial_value": "Value",
    "win_probability": "Win probability",
    "buyer_attractiveness": "Buyer quality",
    "urgency": "Urgency",
    "data_confidence": "Confidence",
}

CUSTOM_CSS = f"""
<style>
:root {{
  --ms-blue:{MS_BLUE}; --ms-cyan:{MS_CYAN}; --ms-green:{MS_GREEN};
  --ms-orange:{MS_ORANGE}; --ms-yellow:{MS_YELLOW}; --ms-purple:{MS_PURPLE};
  --bg:{BG_DARK}; --mid:{BG_MID}; --surface:{SURFACE}; --surface2:{SURFACE_2};
  --surface3:{SURFACE_3}; --border:{BORDER}; --text:{TEXT}; --muted:{TEXT_MUTED};
}}

/* App canvas */
.stApp {{
  background:
    radial-gradient(circle at 8% 0%, rgba(0,120,212,0.18), transparent 28%),
    radial-gradient(circle at 92% 4%, rgba(134,97,197,0.14), transparent 24%),
    linear-gradient(180deg, {BG_DARK} 0%, {BG_MID} 52%, #070B13 100%);
}}
.block-container {{ padding-top:2.1rem; padding-bottom:4rem; max-width:1220px; }}
html, body, [class*="css"] {{ color:{TEXT}; font-family:"Segoe UI", Inter, system-ui, sans-serif; }}
h1,h2,h3,h4,h5 {{ letter-spacing:-0.35px; color:{TEXT}; }}
hr {{ border-color:{BORDER}; }}

/* Hide Streamlit decoration/sidebar for app-like finish */
#MainMenu, footer, header {{ visibility:hidden; }}
section[data-testid="stSidebar"] {{ display:none !important; width:0 !important; }}
[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {{ display:none !important; }}
button[kind="header"][data-testid="baseButton-headerNoPadding"] {{ display:none !important; }}

/* Hero */
.ms-hero {{
  position:relative; overflow:hidden; padding:30px 32px; margin:2px 0 16px 0;
  border:1px solid rgba(111,151,201,0.26); border-radius:26px;
  background:
    linear-gradient(135deg, rgba(0,120,212,0.16), rgba(17,24,39,0.68) 42%, rgba(0,164,239,0.08)),
    rgba(17,24,39,0.78);
  box-shadow:0 24px 70px rgba(0,0,0,0.26), inset 0 1px 0 rgba(255,255,255,0.06);
}}
.ms-hero::before {{
  content:""; position:absolute; inset:-2px; pointer-events:none;
  background:linear-gradient(90deg, {MS_ORANGE}, {MS_GREEN}, {MS_BLUE}, {MS_YELLOW});
  height:3px; opacity:.92;
}}
.ms-hero::after {{
  content:""; position:absolute; width:420px; height:420px; right:-180px; top:-210px;
  border-radius:50%; background:radial-gradient(circle, rgba(0,164,239,0.22), transparent 65%);
}}
.ms-squares {{ display:flex; gap:6px; margin-bottom:16px; position:relative; z-index:1; }}
.ms-sq {{ width:18px; height:18px; border-radius:5px; box-shadow:0 8px 24px rgba(0,0,0,0.25); }}
.ms-hero h1 {{ position:relative; z-index:1; font-size:3.65rem; font-weight:760; margin:0 0 10px 0;
  line-height:1.02; letter-spacing:-1.8px; }}
.ms-hero h1 .ms-w-blue {{ color:{MS_BLUE}; }}
.ms-hero h1 .ms-w-cyan {{ color:{MS_CYAN}; }}
.ms-hero p {{ position:relative; z-index:1; color:{TEXT_SOFT}; font-size:1.08rem; margin:0;
  line-height:1.55; max-width:780px; }}
.ms-hero-sub {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; position:relative; z-index:1; }}
.ms-hero-pill {{ display:inline-flex; align-items:center; gap:7px; padding:7px 11px; border-radius:999px;
  color:#DCEEFF; background:rgba(0,120,212,0.13); border:1px solid rgba(0,120,212,0.32);
  font-size:.79rem; font-weight:650; }}
@media (max-width:760px) {{ .ms-hero h1 {{ font-size:2.42rem; }} .ms-hero {{ padding:24px 20px; }} }}

/* Status chips */
.ms-chips {{ display:flex; flex-wrap:wrap; gap:9px; margin:14px 0 8px 0; }}
.ms-chip {{ display:inline-flex; align-items:center; gap:7px; padding:6px 12px;
  border:1px solid rgba(148,163,184,0.22); border-radius:999px; background:rgba(17,24,39,0.72);
  color:{TEXT_MUTED}; font-size:0.8rem; font-weight:620; backdrop-filter:blur(12px); }}
.ms-dot {{ width:7px; height:7px; border-radius:50%; background:{MS_GREEN};
  box-shadow:0 0 0 4px rgba(127,186,0,0.14); }}
.ms-dot.warn {{ background:{MS_YELLOW}; box-shadow:0 0 0 4px rgba(255,185,0,0.14); }}
.ms-dot.off  {{ background:#64748B; box-shadow:none; }}

/* Command center */
.ms-command {{
  margin:18px 0 18px 0; padding:18px; border-radius:22px;
  background:linear-gradient(180deg, rgba(23,32,51,0.92), rgba(17,24,39,0.86));
  border:1px solid rgba(148,163,184,0.20); box-shadow:0 18px 50px rgba(0,0,0,0.20);
}}
.ms-command-title {{ color:{TEXT}; font-size:1.02rem; font-weight:760; margin-bottom:4px; }}
.ms-command-copy {{ color:{TEXT_MUTED}; font-size:.88rem; line-height:1.55; }}
.ms-quick-header {{ margin:8px 0 10px 0; display:flex; align-items:flex-end; justify-content:space-between; gap:16px; }}
.ms-quick-title {{ color:{TEXT}; font-weight:760; font-size:1.04rem; }}
.ms-quick-sub {{ color:{TEXT_MUTED}; font-size:.82rem; margin-top:2px; }}
.ms-quick-note {{ color:#B7D8F8; font-size:.78rem; background:rgba(0,120,212,0.10); border:1px solid rgba(0,120,212,0.24); padding:5px 9px; border-radius:999px; }}

/* Active request bar */
.ms-active {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px;
  background:rgba(23,32,51,0.86); border:1px solid rgba(148,163,184,0.20); border-radius:14px;
  padding:11px 14px; margin:14px 0 8px 0; box-shadow:0 10px 28px rgba(0,0,0,0.12); }}
.ms-fallback {{ color:#F7BBA8; font-size:0.86rem; line-height:1.5;
  background:rgba(242,80,34,0.08); border:1px solid rgba(242,80,34,0.25);
  border-radius:12px; padding:9px 12px; margin:0 0 16px 0; }}
.ms-active .lbl {{ color:{TEXT_MUTED}; font-size:0.72rem; text-transform:uppercase;
  letter-spacing:0.7px; margin-right:4px; font-weight:760; }}
.ms-tag {{ display:inline-flex; align-items:center; padding:4px 10px; border-radius:9px;
  font-size:0.8rem; font-weight:650; background:rgba(0,120,212,0.12);
  color:#CFE6FB; border:1px solid rgba(0,120,212,0.30); }}
.ms-tag.muted {{ background:rgba(31,41,55,0.72); color:{TEXT_MUTED}; border-color:rgba(148,163,184,0.18); }}
.ms-tag.warn {{ background:rgba(242,80,34,0.12); color:#F7BBA8; border-color:rgba(242,80,34,0.30); }}

/* Cards */
.ms-card {{
  background:linear-gradient(180deg, rgba(17,24,39,0.94), rgba(13,20,34,0.94));
  border:1px solid rgba(148,163,184,0.20); border-radius:18px; padding:18px 20px;
  margin-bottom:15px; box-shadow:0 14px 42px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.035);
  transition:transform .18s ease, border-color .18s ease, box-shadow .18s ease, background .18s ease;
}}
.ms-card:hover {{ transform:translateY(-3px); border-color:rgba(0,164,239,0.46);
  box-shadow:0 22px 65px rgba(0,0,0,0.29), 0 0 0 1px rgba(0,164,239,0.10); }}
.ms-card.exec {{ background:linear-gradient(135deg, rgba(0,120,212,0.16), rgba(23,32,51,0.90)); border-color:rgba(0,164,239,0.28); }}
.ms-card-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:18px; }}
.ms-rank {{ color:{TEXT_MUTED}; font-weight:720; font-size:0.8rem; text-transform:uppercase; letter-spacing:.35px; }}
.ms-title {{ color:{TEXT}; font-weight:720; font-size:1.08rem; margin:4px 0 6px 0; line-height:1.35; }}
.ms-meta {{ color:{TEXT_MUTED}; font-size:0.84rem; line-height:1.55; }}
.ms-meta code {{ color:{MS_CYAN}; background:rgba(0,164,239,0.08); padding:1px 6px; border-radius:6px; }}
.ms-pills {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:10px; }}
.ms-mini-pill {{ display:inline-flex; align-items:center; gap:6px; color:#D9E9F8; background:rgba(148,163,184,0.09);
  border:1px solid rgba(148,163,184,0.18); border-radius:999px; padding:4px 9px; font-size:.75rem; font-weight:650; }}
.ms-mini-pill.blue {{ background:rgba(0,120,212,0.13); border-color:rgba(0,120,212,0.30); color:#CFE6FB; }}
.ms-mini-pill.orange {{ background:rgba(242,80,34,0.11); border-color:rgba(242,80,34,0.26); color:#F7C4B2; }}
.ms-mini-pill.green {{ background:rgba(127,186,0,0.11); border-color:rgba(127,186,0,0.25); color:#DDF2B1; }}
.ms-mini-pill.purple {{ background:rgba(134,97,197,0.14); border-color:rgba(134,97,197,0.32); color:#DDD6FE; }}

/* Score badge */
.ms-badge {{ text-align:center; min-width:92px; padding:10px 12px; border-radius:15px;
  border:1px solid rgba(148,163,184,0.18); background:rgba(7,13,25,0.82); }}
.ms-score-ring {{ width:70px; height:70px; display:grid; place-items:center; border-radius:50%; margin:0 auto 6px auto;
  background:conic-gradient(var(--score-color) calc(var(--score) * 1%), rgba(148,163,184,0.13) 0);
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.04); }}
.ms-score-inner {{ width:54px; height:54px; display:grid; place-items:center; border-radius:50%; background:{BG_DARK}; }}
.ms-score-inner .num {{ font-size:1.28rem; font-weight:820; line-height:1; }}
.ms-badge .den {{ font-size:0.68rem; color:{TEXT_MUTED}; margin-top:-4px; }}
.ms-badge .band {{ font-size:0.68rem; font-weight:760; margin-top:4px; letter-spacing:0.2px; }}

/* KPI bars */
.ms-kpis {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px 18px; margin:16px 0 2px 0; }}
.ms-kpi .row {{ display:flex; justify-content:space-between; font-size:0.74rem; color:{TEXT_MUTED}; margin-bottom:5px; }}
.ms-kpi .row b {{ color:{TEXT}; font-weight:760; }}
.ms-track {{ height:6px; border-radius:999px; background:rgba(148,163,184,0.14); overflow:hidden; }}
.ms-fill {{ height:100%; border-radius:999px; position:relative; overflow:hidden; }}
.ms-fill::after {{ content:""; position:absolute; inset:0; transform:translateX(-100%);
  background:linear-gradient(90deg, transparent, rgba(255,255,255,0.24), transparent);
  animation:msShimmer 2.8s ease-in-out infinite; }}
@keyframes msShimmer {{ 0% {{ transform:translateX(-120%); }} 55%,100% {{ transform:translateX(120%); }} }}

/* Cluster profile badge */
.ms-profile {{ display:inline-flex; align-items:center; gap:7px; margin-top:8px;
  padding:5px 11px; border-radius:999px; font-size:0.78rem; font-weight:760;
  background:rgba(0,120,212,0.13); color:#CFE6FB; border:1px solid rgba(0,120,212,0.35); }}
.ms-profile .label {{ color:{TEXT_MUTED}; font-weight:600; }}

/* Summary and insights */
.ms-metric-grid {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:12px; margin:12px 0 18px 0; }}
.ms-metric {{ position:relative; overflow:hidden; border-radius:16px; padding:14px 15px;
  background:rgba(17,24,39,0.82); border:1px solid rgba(148,163,184,0.18); box-shadow:0 12px 35px rgba(0,0,0,0.18); }}
.ms-metric::before {{ content:""; position:absolute; left:0; top:0; width:4px; height:100%; background:var(--accent, {MS_BLUE}); }}
.ms-metric .label {{ color:{TEXT_MUTED}; font-size:.73rem; text-transform:uppercase; letter-spacing:.6px; font-weight:760; }}
.ms-metric .value {{ color:{TEXT}; font-size:1.28rem; font-weight:820; margin-top:4px; }}
.ms-metric .hint {{ color:{TEXT_MUTED}; font-size:.76rem; margin-top:2px; }}
.ms-insight {{ border:1px solid rgba(0,164,239,0.22); background:rgba(0,120,212,0.075); border-radius:15px;
  padding:12px 14px; color:{TEXT_SOFT}; font-size:.9rem; line-height:1.5; margin:8px 0 16px 0; }}
.ms-section-title {{ margin:18px 0 10px 0; }}
.ms-section-title .kicker {{ color:{MS_CYAN}; font-size:.74rem; text-transform:uppercase; letter-spacing:.8px; font-weight:820; }}
.ms-section-title .title {{ color:{TEXT}; font-size:1.16rem; font-weight:800; margin-top:2px; }}
.ms-section-title .sub {{ color:{TEXT_MUTED}; font-size:.86rem; margin-top:2px; }}

/* Treemap */
.ms-treemap-shell {{ margin-top:18px; padding:16px; border-radius:20px;
  background:rgba(17,24,39,0.72); border:1px solid rgba(148,163,184,0.18); }}
.ms-treemap-fallback {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px; margin-top:12px; }}
.ms-treemap-tile {{ background:rgba(23,32,51,0.82); border:1px solid rgba(148,163,184,0.18); border-radius:14px;
  padding:13px; transition:transform .18s ease, border-color .18s ease; }}
.ms-treemap-tile:hover {{ transform:translateY(-2px); border-color:rgba(0,164,239,0.38); }}
.ms-treemap-tile .name {{ font-weight:760; color:{TEXT}; font-size:0.9rem; }}
.ms-treemap-tile .meta {{ color:{TEXT_MUTED}; font-size:0.78rem; margin-top:5px; line-height:1.45; }}
.ms-treemap-caption {{ color:{TEXT_MUTED}; font-size:.82rem; line-height:1.5; margin:8px 0 14px 0; }}
.ms-treemap-svg-wrap {{
  margin-top:14px; padding:12px; border-radius:18px;
  background:linear-gradient(180deg, rgba(7,13,25,0.60), rgba(17,24,39,0.64));
  border:1px solid rgba(148,163,184,0.18);
  box-shadow:0 18px 52px rgba(0,0,0,0.20);
}}
.ms-treemap-svg {{ width:100%; height:auto; display:block; }}
.ms-treemap-legend {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
.ms-treemap-legend-item {{ display:inline-flex; align-items:center; gap:7px;
  padding:5px 9px; border-radius:999px; color:{TEXT_SOFT};
  background:rgba(148,163,184,0.08); border:1px solid rgba(148,163,184,0.16);
  font-size:.74rem; font-weight:680;
}}
.ms-treemap-dot {{ width:8px; height:8px; border-radius:999px; display:inline-block; }}

/* Section labels inside expanders */
.ms-section {{ color:{TEXT}; font-weight:760; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.7px; margin:2px 0 7px 0; }}
.ms-li {{ color:{TEXT_SOFT}; font-size:0.9rem; line-height:1.58; margin-bottom:3px; }}
.ms-li.risk {{ color:#F6C7B4; }}
.ms-action {{ color:{TEXT}; font-size:0.92rem; background:rgba(0,120,212,0.10);
  border-left:3px solid {MS_BLUE}; border-radius:9px; padding:10px 12px; }}

/* Empty state */
.ms-empty {{ text-align:center; padding:42px 20px; color:{TEXT_MUTED}; }}
.ms-empty .big {{ font-size:1.08rem; color:{TEXT}; margin-bottom:6px; font-weight:760; }}

/* Score guide */
.ms-scoreguide {{ font-size:0.82rem; color:{TEXT_MUTED}; line-height:1.6; }}
.ms-scoreguide b {{ color:{TEXT}; font-weight:720; }}

/* Streamlit controls */
.stButton > button {{
  border-radius:14px !important; border:1px solid rgba(148,163,184,0.20) !important;
  background:linear-gradient(180deg, rgba(23,32,51,0.92), rgba(17,24,39,0.92)) !important;
  color:{TEXT} !important; font-weight:700 !important; font-size:0.86rem !important;
  padding:0.72rem 0.9rem !important; min-height:3.05rem !important;
  box-shadow:0 10px 28px rgba(0,0,0,0.16) !important;
  transition:transform .16s ease, box-shadow .16s ease, border-color .16s ease, background .16s ease !important;
}}
.stButton > button:hover {{ transform:translateY(-2px); border-color:rgba(0,164,239,0.55) !important;
  box-shadow:0 18px 42px rgba(0,0,0,0.24), 0 0 0 1px rgba(0,164,239,0.12) !important; }}
.stButton > button[kind="primary"] {{ background:linear-gradient(135deg, {MS_BLUE}, #168DE2) !important; border-color:{MS_BLUE} !important; color:white !important; }}
.stButton > button[kind="primary"]:hover {{ background:linear-gradient(135deg, #1186E8, {MS_CYAN}) !important; }}
.stTextInput > div > div > input {{ background:rgba(23,32,51,0.92) !important; border:1px solid rgba(148,163,184,0.22) !important;
  border-radius:14px !important; color:{TEXT} !important; min-height:3.1rem; }}
.stTextInput > div > div > input:focus {{ border-color:{MS_BLUE} !important; box-shadow:0 0 0 3px rgba(0,120,212,0.18) !important; }}
.stTextInput > div > div > input::placeholder {{ color:#7F8CA0 !important; }}
.streamlit-expanderHeader, details summary {{ color:{TEXT_MUTED} !important; font-size:0.88rem !important; font-weight:700 !important; }}
details {{ border-radius:16px !important; }}
[data-testid="stExpander"] {{ border:1px solid rgba(148,163,184,0.18) !important; border-radius:16px !important; background:rgba(17,24,39,0.48) !important; }}
.stAlert {{ border-radius:14px !important; }}
@media (max-width:900px) {{ .ms-metric-grid {{ grid-template-columns:repeat(2, minmax(0,1fr)); }} .ms-kpis {{ grid-template-columns:repeat(2,1fr); }} }}
@media (max-width:620px) {{ .ms-metric-grid, .ms-kpis {{ grid-template-columns:1fr; }} .ms-card-head {{ flex-direction:column; }} .ms-badge {{ width:100%; }} }}
</style>
"""


def _h(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _compact_money(value: Any, currency: str = "EUR") -> str:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "—"
    cur = currency.strip().upper() if currency else "EUR"
    if abs(val) >= 1_000_000_000:
        return f"{val/1_000_000_000:.1f}bn {cur}"
    if abs(val) >= 1_000_000:
        return f"{val/1_000_000:.1f}m {cur}"
    if abs(val) >= 1_000:
        return f"{val/1_000:.0f}k {cur}"
    return f"{val:,.0f} {cur}"


def _pct(value: Any) -> str:
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return "—"


def _score_value(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.strip().lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(v))):02X}" for v in rgb)


def _mix_hex(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, float(t)))
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)
    return _rgb_to_hex((
        round(ar + (br - ar) * t),
        round(ag + (bg - ag) * t),
        round(ab + (bb - ab) * t),
    ))


def _value_gradient_color(value: Any) -> str:
    """Map any 0-100 value to the project-wide fixed score palette.

    This exact palette is used everywhere a value is on a 0-100 scale:
    <50 dark red (#ff3131), 50-59 dark orange (#ff914d),
    60-69 orange (#ffbd59), 70-79 yellow (#ffde59),
    80-89 light green (#c1ff72), 90+ dark green (#00bf63).
    """
    v = _score_value(value)
    if v >= 90:
        return SCORE_DARK_GREEN
    if v >= 80:
        return SCORE_LIGHT_GREEN
    if v >= 70:
        return SCORE_YELLOW
    if v >= 60:
        return SCORE_ORANGE
    if v >= 50:
        return SCORE_DARK_ORANGE
    return SCORE_DARK_RED


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    return f"rgba({r},{g},{b},{max(0.0, min(1.0, alpha)):.3f})"


def _profile_color(profile: str, index: int = 0) -> str:
    if index < len(TREEMAP_PALETTE):
        return TREEMAP_PALETTE[index]
    seed = sum(ord(ch) for ch in profile)
    return TREEMAP_PALETTE[seed % len(TREEMAP_PALETTE)]


def _truncate(value: Any, max_chars: int) -> str:
    text = str(value if value is not None else "")
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "…"


def inject_css(st) -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def hero(st) -> None:
    st.markdown(
        f"""
        <div class="ms-hero">
          <div class="ms-squares">
            <div class="ms-sq" style="background:{MS_ORANGE}"></div>
            <div class="ms-sq" style="background:{MS_GREEN}"></div>
            <div class="ms-sq" style="background:{MS_BLUE}"></div>
            <div class="ms-sq" style="background:{MS_YELLOW}"></div>
          </div>
          <h1><span class="ms-w-blue">Microsoft</span> Bid Prioritization <span class="ms-w-cyan">Assistant</span></h1>
          <p>Executive-grade tender intelligence for prioritizing public-sector opportunities by Microsoft fit, buyer profile, value, probability and actionability.</p>
          <div class="ms-hero-sub">
            <span class="ms-hero-pill">Copilot-style guidance</span>
            <span class="ms-hero-pill">Gold-table grounded</span>
            <span class="ms-hero-pill">Buyer-cluster personas</span>
            <span class="ms-hero-pill">ML probability signals</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_chips(st, health: Dict[str, Any], llm_provider: str) -> None:
    """Compact status chips: data connection, grounding, scoring."""
    connected = bool(health.get("ok"))
    data_dot = "" if connected else " warn"
    if connected:
        rows = health.get("primary_rows")
        rows_txt = f"{rows:,}" if isinstance(rows, int) else "—"
        data_label = f"Gold data connected · {rows_txt} notices"
    else:
        data_label = "Gold data offline"

    llm_on = (llm_provider or "none").lower() != "none"
    ground_label = "Retrieval grounded" + (f" · LLM {llm_provider}" if llm_on else " · deterministic")

    st.markdown(
        f"""
        <div class="ms-chips">
          <span class="ms-chip"><span class="ms-dot{data_dot}"></span>{_h(data_label)}</span>
          <span class="ms-chip"><span class="ms-dot"></span>{_h(ground_label)}</span>
          <span class="ms-chip"><span class="ms-dot"></span>Opportunity scoring enabled</span>
          <span class="ms-chip"><span class="ms-dot"></span>Buyer profiles + CN predictions ready</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def command_center(st) -> None:
    """Premium introduction panel above the quick question buttons."""
    st.markdown(
        """
        <div class="ms-command">
          <div class="ms-command-title">Start with a boardroom-ready question</div>
          <div class="ms-command-copy">Each button applies a complete analysis preset: filters, ranking logic, fallback strategy and output layout. You can also type a custom request below.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def quick_question_header(st) -> None:
    st.markdown(
        """
        <div class="ms-quick-header">
          <div>
            <div class="ms-quick-title">Recommended business questions</div>
            <div class="ms-quick-sub">Designed for Microsoft account teams, bid managers and market intelligence users.</div>
          </div>
          <div class="ms-quick-note">One-click analysis</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_guide(st) -> None:
    """Short explanation of the score."""
    st.markdown(
        f"""
        <div class="ms-scoreguide">
        The <b>Opportunity Score</b> (0–100) blends six signals:<br>
        <b>Strategic fit</b> · Microsoft cloud / AI / security / data alignment<br>
        <b>Value</b> · contract size (value-balanced)<br>
        <b>Win probability</b> · openness &amp; competition<br>
        <b>Buyer</b> · buyer attractiveness &amp; history<br>
        <b>Urgency</b> · deadline actionability<br>
        <b>Confidence</b> · record completeness
        </div>
        """,
        unsafe_allow_html=True,
    )


def active_request_bar(st, active: Dict[str, Any], fallback_note: str = "") -> None:
    """Render the active request bar so the user can trust filters are applied."""
    tags: List[str] = []

    tech = active.get("technology") or "Any technology"
    tags.append(f'<span class="ms-tag">{_h(tech)}</span>')

    country = active.get("country")
    tags.append(
        f'<span class="ms-tag">{_h(country)}</span>' if country
        else '<span class="ms-tag muted">All countries</span>'
    )

    min_amount = active.get("min_amount")
    if min_amount:
        amt = float(min_amount)
        amt_txt = f"≥ €{amt/1_000_000:.1f}m" if amt >= 1_000_000 else f"≥ €{amt/1_000:.0f}k"
        tags.append(f'<span class="ms-tag">{_h(amt_txt)}</span>')
    else:
        tags.append('<span class="ms-tag muted">Any value</span>')

    scope = active.get("scope") or "Open tenders only"
    tags.append(f'<span class="ms-tag">{_h(scope)}</span>')

    if active.get("low_competition"):
        tags.append('<span class="ms-tag warn">Low competition</span>')

    sort = active.get("sort") or "Recommended"
    tags.append(f'<span class="ms-tag">Sorted by {_h(sort)}</span>')

    top_n = active.get("top_n")
    if top_n:
        tags.append(f'<span class="ms-tag muted">Top {_h(top_n)}</span>')

    tags.append(
        '<span class="ms-tag muted">Fast mode</span>' if active.get("fast_mode", True)
        else '<span class="ms-tag muted">Semantic mode</span>'
    )

    if fallback_note:
        tags.append('<span class="ms-tag warn">Fallback applied</span>')

    st.markdown(
        f'<div class="ms-active"><span class="lbl">Active request</span>{"".join(tags)}</div>',
        unsafe_allow_html=True,
    )
    if fallback_note:
        st.markdown(
            f'<div class="ms-fallback">No exact matches for the original request. {_h(fallback_note)}</div>',
            unsafe_allow_html=True,
        )


def advanced_filters(st, state: Dict[str, Any], tech_labels: List[str],
                     sort_modes: List[str], on_reset) -> Dict[str, Any]:
    """Render the in-page Advanced filters expander and return its values."""
    defaults = {
        "country": "", "technology": "Any technology", "min_amount": 0,
        "scope": "Open tenders only", "sort": "Recommended", "risk": "Balanced",
        "top_n": state.get("top_n", 10), "low_competition": False, "fast_mode": True,
    }
    with st.expander("Advanced filters and scoring controls", expanded=False):
        c1, c2, c3 = st.columns(3)
        country = c1.text_input("Target country (ISO code, e.g. ESP)", key="f_country")
        technology = c2.selectbox("Technology area", tech_labels, key="f_tech")
        min_amount = c3.number_input("Minimum amount (EUR)", min_value=0, step=50_000, key="f_min_amount")

        c4, c5, c6 = st.columns(3)
        scope = c4.radio("Scope", ["Open tenders only", "Awarded contracts", "Both"], key="f_scope")
        sort = c5.selectbox("Sort by", sort_modes, key="f_sort")
        risk = c6.select_slider("Risk appetite", options=["Conservative", "Balanced", "Aggressive"], key="f_risk")

        c7, c8, c9 = st.columns(3)
        top_n = c7.slider("Number of recommendations", 3, 25, key="f_top_n")
        low_comp = c8.checkbox("Low competition only (single-bidder)", key="f_low_comp")
        fast = c9.checkbox("Fast mode", key="f_fast",
                           help="On: fast keyword ranking. Off: TF-IDF semantic matching (slower).")

        st.button("Reset filters", on_click=on_reset, use_container_width=False)

        st.markdown('<div class="ms-section" style="margin-top:14px;">About the score</div>',
                    unsafe_allow_html=True)
        score_guide(st)

    country_norm = (country or "").strip().upper() or None
    min_amount_val = float(min_amount) if min_amount else 0
    values = {
        "country": country_norm,
        "technology": technology,
        "min_amount": min_amount_val,
        "scope": scope,
        "sort": sort,
        "risk": risk,
        "top_n": int(top_n),
        "low_competition": bool(low_comp),
        "fast_mode": bool(fast),
    }
    touched = {
        "country": bool(country_norm),
        "technology": technology != defaults["technology"],
        "min_amount": bool(min_amount_val),
        "scope": scope != defaults["scope"],
        "sort": sort != defaults["sort"],
        "low_competition": bool(low_comp),
    }
    return {"values": values, "touched": touched}


def buyer_route_note(st) -> None:
    """Clarify that buyer results are organisations, not biddable tenders."""
    st.info("These are **buyer organisations** ranked by strategic attractiveness — not open tenders. Use them to focus account targeting.")


def exec_summary(st, text: str, deterministic: bool) -> None:
    note = (
        "Deterministic answer grounded in Gold tables."
        if deterministic
        else "Grounded answer, refined by the configured LLM."
    )
    st.markdown(
        f"""
        <div class="ms-card exec">
          <div class="ms-section">Executive summary</div>
          <div class="ms-li" style="color:{TEXT};font-size:0.97rem;">{_h(text)}</div>
          <div class="ms-meta" style="margin-top:10px;">{_h(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(st, kicker: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="ms-section-title">
          <div class="kicker">{_h(kicker)}</div>
          <div class="title">{_h(title)}</div>
          <div class="sub">{_h(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metric(label: str, value: str, hint: str, accent: str = MS_BLUE) -> str:
    return (
        f'<div class="ms-metric" style="--accent:{accent}">'
        f'<div class="label">{_h(label)}</div><div class="value">{_h(value)}</div><div class="hint">{_h(hint)}</div></div>'
    )


def opportunity_overview(st, cards: List[Dict[str, Any]]) -> None:
    if not cards:
        return
    high = sum(1 for c in cards if c.get("band") == "High-priority bid")
    avg_score = sum(float(c.get("opportunity_score") or 0) for c in cards) / max(1, len(cards))
    values = [float(c.get("amount_value") or 0) for c in cards if isinstance(c.get("amount_value"), (int, float))]
    total_value = sum(values)
    avg_single = sum(float(c.get("single_bidder_probability") or 0) for c in cards) / max(1, len(cards))
    best_profile = _top_profile(cards)
    html_block = (
        '<div class="ms-metric-grid">'
        + _metric("Recommendations", str(len(cards)), f"{high} high-priority", MS_GREEN if high else MS_CYAN)
        + _metric("Average score", f"{avg_score:.0f}/100", "Microsoft opportunity score", MS_BLUE)
        + _metric("Visible value", _compact_money(total_value), "Sum of displayed records", MS_CYAN)
        + _metric("Single-bidder risk", f"{avg_single:.0f}/100", "Average displayed probability", MS_ORANGE if avg_single >= 60 else MS_YELLOW)
        + '</div>'
    )
    insight = (
        f"<div class='ms-insight'><b>Boardroom readout:</b> The current recommendation set is concentrated around "
        f"<b>{_h(best_profile)}</b>. Prioritize cards with high strategic fit, strong buyer quality and a clear next action.</div>"
    )
    st.markdown(html_block + insight, unsafe_allow_html=True)


def buyer_overview(st, buyers: List[Dict[str, Any]]) -> None:
    if not buyers:
        return
    avg_fit = sum(float(b.get("attractiveness") or 0) for b in buyers) / max(1, len(buyers))
    total_contracts = sum(int(b.get("total_contracts") or 0) for b in buyers)
    top_country = _most_common([b.get("country") for b in buyers]) or "Mixed"
    top_cpv = _most_common([b.get("top_cpv_division") for b in buyers if b.get("top_cpv_division") != "—"]) or "Mixed"
    st.markdown(
        '<div class="ms-metric-grid">'
        + _metric("Priority buyers", str(len(buyers)), f"Avg fit {avg_fit:.0f}/100", MS_BLUE)
        + _metric("Contracts observed", f"{total_contracts:,}", "Across displayed buyers", MS_CYAN)
        + _metric("Top market", str(top_country), "Most common country", MS_GREEN)
        + _metric("Top CPV division", str(top_cpv), "Most common technology area", MS_YELLOW)
        + '</div>'
        + "<div class='ms-insight'><b>Account targeting view:</b> Use this list to focus relationship building before the next tender wave, especially where buyer spend and technology concentration are high.</div>",
        unsafe_allow_html=True,
    )


def market_intel_overview(st, awards: List[Dict[str, Any]]) -> None:
    if not awards:
        return
    values = []
    single = 0
    known_tenders = 0
    for a in awards:
        try:
            values.append(float(a.get("award_value_eur") or a.get("amount") or 0))
        except (TypeError, ValueError):
            pass
        nt = a.get("num_tenders")
        if isinstance(nt, (int, float)):
            known_tenders += 1
            if int(nt) == 1:
                single += 1
    single_share = single / known_tenders * 100 if known_tenders else 0
    top_winner = _most_common([a.get("winner_name") for a in awards if a.get("winner_name")]) or "Multiple winners"
    st.markdown(
        '<div class="ms-metric-grid">'
        + _metric("Awarded records", str(len(awards)), "Market intelligence", MS_PURPLE)
        + _metric("Awarded value", _compact_money(sum(values)), "Visible awarded spend", MS_CYAN)
        + _metric("Single-bidder share", f"{single_share:.0f}%", "Among known tender counts", MS_ORANGE if single_share >= 50 else MS_YELLOW)
        + _metric("Frequent winner", str(top_winner)[:26], "In displayed awards", MS_GREEN)
        + '</div>'
        + "<div class='ms-insight'><b>Competitive intelligence:</b> These records are already awarded. Use them to identify buyer behaviour, incumbent suppliers and low-competition patterns.</div>",
        unsafe_allow_html=True,
    )


def _most_common(items: List[Any]) -> Optional[Any]:
    counts: Dict[Any, int] = {}
    for item in items:
        if item in (None, "", "—"):
            continue
        counts[item] = counts.get(item, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda x: x[1])[0]


def _top_profile(cards: List[Dict[str, Any]]) -> str:
    return str(_most_common([c.get("treemap_profile_type") or c.get("profile_type") for c in cards]) or "mixed profiles")


def _kpi_bars_html(components: Dict[str, float], single_bidder_probability: Optional[float] = None) -> str:
    """Render KPI bars on one universal 0-100 red-to-green colour scale."""
    cells = []
    for key, label in KPI_LABELS.items():
        val = _score_value(components.get(key, 0.0))
        color = _value_gradient_color(val)
        cells.append(
            f"""<div class="ms-kpi">
                  <div class="row"><span>{_h(label)}</span><b>{val:.0f}</b></div>
                  <div class="ms-track"><div class="ms-fill"
                       style="width:{max(2,min(100,val)):.0f}%;background:{color};"></div></div>
                </div>"""
        )
    if single_bidder_probability is not None:
        val = _score_value(single_bidder_probability)
        color = _value_gradient_color(val)
        cells.append(
            f"""<div class="ms-kpi">
                  <div class="row"><span>Single-bidder probability</span><b>{val:.0f}/100</b></div>
                  <div class="ms-track"><div class="ms-fill"
                       style="width:{max(2,min(100,val)):.0f}%;background:{color};"></div></div>
                </div>"""
        )
    return f'<div class="ms-kpis">{"".join(cells)}</div>'


def render_opportunity_card(st, card: Dict[str, Any]) -> None:
    score = max(0.0, min(100.0, float(card.get("opportunity_score") or 0)))
    color = _value_gradient_color(score)
    band_color = BAND_COLORS.get(card["band"], MS_CYAN)
    deadline = card.get("deadline")
    deadline_txt = f" · Closes {_h(deadline)}" if deadline and deadline != "—" else ""
    winner = card.get("winner")
    winner_txt = f" · Winner {_h(winner)}" if winner else ""
    single_prob = card.get("single_bidder_probability", 50)
    single_prob_color = _value_gradient_color(single_prob)
    single_prob_style = (
        f"background:{_rgba(single_prob_color, 0.18)};"
        f"border-color:{_rgba(single_prob_color, 0.52)};"
        "color:#F8FAFC;"
    )

    st.markdown(
        f"""
        <div class="ms-card">
          <div class="ms-card-head">
            <div>
              <div class="ms-rank">#{_h(card['rank'])} · {_h(card['kind'])}</div>
              <div class="ms-title">{_h(card['title'])}</div>
              <div class="ms-meta">{_h(card['buyer'])} · {_h(card['country'])} · {_h(card['amount'])}{deadline_txt}<br>
                CPV {_h(card['cpv'])} · Procedure {_h(card['procedure'])}{winner_txt}</div>
              <div class="ms-pills">
                <span class="ms-mini-pill blue">Buyer profile: {_h(card.get('profile_type', 'Unclustered buyer'))}</span>
                <span class="ms-mini-pill purple">Opportunity: {_h(card.get('opportunity_profile_type', 'Other / Unclassified'))}</span>
                <span class="ms-mini-pill" style="{single_prob_style}">Single-bidder {_h(single_prob)}/100</span>
                <span class="ms-mini-pill" style="background:{_rgba(band_color, 0.14)};border-color:{_rgba(band_color, 0.38)};color:#F8FAFC;">{_h(card['band'])}</span>
              </div>
            </div>
            <div class="ms-badge">
              <div class="ms-score-ring" style="--score:{score:.0f}; --score-color:{color};">
                <div class="ms-score-inner"><div class="num" style="color:{color};">{score:.0f}</div></div>
              </div>
              <div class="den">/ 100</div>
              <div class="band" style="color:{color};">{_h(card['band'])}</div>
            </div>
          </div>
          {_kpi_bars_html(card['components'], card.get('single_bidder_probability'))}
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Decision details: fit, risks, next action and evidence"):
        st.markdown('<div class="ms-section">Why it fits Microsoft</div>', unsafe_allow_html=True)
        for w in (card["why"][:3] or ["No specific signal recorded."]):
            st.markdown(f'<div class="ms-li">• {_h(w)}</div>', unsafe_allow_html=True)

        st.markdown('<div class="ms-section" style="margin-top:12px;">Risks</div>', unsafe_allow_html=True)
        if card["risks"]:
            for risk in card["risks"][:2]:
                st.markdown(f'<div class="ms-li risk">• {_h(risk)}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ms-li">• None flagged.</div>', unsafe_allow_html=True)

        st.markdown('<div class="ms-section" style="margin-top:12px;">Profile evidence</div>',
                    unsafe_allow_html=True)
        profile_source = card.get("profile_source") or "No clustered buyer match"
        treemap_source = card.get("treemap_profile_source") or "Opportunity profile fallback"
        st.markdown(
            f'<div class="ms-li">• Buyer profile: {_h(card.get("profile_type", "Unclustered buyer"))} — {_h(profile_source)}</div>'
            f'<div class="ms-li">• Opportunity profile: {_h(card.get("opportunity_profile_type", "Other / Unclassified"))} — {_h(treemap_source)}</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="ms-section" style="margin-top:12px;">Single-bidder probability</div>',
                    unsafe_allow_html=True)
        reasons = card.get("single_bidder_reasons") or ["Limited competition data available."]
        st.markdown(f'<div class="ms-li">• {_h(single_prob)}/100 — {_h(reasons[0])}</div>', unsafe_allow_html=True)

        st.markdown('<div class="ms-section" style="margin-top:12px;">Recommended next action</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="ms-action">{_h(card["next_action"])}</div>', unsafe_allow_html=True)

        st.markdown(
            f'<div class="ms-meta" style="margin-top:12px;">Source · notice <code>{_h(card["notice_id"])}</code>'
            f' · relevance {float(card["relevance"]):.0f}/100</div>',
            unsafe_allow_html=True,
        )


def prepare_profile_treemap_data(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate displayed cards by the best available profile dimension.

    Clustered buyer personas remain the preferred source. For open-tender buyers
    not present in buyer_profiles_clustered, the app uses the opportunity profile
    so the treemap stays useful instead of collapsing to an empty warning.
    """
    groups: Dict[str, Dict[str, Any]] = {}
    total = max(1, len(cards))
    for c in cards or []:
        profile = str(c.get("treemap_profile_type") or c.get("profile_type") or "Other / Unclassified").strip() or "Other / Unclassified"
        source = str(c.get("treemap_profile_source") or "Opportunity profile fallback")
        g = groups.setdefault(profile, {
            "profile_type": profile, "source": source, "count": 0, "score_sum": 0.0, "score_n": 0,
            "value_sum": 0.0, "single_sum": 0.0, "single_n": 0, "clustered_count": 0, "fallback_count": 0,
        })
        g["count"] += 1
        if bool(c.get("is_clustered_profile")):
            g["clustered_count"] += 1
        else:
            g["fallback_count"] += 1
        score = c.get("opportunity_score")
        if isinstance(score, (int, float)):
            g["score_sum"] += float(score)
            g["score_n"] += 1
        val = c.get("amount_value")
        if isinstance(val, (int, float)):
            g["value_sum"] += float(val)
        sp = c.get("single_bidder_probability")
        if isinstance(sp, (int, float)):
            g["single_sum"] += float(sp)
            g["single_n"] += 1
    out: List[Dict[str, Any]] = []
    for g in groups.values():
        count = int(g["count"])
        fallback_count = int(g.get("fallback_count") or 0)
        clustered_count = int(g.get("clustered_count") or 0)
        if clustered_count and fallback_count:
            source = "Mixed clustered + fallback"
        elif clustered_count:
            source = "Clustered buyer persona"
        else:
            source = "Opportunity profile fallback"
        out.append({
            "Profile Type": g["profile_type"],
            "Source": source,
            "Count": count,
            "Share": count / total,
            "Average opportunity score": (g["score_sum"] / g["score_n"]) if g["score_n"] else 0.0,
            "Total value": g["value_sum"],
            "Average single-bidder probability": (g["single_sum"] / g["single_n"]) if g["single_n"] else 0.0,
            "Clustered matches": clustered_count,
            "Fallback profiles": fallback_count,
        })
    out.sort(key=lambda r: (r["Count"], r["Average opportunity score"]), reverse=True)
    return out



def _treemap_split(items: List[Dict[str, Any]], x: float, y: float, w: float, h: float, depth: int = 0) -> List[Dict[str, Any]]:
    """Small deterministic binary treemap layout using Count as area."""
    if not items:
        return []
    if len(items) == 1:
        out = dict(items[0])
        out.update({"x": x, "y": y, "w": w, "h": h})
        return [out]

    total = sum(max(0.001, float(i.get("Count") or 0)) for i in items)
    half = total / 2.0
    best_idx = 1
    best_diff = float("inf")
    running = 0.0
    for idx in range(1, len(items)):
        running += max(0.001, float(items[idx - 1].get("Count") or 0))
        diff = abs(half - running)
        if diff < best_diff:
            best_idx = idx
            best_diff = diff
    left = items[:best_idx]
    right = items[best_idx:]
    left_total = sum(max(0.001, float(i.get("Count") or 0)) for i in left)

    if w >= h:
        w1 = w * left_total / total
        return _treemap_split(left, x, y, w1, h, depth + 1) + _treemap_split(right, x + w1, y, w - w1, h, depth + 1)
    h1 = h * left_total / total
    return _treemap_split(left, x, y, w, h1, depth + 1) + _treemap_split(right, x, y + h1, w, h - h1, depth + 1)


def _profile_treemap_svg(data: List[Dict[str, Any]]) -> str:
    """Render an SVG treemap with categorical colours and score pills."""
    if not data:
        return ""
    width, height = 1040, 430
    pad = 6
    items = []
    for idx, row in enumerate(data):
        profile = str(row.get("Profile Type") or "Other / Unclassified")
        item = dict(row)
        item["_color"] = _profile_color(profile, idx)
        items.append(item)
    rects = _treemap_split(items, 0, 0, width, height)

    svg_parts = [
        f'<svg class="ms-treemap-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Recommendation mix by profile type">'
    ]
    svg_parts.append(
        '<defs><linearGradient id="tileShade" x1="0" x2="1" y1="0" y2="1">'
        '<stop offset="0%" stop-color="rgba(255,255,255,0.20)" />'
        '<stop offset="45%" stop-color="rgba(255,255,255,0.03)" />'
        '<stop offset="100%" stop-color="rgba(0,0,0,0.34)" />'
        '</linearGradient></defs>'
    )
    for r in rects:
        x = float(r["x"]) + pad / 2
        y = float(r["y"]) + pad / 2
        w = max(0.0, float(r["w"]) - pad)
        h = max(0.0, float(r["h"]) - pad)
        if w <= 0 or h <= 0:
            continue
        profile = str(r.get("Profile Type") or "Other / Unclassified")
        count = int(r.get("Count") or 0)
        share = float(r.get("Share") or 0.0)
        avg_score = _score_value(r.get("Average opportunity score"))
        avg_single = _score_value(r.get("Average single-bidder probability"))
        source = str(r.get("Source") or "")
        tile_color = str(r.get("_color") or MS_BLUE)
        score_color = _value_gradient_color(avg_score)
        max_chars = max(8, int((w - 22) / 8.2))
        name = _h(_truncate(profile, max_chars))
        tooltip = _h(
            f"{profile} | Count: {count} | Share: {share:.0%} | Avg score: {avg_score:.1f}/100 | Avg single-bidder: {avg_single:.1f}/100 | Source: {source}"
        )
        svg_parts.append(f'<g class="tm-tile"><title>{tooltip}</title>')
        svg_parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="12" '
            f'fill="{tile_color}" stroke="rgba(255,255,255,0.30)" stroke-width="1.2" opacity="0.92" />'
        )
        svg_parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="12" '
            f'fill="url(#tileShade)" opacity="0.55" />'
        )
        if w > 75 and h > 46:
            title_size = 18 if w > 180 and h > 110 else 14
            svg_parts.append(
                f'<text x="{x + 12:.1f}" y="{y + 28:.1f}" fill="#FFFFFF" font-size="{title_size}" '
                f'font-weight="760" font-family="Segoe UI, Inter, sans-serif">{name}</text>'
            )
        if w > 118 and h > 92:
            svg_parts.append(
                f'<text x="{x + 12:.1f}" y="{y + 52:.1f}" fill="rgba(255,255,255,0.86)" font-size="13" '
                f'font-weight="600" font-family="Segoe UI, Inter, sans-serif">{count} recs · {share:.0%} share</text>'
            )
        if w > 132 and h > 82:
            pill_w = 138
            pill_h = 26
            pill_x = x + 12
            pill_y = y + h - pill_h - 12
            svg_parts.append(
                f'<rect x="{pill_x:.1f}" y="{pill_y:.1f}" width="{pill_w}" height="{pill_h}" rx="13" '
                f'fill="#FFFFFF" opacity="0.96" />'
            )
            svg_parts.append(
                f'<text x="{pill_x + 13:.1f}" y="{pill_y + 18:.1f}" fill="#111827" font-size="12" '
                f'font-weight="800" font-family="Segoe UI, Inter, sans-serif">Avg Score</text>'
            )
            svg_parts.append(
                f'<text x="{pill_x + 86:.1f}" y="{pill_y + 18:.1f}" fill="{score_color}" font-size="12" '
                f'font-weight="900" font-family="Segoe UI, Inter, sans-serif">{avg_score:.0f}</text>'
            )
        svg_parts.append('</g>')
    svg_parts.append('</svg>')
    return ''.join(svg_parts)


def _profile_treemap_legend(data: List[Dict[str, Any]]) -> str:
    items = []
    for idx, d in enumerate(data[:10]):
        profile = str(d.get("Profile Type") or "Other / Unclassified")
        color = _profile_color(profile, idx)
        items.append(
            f'<span class="ms-treemap-legend-item"><span class="ms-treemap-dot" style="background:{color}"></span>'
            f'{_h(_truncate(profile, 30))}</span>'
        )
    return f'<div class="ms-treemap-legend">{"".join(items)}</div>' if items else ""

def render_profile_treemap(st, cards: List[Dict[str, Any]]) -> None:
    """Render recommendation mix by profile type with clear categorical colours."""
    st.markdown('<div class="ms-treemap-shell">', unsafe_allow_html=True)
    section_title(
        st,
        "Buyer personas",
        "Recommendation mix by profile type",
        "Tile size shows proportion of displayed recommendations. Category colours identify profiles; the white Avg Score pill uses the same 0-100 score-band scale as the cards.",
    )
    if not cards:
        st.info("No recommendation mix available yet. Run an analysis to view profile distribution.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    data = prepare_profile_treemap_data(cards)
    if not data:
        st.info("No recommendation mix available yet. Run an analysis to view profile distribution.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    fallback_rows = sum(int(d.get("Fallback profiles") or 0) for d in data)
    clustered_rows = sum(int(d.get("Clustered matches") or 0) for d in data)
    if fallback_rows and not clustered_rows:
        st.markdown(
            '<div class="ms-treemap-caption">These displayed buyers were not matched in '
            '<code>buyer_profiles_clustered</code>, so profile mix uses opportunity-profile categories. '
            'The tile colours are categorical; the Avg Score pill is the performance signal.</div>',
            unsafe_allow_html=True,
        )
    elif fallback_rows:
        st.markdown(
            '<div class="ms-treemap-caption">Some buyers were not matched in '
            '<code>buyer_profiles_clustered</code>; those cards use opportunity-profile fallback categories. '
            'The tile colours are categorical; the Avg Score pill is the performance signal.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="ms-treemap-caption">All displayed buyers are matched to clustered buyer personas. '
            'The tile colours are categorical; the Avg Score pill is the performance signal.</div>',
            unsafe_allow_html=True,
        )

    svg = _profile_treemap_svg(data)
    legend = _profile_treemap_legend(data)
    if svg:
        st.markdown(f'<div class="ms-treemap-svg-wrap">{svg}{legend}</div>', unsafe_allow_html=True)
    else:
        tiles = []
        for idx, d in enumerate(data):
            profile_name = str(d.get("Profile Type") or "Other / Unclassified")
            color = _profile_color(profile_name, idx)
            score = _score_value(d.get("Average opportunity score"))
            score_color = _value_gradient_color(score)
            tile = (
                f'<div class="ms-treemap-tile" style="border-color:{_rgba(color, .55)};">'
                f'<div class="name">{_h(profile_name)}</div>'
                f'<div class="meta">{d["Count"]} recommendations · {d["Share"]:.0%} share<br>'
                f'<span class="ms-mini-pill" style="margin-top:7px;background:#FFFFFF;border-color:rgba(255,255,255,.72);color:#111827;">'
                f'Avg Score <span style="color:{score_color};font-weight:900;">{score:.0f}</span></span></div></div>'
            )
            tiles.append(tile)
        st.markdown(f'<div class="ms-treemap-fallback">{"".join(tiles)}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_buyer_card(st, b: Dict[str, Any]) -> None:
    sbr = b.get("single_bidder_rate")
    sbr_txt = f"single-bidder {float(sbr):.0%}" if isinstance(sbr, (int, float)) else "competition data unavailable"
    fit = max(0.0, min(100.0, float(b.get("attractiveness") or 0)))
    fit_color = _value_gradient_color(fit)
    st.markdown(
        f"""
        <div class="ms-card">
          <div class="ms-card-head">
            <div>
              <div class="ms-rank">#{_h(b['rank'])} · Buyer profile</div>
              <div class="ms-title">{_h(b['buyer'])}</div>
              <div class="ms-meta">{_h(b['country'])} · {_h(b['buyer_type'])} · top CPV {_h(b['top_cpv_division'])}</div>
              <div class="ms-pills">
                <span class="ms-mini-pill blue">{_h(b['total_contracts'])} contracts</span>
                <span class="ms-mini-pill green">Total {_h(b['total_value'])}</span>
                <span class="ms-mini-pill orange">{_h(sbr_txt)}</span>
              </div>
            </div>
            <div class="ms-badge">
              <div class="ms-score-ring" style="--score:{fit:.0f}; --score-color:{fit_color};">
                <div class="ms-score-inner"><div class="num" style="color:{fit_color};">{fit:.0f}</div></div>
              </div>
              <div class="den">/ 100</div>
              <div class="band" style="color:{fit_color};">Buyer fit</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Account strategy rationale"):
        for r in (b["reasons"] or ["No specific signal recorded."]):
            st.markdown(f'<div class="ms-li">• {_h(r)}</div>', unsafe_allow_html=True)


def empty_state(st, message: str) -> None:
    st.markdown(
        f"""
        <div class="ms-card"><div class="ms-empty">
          <div class="big">No matching opportunities</div>
          <div>{_h(message)}</div>
        </div></div>
        """,
        unsafe_allow_html=True,
    )


def market_intel_card(st, a: Dict[str, Any], amount: str) -> None:
    nt = a.get("num_tenders")
    nt_txt = nt if nt is not None else "—"
    comp_label = "single-bidder" if nt == 1 else (f"{nt_txt} tenders" if nt_txt != "—" else "competition unknown")
    st.markdown(
        f"""
        <div class="ms-card">
          <div class="ms-card-head">
            <div>
              <div class="ms-rank">Awarded contract · market intelligence</div>
              <div class="ms-title">{_h(a.get('project_title') or '(untitled notice)')}</div>
              <div class="ms-meta">Winner {_h(a.get('winner_name') or 'n/a')} · Buyer {_h(a.get('buyer_name') or 'n/a')} ({_h(a.get('buyer_country') or '—')})</div>
              <div class="ms-pills">
                <span class="ms-mini-pill green">{_h(amount)}</span>
                <span class="ms-mini-pill blue">CPV {_h(a.get('cpv_code') or '—')}</span>
                <span class="ms-mini-pill orange">{_h(comp_label)}</span>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
