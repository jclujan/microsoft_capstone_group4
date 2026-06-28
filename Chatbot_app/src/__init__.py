"""Microsoft Bid Prioritization Assistant — source package.

Modules:
  config              environment-driven configuration
  gold_contract       revised-Gold schema contract + table safety
  data_access         Databricks SQL access (column-scoped, filtered, cached)
  opportunity_scoring deterministic Microsoft Opportunity Score engine
  retrieval           intent routing + relevance + blended ranking
  formatting          clean source cards / business summaries
  llm                 optional grounded LLM explanation layer
  ui_components       Microsoft-styled Streamlit components
"""

__all__ = [
    "config",
    "gold_contract",
    "data_access",
    "opportunity_scoring",
    "retrieval",
    "formatting",
    "llm",
    "ui_components",
]

__version__ = "2.0.0"
