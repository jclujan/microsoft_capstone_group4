# Implementation Notes

## Overview

`chatbot_app` contains the Databricks App implementation for the Microsoft Bid Prioritization Assistant. The application reads approved revised Gold tables, ranks opportunities, enriches them with buyer and prediction signals, and renders the results in a Streamlit interface.

## Folder structure

```text
chatbot_app/
├── app.py
├── app.yaml
├── requirements.txt
├── sample.env.example
├── src/
│   ├── config.py
│   ├── data_access.py
│   ├── formatting.py
│   ├── gold_contract.py
│   ├── llm.py
│   ├── opportunity_scoring.py
│   ├── retrieval.py
│   └── ui_components.py
└── tests/
```

## Module responsibilities

- `app.py` coordinates the Streamlit application, user requests, data loading, scoring, and rendering.
- `src/config.py` loads environment-driven configuration and table names.
- `src/gold_contract.py` validates approved Gold table identifiers and blocks unsafe or legacy table references.
- `src/data_access.py` contains SQL Warehouse queries with column-scoped selection, parameterized filters, and graceful handling of optional tables.
- `src/retrieval.py` handles quick presets, query intent, fallback planning, buyer-profile matching, and ranking.
- `src/opportunity_scoring.py` calculates the Microsoft Opportunity Score, buyer-profile enrichment, opportunity-profile fallback, and single-bidder probability.
- `src/formatting.py` converts scored records into card-ready dictionaries and summaries.
- `src/llm.py` provides an optional grounded explanation layer. It is disabled by default.
- `src/ui_components.py` contains Streamlit rendering helpers and the visual system.

## Data flow

1. The user selects a quick preset or enters a custom request.
2. The request is translated into a structured active request with filters, route, sorting, and fallback strategy.
3. Candidate notices or buyer records are loaded from the revised Gold tables through the SQL Warehouse.
4. Records are enriched with buyer profile, cluster profile, and single-bidder prediction data when available.
5. Opportunities are scored and ranked.
6. The UI renders cards, KPI bars, profile labels, score bands, and the profile treemap.

## Gold table safety

The application only allows approved `workspace.gold` tables. It rejects Silver, Bronze, raw, legacy RAG, and legacy feature-table references. SQL identifiers are validated and quoted, and user-controlled filters are passed as query parameters.

## Buyer profiles and treemap

Buyer profile type is sourced from `workspace.gold.buyer_profiles_clustered` and `workspace.gold.cluster_profiles` when a buyer match exists. Matching uses normalized buyer name plus country, with buyer-name-only matching only when the name is unique. If a buyer cannot be matched, the card remains transparent by showing `Unclustered buyer`; the treemap uses an opportunity-profile fallback so the displayed portfolio can still be interpreted.

## Single-bidder probability

For open Contract Notices, the preferred signal is `workspace.gold.cn_predictions.single_bidder_prob`, matched by `notice_id`. If no prediction is available, the app falls back to available competition evidence such as `num_tenders`, buyer-level `single_bidder_rate`, and cluster-level single-bidder rates.

## UI score bands

All 0-100 score indicators use the same fixed palette:

| Range | Color |
|---:|---|
| 90-100 | `#00bf63` |
| 80-89 | `#c1ff72` |
| 70-79 | `#ffde59` |
| 60-69 | `#ffbd59` |
| 50-59 | `#ff914d` |
| Below 50 | `#ff3131` |

This applies to opportunity scores, KPI bars, single-bidder probability, buyer scores, and treemap average-score labels.

## Testing

The unit tests run without Databricks. They validate table safety, query intent, active-request construction, scoring, formatting, clustered profile matching, `cn_predictions` handling, and data-access SQL generation.
