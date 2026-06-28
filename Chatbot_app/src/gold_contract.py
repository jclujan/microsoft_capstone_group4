"""Revised-Gold schema contract and table-name safety validation.

This module is the single source of truth for which tables and columns the
Microsoft Bid Prioritization Assistant is allowed to read. Everything is derived
from `data_engineering/03_Gold/03_build_gold_tables_revised.py`.

Hard rules enforced here:
  * Only `workspace.gold.<table>` identifiers are allowed.
  * Silver, bronze and raw schemas are rejected.
  * The legacy tables `rag_documents` and `ml_contract_features` are rejected.
  * Any identifier containing whitespace, quotes, comments, semicolons or other
    SQL-injection patterns is rejected.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

CATALOG = "workspace"
SCHEMA = "gold"

# ---------------------------------------------------------------------------
# Allowed revised-Gold tables (exact names from 03_build_gold_tables_revised.py)
# ---------------------------------------------------------------------------
ALLOWED_TABLES = frozenset(
    {
        "notices_unified",       # primary table
        "awards_analysis",
        "ml_features",
        "buyer_profiles",
        "cpv_summary",
        "daily_activity",
        "dim_country",
        "dim_cpv",
        "dim_buyer_type",
        "dim_procedure_type",
        "buyer_profiles_clustered",
        "cluster_profiles",
        "cn_predictions",
    }
)

# Tables that must NEVER be queried, even if someone writes workspace.gold.<x>.
FORBIDDEN_TABLES = frozenset(
    {
        "rag_documents",
        "ml_contract_features",
    }
)

PRIMARY_TABLE = f"{CATALOG}.{SCHEMA}.notices_unified"

# ---------------------------------------------------------------------------
# Column contracts (exact aliases produced by the revised Gold builder)
# ---------------------------------------------------------------------------
NOTICES_UNIFIED_COLUMNS: List[str] = [
    "notice_kind",          # 'CN' (open) or 'CAN' (awarded)
    "notice_id",
    "publication_date",
    "buyer_name",
    "buyer_country",
    "buyer_type",
    "project_title",
    "description",          # only populated for CN rows
    "cpv_code",
    "cpv_division",
    "procedure_type",
    "amount",               # estimated_value (CN) or award_value (CAN)
    "currency",
    "submission_deadline",  # only populated for CN rows
    "result_code",
    "winner_name",
    "winner_country",
    "num_tenders",
    "source_file",
    "run_date",
]

BUYER_PROFILE_COLUMNS: List[str] = [
    "buyer_name",
    "buyer_country",
    "buyer_type",
    "total_contracts",
    "total_awarded_value_eur",
    "avg_award_value_eur",
    "distinct_cpv_codes",
    "last_tender_date",
    "single_bidder_rate",
    "cross_border_rate",
    "top_cpv_division",
]

BUYER_PROFILE_CLUSTERED_COLUMNS: List[str] = [
    "buyer_name",
    "buyer_country",
    "buyer_type",
    "total_contracts",
    "total_awarded_value_eur",
    "avg_award_value_eur",
    "distinct_cpv_codes",
    "single_bidder_rate",
    "cross_border_rate",
    "top_cpv_division",
    "cluster_id",
]

CLUSTER_PROFILE_COLUMNS: List[str] = [
    "cluster_id",
    "cluster_label",
    "num_buyers",
    "avg_contracts",
    "avg_total_spend",
    "avg_contract_size",
    "avg_cpv_diversity",
    "avg_single_bidder_rate",
    "avg_cross_border_rate",
    "top_country",
    "top_cpv_division",
]

CN_PREDICTION_COLUMNS: List[str] = [
    "notice_id",
    "buyer_name",
    "project_title",
    "cpv_code",
    "buyer_country",
    "estimated_value",
    "single_bidder_prob",
    "scored_at",
]

CPV_SUMMARY_COLUMNS: List[str] = [
    "cpv_division",
    "contract_count",
    "total_award_value_eur",
    "avg_award_value_eur",
    "distinct_buyers",
    "distinct_buyer_countries",
    "single_bidder_rate",
]

AWARDS_ANALYSIS_COLUMNS: List[str] = [
    "notice_id",
    "notice_subtype",
    "publication_date",
    "buyer_name",
    "buyer_country",
    "buyer_type",
    "project_title",
    "cpv_code",
    "cpv_division",
    "procedure_type",
    "award_value",
    "award_value_eur",
    "currency",
    "winner_name",
    "winner_country",
    "num_tenders",
    "source_file",
    "run_date",
]

# Columns we actually want to pull for retrieval candidates. We never SELECT *.
NOTICES_CANDIDATE_COLUMNS: List[str] = [
    "notice_kind",
    "notice_id",
    "publication_date",
    "buyer_name",
    "buyer_country",
    "buyer_type",
    "project_title",
    "description",
    "cpv_code",
    "cpv_division",
    "procedure_type",
    "amount",
    "currency",
    "submission_deadline",
    "result_code",
    "winner_name",
    "winner_country",
    "num_tenders",
]

# ---------------------------------------------------------------------------
# Identifier safety
# ---------------------------------------------------------------------------
_INJECTION_PATTERN = re.compile(r"[\s\"'`;]|--|/\*|\*/")
_VALID_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


class UnsafeTableError(ValueError):
    """Raised when a requested table is not an allowed revised-Gold table."""


def is_safe_table(table_name: str) -> bool:
    """Return True only for fully-qualified, allow-listed revised-Gold tables."""
    if not isinstance(table_name, str):
        return False
    raw = table_name.strip()
    if not raw:
        return False
    # Reject injection characters / comment markers before anything else.
    if _INJECTION_PATTERN.search(raw):
        return False
    parts = raw.split(".")
    if len(parts) != 3:
        return False
    catalog, schema, table = (p.strip().lower() for p in parts)
    if catalog != CATALOG or schema != SCHEMA:
        return False
    if not _VALID_IDENTIFIER.match(table):
        return False
    if table in FORBIDDEN_TABLES:
        return False
    return table in ALLOWED_TABLES


def safe_table_identifier(table_name: str) -> str:
    """Validate and return a backtick-quoted safe identifier, or raise."""
    if not is_safe_table(table_name):
        raise UnsafeTableError(
            f"Refusing to query non-allowed table: {table_name!r}. "
            "Only revised workspace.gold.* tables are permitted."
        )
    catalog, schema, table = (p.strip().lower() for p in table_name.split("."))
    return f"`{catalog}`.`{schema}`.`{table}`"


def qualified(table: str) -> str:
    """Build a fully-qualified name from a bare allow-listed table name."""
    if table not in ALLOWED_TABLES:
        raise UnsafeTableError(f"Unknown revised-Gold table: {table!r}")
    return f"{CATALOG}.{SCHEMA}.{table}"


def missing_columns(present: Iterable[str], required: Iterable[str]) -> List[str]:
    present_set = {str(c).lower() for c in present}
    return [c for c in required if c.lower() not in present_set]


# ---------------------------------------------------------------------------
# Row normalisation helpers
# ---------------------------------------------------------------------------
def _coerce(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    return value


def normalize_notice_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Return a notice dict with every contract column present (None-filled)."""
    out: Dict[str, Any] = {}
    for col in NOTICES_UNIFIED_COLUMNS:
        out[col] = _coerce(row.get(col))
    return out


def normalize_generic_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _coerce(v) for k, v in row.items()}
