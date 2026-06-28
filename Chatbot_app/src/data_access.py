"""Databricks SQL access for the revised-Gold Bid Prioritization Assistant.

Performance & safety rules enforced here:
  * Never SELECT * from large Gold tables — only the columns we need.
  * Push query-specific filters into SQL before loading candidates.
  * Limit initial candidate loading.
  * Validate every table name through the gold_contract allow-list.
  * Never expose stack traces; raise clean DataAccessError messages.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .config import AppConfig
from .gold_contract import (
    NOTICES_CANDIDATE_COLUMNS,
    BUYER_PROFILE_COLUMNS,
    BUYER_PROFILE_CLUSTERED_COLUMNS,
    CLUSTER_PROFILE_COLUMNS,
    CN_PREDICTION_COLUMNS,
    CPV_SUMMARY_COLUMNS,
    AWARDS_ANALYSIS_COLUMNS,
    normalize_generic_row,
    normalize_notice_row,
    safe_table_identifier,
)

logger = logging.getLogger(__name__)


class DataAccessError(Exception):
    """Clean, user-presentable data-access error."""


def _import_sql_connector():
    try:
        from databricks import sql  # type: ignore
        return sql
    except Exception as exc:  # pragma: no cover
        raise DataAccessError("Missing databricks-sql-connector. Check requirements.txt.") from exc


def _sdk_credentials(cfg: AppConfig):
    """Build a Databricks SDK credentials provider for Apps service principals."""
    try:
        from databricks.sdk.core import Config  # type: ignore
    except Exception:
        return None
    kwargs: Dict[str, Any] = {}
    if cfg.server_hostname:
        host = cfg.server_hostname
        if not host.startswith("http"):
            host = f"https://{host}"
        kwargs["host"] = host
    if cfg.access_token:
        kwargs["token"] = cfg.access_token
    try:
        return Config(**kwargs)
    except Exception as exc:
        logger.info("Could not build SDK config: %s", exc)
        return None


def connect(cfg: AppConfig):
    if not cfg.sql_configured:
        raise DataAccessError(
            "SQL Warehouse is not configured. Set DATABRICKS_SERVER_HOSTNAME and bind the "
            "'sql_warehouse' resource so DATABRICKS_WAREHOUSE_ID is provided."
        )
    sql = _import_sql_connector()
    sdk_cfg = _sdk_credentials(cfg)
    try:
        if sdk_cfg is not None and not cfg.access_token:
            return sql.connect(
                server_hostname=cfg.server_hostname,
                http_path=cfg.resolved_http_path,
                credentials_provider=lambda: sdk_cfg.authenticate,
            )
        if cfg.access_token:
            return sql.connect(
                server_hostname=cfg.server_hostname,
                http_path=cfg.resolved_http_path,
                access_token=cfg.access_token,
            )
        if sdk_cfg is not None:
            return sql.connect(
                server_hostname=cfg.server_hostname,
                http_path=cfg.resolved_http_path,
                credentials_provider=lambda: sdk_cfg.authenticate,
            )
        raise DataAccessError(
            "Could not resolve Databricks authentication. In Databricks Apps this is automatic; "
            "for local runs set DATABRICKS_TOKEN."
        )
    except DataAccessError:
        raise
    except Exception as exc:
        raise DataAccessError(
            "Could not connect to the Databricks SQL Warehouse. Check the host, the bound "
            "'sql_warehouse' resource, and SELECT permissions on the Gold tables."
        ) from exc


def _run_query(cfg: AppConfig, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    conn = connect(cfg)
    try:
        cur = conn.cursor()
        try:
            cur.execute(query, params or [])
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(cols, row)) for row in rows]
        finally:
            cur.close()
    except DataAccessError:
        raise
    except Exception as exc:
        logger.info("Query failed: %s", exc)
        raise DataAccessError("A data query failed on the SQL Warehouse. Please retry or narrow the filters.") from exc
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _column_list(columns: List[str]) -> str:
    return ", ".join(f"`{c}`" for c in columns)


def _available_columns(cfg: AppConfig, table_name: str) -> List[str]:
    """Return available columns for a safe table, tolerating Databricks DESCRIBE shape."""
    table = safe_table_identifier(table_name)
    rows = _run_query(cfg, f"DESCRIBE {table}")
    cols: List[str] = []
    for row in rows:
        raw = row.get("col_name") or row.get("col_name ") or row.get("name") or row.get("column_name")
        if raw is None and row:
            # Databricks connector commonly names the first DESCRIBE column `col_name`,
            # but keep a defensive fallback for local mocks.
            raw = next(iter(row.values()))
        col = str(raw or "").strip()
        if not col or col.startswith("#") or col.lower() in {"", "partitioning"}:
            continue
        cols.append(col)
    return cols


def _select_existing(preferred: List[str], available: List[str]) -> List[str]:
    available_lc = {c.lower(): c for c in available}
    return [available_lc[c.lower()] for c in preferred if c.lower() in available_lc]


# ---------------------------------------------------------------------------
# Candidate / supporting fetchers (parameterised, column-scoped, filtered)
# ---------------------------------------------------------------------------
def fetch_notice_candidates(
    cfg: AppConfig,
    *,
    country: Optional[str] = None,
    min_amount: Optional[float] = None,
    notice_kind: Optional[str] = None,   # 'CN', 'CAN', or None for both
    cpv_divisions: Optional[List[str]] = None,
    keyword: Optional[str] = None,
    tech_terms: Optional[List[str]] = None,
    limit: int = 800,
) -> List[Dict[str, Any]]:
    """Load a filtered, column-scoped candidate set from notices_unified.

    Technology filtering uses OR logic: a notice matches the technology area if
    its CPV division is in `cpv_divisions` OR any of `tech_terms` appears in the
    title or description. This avoids the overly strict AND behaviour that
    previously returned near-empty / too-similar result sets. Country, amount and
    notice_kind remain AND filters.
    """
    table = safe_table_identifier(cfg.primary_table)
    cols = _column_list(NOTICES_CANDIDATE_COLUMNS)
    where: List[str] = []
    params: List[Any] = []

    if country:
        where.append("upper(`buyer_country`) = ?")
        params.append(str(country).strip().upper())
    if notice_kind in ("CN", "CAN"):
        where.append("`notice_kind` = ?")
        params.append(notice_kind)
    if min_amount is not None:
        where.append("`amount` >= ?")
        params.append(float(min_amount))

    # Technology = (cpv_division IN divs) OR (title/description LIKE any term).
    safe_divs = [d for d in (cpv_divisions or []) if str(d).isdigit() and len(str(d)) == 2]
    terms = [str(t).strip().lower() for t in (tech_terms or []) if str(t).strip()]
    tech_or: List[str] = []
    if safe_divs:
        placeholders = ", ".join("?" for _ in safe_divs)
        tech_or.append(f"`cpv_division` IN ({placeholders})")
        params.extend(safe_divs)
    for t in terms:
        tech_or.append("(lower(`project_title`) LIKE ? OR lower(`description`) LIKE ?)")
        params.extend([f"%{t}%", f"%{t}%"])
    if tech_or:
        where.append("(" + " OR ".join(tech_or) + ")")

    # Legacy single-keyword filter (kept for backward compatibility).
    if keyword:
        kw = f"%{str(keyword).strip().lower()}%"
        where.append("(lower(`project_title`) LIKE ? OR lower(`description`) LIKE ?)")
        params.extend([kw, kw])

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    limit = max(1, min(int(limit), 5000))
    query = (
        f"SELECT {cols} FROM {table}{where_sql} "
        f"ORDER BY `publication_date` DESC NULLS LAST LIMIT {limit}"
    )
    rows = _run_query(cfg, query, params)
    return [normalize_notice_row(r) for r in rows]


def fetch_buyer_profiles(
    cfg: AppConfig,
    *,
    country: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    table = safe_table_identifier(cfg.buyer_profiles_table)
    cols = _column_list(BUYER_PROFILE_COLUMNS)
    where: List[str] = []
    params: List[Any] = []
    if country:
        where.append("upper(`buyer_country`) = ?")
        params.append(str(country).strip().upper())
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    limit = max(1, min(int(limit), 5000))
    query = (
        f"SELECT {cols} FROM {table}{where_sql} "
        f"ORDER BY `total_awarded_value_eur` DESC NULLS LAST LIMIT {limit}"
    )
    rows = _run_query(cfg, query, params)
    return [normalize_generic_row(r) for r in rows]


def fetch_buyer_profiles_clustered(
    cfg: AppConfig,
    *,
    country: Optional[str] = None,
    limit: int = 5000,
) -> List[Dict[str, Any]]:
    """Load clustered buyer profiles produced by ml/k-means/04_kmeans_buyer_segmentation.py.

    The table is optional for core app operation. This function selects only
    columns that actually exist so small schema variations do not break runtime checks.
    """
    table_name = cfg.buyer_profiles_clustered_table
    table = safe_table_identifier(table_name)
    available = _available_columns(cfg, table_name)
    cols_list = _select_existing(BUYER_PROFILE_CLUSTERED_COLUMNS, available)
    if not cols_list:
        raise DataAccessError("buyer_profiles_clustered has no usable columns.")
    cols = _column_list(cols_list)
    where: List[str] = []
    params: List[Any] = []
    if country and any(c.lower() == "buyer_country" for c in cols_list):
        where.append("upper(`buyer_country`) = ?")
        params.append(str(country).strip().upper())
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    limit = max(1, min(int(limit), 10000))
    order_col = "`total_awarded_value_eur` DESC NULLS LAST" if any(c.lower() == "total_awarded_value_eur" for c in cols_list) else "`buyer_name` ASC"
    query = f"SELECT {cols} FROM {table}{where_sql} ORDER BY {order_col} LIMIT {limit}"
    rows = _run_query(cfg, query, params)
    return [normalize_generic_row(r) for r in rows]


def fetch_cluster_profiles(cfg: AppConfig, limit: int = 100) -> List[Dict[str, Any]]:
    """Load cluster-level persona labels and summary metrics."""
    table_name = cfg.cluster_profiles_table
    table = safe_table_identifier(table_name)
    available = _available_columns(cfg, table_name)
    cols_list = _select_existing(CLUSTER_PROFILE_COLUMNS, available)
    if "cluster_id" not in {c.lower() for c in cols_list}:
        raise DataAccessError("cluster_profiles must contain cluster_id.")
    cols = _column_list(cols_list)
    limit = max(1, min(int(limit), 500))
    order_sql = "ORDER BY `cluster_id` ASC" if any(c.lower() == "cluster_id" for c in cols_list) else ""
    query = f"SELECT {cols} FROM {table} {order_sql} LIMIT {limit}"
    rows = _run_query(cfg, query)
    return [normalize_generic_row(r) for r in rows]


def fetch_cn_predictions(
    cfg: AppConfig,
    *,
    notice_ids: Optional[List[Any]] = None,
    limit: int = 5000,
) -> List[Dict[str, Any]]:
    """Load ML single-bidder predictions from workspace.gold.cn_predictions.

    The table is produced by ml/bidders/Single-Bidder Inference.py and contains
    `single_bidder_prob` for Contract Notices. It is optional: callers should
    catch DataAccessError and continue with deterministic/buyer-history estimates
    when the table is unavailable or not granted as an App resource.
    """
    table_name = cfg.cn_predictions_table
    table = safe_table_identifier(table_name)
    available = _available_columns(cfg, table_name)
    cols_list = _select_existing(CN_PREDICTION_COLUMNS, available)
    if "notice_id" not in {c.lower() for c in cols_list}:
        raise DataAccessError("cn_predictions must contain notice_id.")
    if "single_bidder_prob" not in {c.lower() for c in cols_list}:
        raise DataAccessError("cn_predictions must contain single_bidder_prob.")
    cols = _column_list(cols_list)

    ids = [str(x).strip() for x in (notice_ids or []) if str(x or "").strip()]
    # De-duplicate while preserving order and keep IN clauses reasonably small.
    ids = list(dict.fromkeys(ids))[:5000]

    params: List[Any] = []
    where_sql = ""
    if ids:
        placeholders = ", ".join("?" for _ in ids)
        where_sql = f" WHERE `notice_id` IN ({placeholders})"
        params.extend(ids)

    limit = max(1, min(int(limit), 10000))
    order_sql = "ORDER BY `scored_at` DESC NULLS LAST" if any(c.lower() == "scored_at" for c in cols_list) else ""
    query = f"SELECT {cols} FROM {table}{where_sql} {order_sql} LIMIT {limit}"
    rows = _run_query(cfg, query, params)
    return [normalize_generic_row(r) for r in rows]


def fetch_awards(
    cfg: AppConfig,
    *,
    country: Optional[str] = None,
    cpv_divisions: Optional[List[str]] = None,
    min_amount: Optional[float] = None,
    single_bidder_only: bool = False,
    order_by_competition: bool = False,
    limit: int = 400,
) -> List[Dict[str, Any]]:
    table = safe_table_identifier(cfg.awards_table)
    cols = _column_list(AWARDS_ANALYSIS_COLUMNS)
    where: List[str] = []
    params: List[Any] = []
    if country:
        where.append("upper(`buyer_country`) = ?")
        params.append(str(country).strip().upper())
    if min_amount is not None:
        where.append("`award_value_eur` >= ?")
        params.append(float(min_amount))
    if single_bidder_only:
        where.append("`num_tenders` = 1")
    if cpv_divisions:
        safe_divs = [d for d in cpv_divisions if str(d).isdigit() and len(str(d)) == 2]
        if safe_divs:
            placeholders = ", ".join("?" for _ in safe_divs)
            where.append(f"`cpv_division` IN ({placeholders})")
            params.extend(safe_divs)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    limit = max(1, min(int(limit), 5000))
    # Low-competition fallback: surface the least-contested awards first.
    if order_by_competition:
        order_sql = "ORDER BY `num_tenders` ASC NULLS LAST, `award_value_eur` DESC NULLS LAST"
    else:
        order_sql = "ORDER BY `award_value_eur` DESC NULLS LAST"
    query = f"SELECT {cols} FROM {table}{where_sql} {order_sql} LIMIT {limit}"
    rows = _run_query(cfg, query, params)
    return [normalize_generic_row(r) for r in rows]


def fetch_cpv_summary(cfg: AppConfig, limit: int = 60) -> List[Dict[str, Any]]:
    table = safe_table_identifier(cfg.cpv_summary_table)
    cols = _column_list(CPV_SUMMARY_COLUMNS)
    limit = max(1, min(int(limit), 200))
    query = f"SELECT {cols} FROM {table} ORDER BY `total_award_value_eur` DESC NULLS LAST LIMIT {limit}"
    rows = _run_query(cfg, query)
    return [normalize_generic_row(r) for r in rows]


def fetch_dim(cfg: AppConfig, which: str) -> List[Dict[str, Any]]:
    mapping = {
        "country": cfg.dim_country_table,
        "cpv": cfg.dim_cpv_table,
        "buyer_type": cfg.dim_buyer_type_table,
        "procedure_type": cfg.dim_procedure_type_table,
    }
    if which not in mapping:
        raise DataAccessError(f"Unknown dimension '{which}'.")
    table = safe_table_identifier(mapping[which])
    rows = _run_query(cfg, f"SELECT * FROM {table} LIMIT 500")
    return [normalize_generic_row(r) for r in rows]


def health_check(cfg: AppConfig) -> Dict[str, Any]:
    """Lightweight connectivity probe against the primary table only."""
    table = safe_table_identifier(cfg.primary_table)
    try:
        rows = _run_query(cfg, f"SELECT count(*) AS n FROM {table}")
        n = rows[0].get("n") if rows else 0
        return {"ok": True, "primary_rows": n, "error": None}
    except DataAccessError as exc:
        return {"ok": False, "primary_rows": None, "error": str(exc)}
