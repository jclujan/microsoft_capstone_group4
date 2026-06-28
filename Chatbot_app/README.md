# Microsoft Bid Prioritization Assistant

A Databricks App built with Streamlit that helps Microsoft teams prioritize European public-procurement opportunities. The app connects to the revised Gold layer, ranks opportunities with an explainable Microsoft Opportunity Score, and presents the results through an interactive business interface.

## Purpose

The assistant supports early bid screening. It helps users identify which tenders are most aligned with Microsoft, which buyers deserve attention, and which awarded contracts provide useful market intelligence. It is intended as a decision-support layer, not as a replacement for formal bid/no-bid review, legal validation, eligibility checks, or commercial strategy.

## Main capabilities

- Ranks open opportunities using a 0-100 Microsoft Opportunity Score.
- Shows KPI components for strategic fit, value, win probability, buyer quality, urgency, data confidence, and single-bidder probability.
- Provides quick analysis presets for top Microsoft-fit opportunities, cloud opportunities, cybersecurity opportunities, high-value open tenders, Spain-focused opportunities, buyer prioritization, and low-competition awarded contracts.
- Assigns buyer profile labels from the clustered buyer profile outputs when available.
- Uses an opportunity-profile fallback for unclustered buyers so portfolio-level visualization remains useful.
- Displays a recommendation mix treemap by profile type.
- Uses `workspace.gold.cn_predictions` for single-bidder probability when a matching prediction exists.
- Runs in retrieval-only mode by default, with an optional grounded LLM explanation layer.

## Data sources

The app reads from the revised Gold layer only. The SQL Warehouse is the query engine; the Gold tables remain the data source.

| Table | Role |
|---|---|
| `workspace.gold.notices_unified` | Primary source for open and awarded notices |
| `workspace.gold.awards_analysis` | Awarded-contract market intelligence |
| `workspace.gold.buyer_profiles` | Buyer-level historical metrics |
| `workspace.gold.buyer_profiles_clustered` | Clustered buyer profile assignments |
| `workspace.gold.cluster_profiles` | Cluster labels and profile summaries |
| `workspace.gold.cn_predictions` | Single-bidder probability predictions for Contract Notices |
| `workspace.gold.cpv_summary` | CPV-level market context |
| `workspace.gold.ml_features` | Supporting ML features |
| `workspace.gold.daily_activity` | Activity trend context |
| `workspace.gold.dim_country`, `dim_cpv`, `dim_buyer_type`, `dim_procedure_type` | Dimension lookups |

The app does not read Silver, Bronze, raw files, legacy RAG tables, or external databases.

## Scoring logic

The Microsoft Opportunity Score is deterministic and explainable. It combines:

| Component | Weight | Description |
|---|---:|---|
| Strategic fit | 30% | Microsoft-relevant technology fit, including cloud, Azure, cybersecurity, AI, data, software, IT services, and relevant CPV divisions |
| Win probability | 20% | Procedure type, notice status, competition indicators, and single-bidder signals |
| Commercial value | 15% | Contract value using log-damped scoring |
| Buyer quality | 15% | Buyer profile strength and historical procurement behavior |
| Urgency | 10% | Time left before submission deadline |
| Data confidence | 10% | Completeness of key fields used for scoring |

Each card also displays a separate single-bidder probability. When available, the app uses `cn_predictions.single_bidder_prob` by `notice_id`; otherwise it falls back to notice competition data, buyer history, and cluster-level signals.

## Deployment

The Databricks App uses `app.yaml` with:

```yaml
command: ["streamlit", "run", "app.py"]
```

Required app resources:

- SQL Warehouse resource with key `sql_warehouse` and permission `Can use`.
- Required Gold table resources with permission `Can select`, including:
  - `workspace.gold.notices_unified`
  - `workspace.gold.buyer_profiles_clustered`
  - `workspace.gold.cluster_profiles`
  - `workspace.gold.cn_predictions`

Supporting Gold tables should also be added with `Can select` for the full experience.

## Local run

```bash
pip install -r requirements.txt
cp sample.env.example .env
# Fill in Databricks host, warehouse id, and local token if needed.
streamlit run app.py
```

## Tests

```bash
pytest
```

The tests run without Databricks and cover scoring, routing, formatting, table validation, clustered profile matching, prediction handling, and UI-safe data structures.

## Limitations

- Scores are prioritization signals, not final bid/no-bid decisions.
- Single-bidder probability is a decision-support metric, not a guaranteed outcome.
- Buyer profile labels depend on the availability and coverage of the clustered buyer profile tables.
- The optional LLM layer is disabled by default and only rephrases already retrieved evidence when configured.
