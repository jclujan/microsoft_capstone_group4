"""Configuration for the Microsoft Bid Prioritization Assistant.

All secrets and connection details come from environment variables provided by
Databricks Apps (service-principal / resource binding). Nothing is hardcoded and
the user is never asked to paste a token into the UI.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from . import gold_contract

DEFAULT_CATALOG = gold_contract.CATALOG
DEFAULT_SCHEMA = gold_contract.SCHEMA


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)) or default)
    except (ValueError, TypeError):
        return default


def derive_http_path(warehouse_id: Optional[str]) -> Optional[str]:
    if not warehouse_id:
        return None
    warehouse_id = warehouse_id.strip()
    if warehouse_id.startswith("/sql/"):
        return warehouse_id
    return f"/sql/1.0/warehouses/{warehouse_id}"


@dataclass(frozen=True)
class AppConfig:
    server_hostname: Optional[str]
    warehouse_id: Optional[str]
    access_token: Optional[str]

    catalog: str = DEFAULT_CATALOG
    schema: str = DEFAULT_SCHEMA

    primary_table: str = gold_contract.qualified("notices_unified")
    awards_table: str = gold_contract.qualified("awards_analysis")
    ml_features_table: str = gold_contract.qualified("ml_features")
    buyer_profiles_table: str = gold_contract.qualified("buyer_profiles")
    cpv_summary_table: str = gold_contract.qualified("cpv_summary")
    daily_activity_table: str = gold_contract.qualified("daily_activity")
    dim_country_table: str = gold_contract.qualified("dim_country")
    dim_cpv_table: str = gold_contract.qualified("dim_cpv")
    dim_buyer_type_table: str = gold_contract.qualified("dim_buyer_type")
    dim_procedure_type_table: str = gold_contract.qualified("dim_procedure_type")
    buyer_profiles_clustered_table: str = gold_contract.qualified("buyer_profiles_clustered")
    cluster_profiles_table: str = gold_contract.qualified("cluster_profiles")
    cn_predictions_table: str = gold_contract.qualified("cn_predictions")

    candidate_limit: int = 800
    default_top_n: int = 10
    llm_provider: str = "none"

    @property
    def resolved_http_path(self) -> Optional[str]:
        return derive_http_path(self.warehouse_id)

    @property
    def sql_configured(self) -> bool:
        return bool(self.server_hostname and self.warehouse_id)


def load_config() -> AppConfig:
    return AppConfig(
        server_hostname=_env("DATABRICKS_SERVER_HOSTNAME"),
        warehouse_id=_env("DATABRICKS_WAREHOUSE_ID"),
        access_token=_env("DATABRICKS_TOKEN"),
        candidate_limit=_env_int("CANDIDATE_LIMIT", 800),
        default_top_n=_env_int("DEFAULT_TOP_N", 10),
        llm_provider=(_env("LLM_PROVIDER", "none") or "none").lower(),
    )
