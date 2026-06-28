# Procurement Intelligence Platform

**IE University · MBDS Capstone · Microsoft Public Sector Sales**

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Databricks](https://img.shields.io/badge/Platform-Databricks-red) ![XGBoost](https://img.shields.io/badge/ML-XGBoost-orange) ![Streamlit](https://img.shields.io/badge/App-Streamlit-brightgreen) ![Status](https://img.shields.io/badge/Status-Complete-success)

A four-component intelligence system that surfaces actionable EU public procurement signals for Microsoft's public sector sales team — before competitors act on them.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Project Scope](#2-project-scope)
3. [Quick Start](#3-quick-start)
4. [Data Architecture](#4-data-architecture)
5. [Component 1 — Single-Bidder Classifier](#5-component-1--single-bidder-classifier)
6. [Component 2 — Buyer Segmentation](#6-component-2--buyer-segmentation)
7. [Component 3 — Bid Prioritization Assistant](#7-component-3--bid-prioritization-assistant)
8. [Component 4 — Procurement Analytics Dashboard](#8-component-4--procurement-analytics-dashboard)
9. [Data Model](#9-data-model)
10. [Results & Key Findings](#10-results--key-findings)
11. [Known Limitations](#11-known-limitations)
12. [Technology Stack](#12-technology-stack)
13. [Team & Credits](#13-team--credits)
14. [References](#14-references)

---

## 1. Problem Statement

EU public procurement is governed by TED (Tenders Electronic Daily), the European Commission's official database of ~1,500 new notices per day across 27 member states. Microsoft's public sector sales team needs to identify and prioritize opportunities before competitors act — but the volume of notices makes manual review impractical.

**The core insight driving this project:** value exists in early signal, not in reactive tender review. Once a Contract Notice is published, competitors are already reading it. The real advantage lies in knowing *which* tenders are worth pursuing before the deadline, and *which* buyers have historically been open to competition or cross-border suppliers.

This platform provides three interconnected answers:
- **How likely is this tender to attract only one bid?** (competition intelligence)
- **What kind of buyer is this, and have they worked with vendors like Microsoft before?** (buyer profiling)
- **Given all signals, which open opportunities should the sales team prioritize today?** (decision support)

---

## 2. Project Scope

**Included:**
- Automated ingestion from TED v3 API (XML → Bronze → Silver → Gold)
- Single-bidder competition classifier trained on ~25,000 Contract Award Notices
- K-means buyer segmentation across 10,175 distinct buyers
- Browser-based bid prioritization assistant with deterministic scoring
- Full test suite for chatbot modules (no Databricks dependency required)

**Not included:**
- Formal bid/no-bid legal review or eligibility assessment
- Real-time streaming (batch ingestion, ~daily cadence)
- Buyer data outside the ~30-day training window
- Any confidential Microsoft or buyer data (all sources are public TED API)

---

## 3. Quick Start

### Notebooks (Databricks)

All notebooks run on Databricks Free Edition. Clone the repo and attach each notebook to a serverless cluster. Tables are written to `workspace.gold.*` in Unity Catalog.

**Recommended execution order:**

```
00_Setup/00_create_schemas          → create catalog schemas
01_Bronze/01_ingest_xml             → ingest TED XML files
02_Silver/02_parse_notices          → parse into Delta tables
03_Gold/03_build_gold_tables        → build business-ready Gold layer
ML/k-means/04_kmeans_buyer_segmentation → buyer personas
ML/bidders/05_EDA                   → feature engineering + train/test split
ML/bidders/05c_ml_model             → train XGBoost classifier
ML/bidders/05d_Single_Bidder_Inference  → score live Contract Notices
```

### Chatbot App (local)

```bash
cd Chatbot_app
pip install -r requirements.txt
cp sample.env.example .env
# Set DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN in .env
streamlit run app.py
```

### Tests

```bash
cd Chatbot_app
pytest
```

Tests cover scoring, routing, formatting, table validation, and all fallback paths. No Databricks connection required.

---

## 4. Data Architecture

The pipeline follows a Medallion architecture on Databricks:

```
TED v3 API  (~1,500 notices/day)
    │
    ▼
[Bronze]  Raw XML files — DBFS Volumes
    │
    ▼
[Silver]  Parsed Delta tables
    ├── contract_notices            (open tenders, CN)
    └── contract_award_notices      (closed tenders, CAN — with notice_subtype filter)
    │
    ▼
[Gold]    Business-ready datasets
    ├── ml_features_train / ml_features_test   (frozen for reproducibility)
    ├── cn_predictions                         (single-bidder probability per CN)
    ├── buyer_profiles                         (aggregated buyer metrics)
    ├── buyer_profiles_clustered               (with cluster assignment)
    ├── cluster_profiles                       (persona label per cluster)
    └── notices_unified                        (chatbot primary source)
    │
    ▼
[Applications]
    └── Bid Prioritization Assistant (Streamlit on Databricks Apps)
```

**Platform:** Databricks Free Edition (serverless clusters), Delta Lake, Unity Catalog, PySpark.

---

## 5. Component 1 — Single-Bidder Classifier

### What it does

Predicts the probability that a given open tender (Contract Notice) will close with only one bidder. A high single-bidder probability signals low competition — a strategic window for Microsoft to engage the buyer early or to influence technical specifications.

The model is trained on historical Contract Award Notices (CANs), where the outcome (single vs. multiple bidders) is known, and then applied to live Contract Notices (CNs) where outcome is unknown.

### Features

| Feature | Rationale |
|---|---|
| `buyer_country` | Procurement culture varies significantly by country |
| `cpv_division` | Technology categories attract different bidder pools |
| `procedure_type` | Restricted / negotiated procedures reduce competition |
| `buyer_type` | Central agencies behave differently from local bodies |

Contract value was tested but excluded: CANs carry realized value while CNs carry only estimated value, creating a train/inference mismatch.

### Performance

| Metric | Value |
|---|---|
| Algorithm | XGBoost (gradient-boosted trees) |
| ROC-AUC (test set) | **0.771** |
| Training records | 25,642 CANs |
| Scored live notices | 41,159 CNs |
| Base rate (single-bidder) | 45.3% |

### Notebooks

| Notebook | Purpose |
|---|---|
| [ML/bidders/05_EDA.ipynb](ML/bidders/05_EDA.ipynb) | EDA, feature engineering, train/test split |
| [ML/bidders/05b_EDA_appendix.ipynb](ML/bidders/05b_EDA_appendix.ipynb) | Ablation study, feature importance plots |
| [ML/bidders/05c_ml_model.ipynb](ML/bidders/05c_ml_model.ipynb) | Model training and algorithm comparison |
| [ML/bidders/05d_Single_Bidder_Inference.ipynb](ML/bidders/05d_Single_Bidder_Inference.ipynb) | Scoring and writing to `cn_predictions` |

**Output table:** `workspace.gold.cn_predictions`

---

## 6. Component 2 — Buyer Segmentation

### What it does

Groups 10,175 distinct buyers into six strategic personas based on historical procurement behavior. Each persona carries different implications for how Microsoft should approach the buyer — from proactive outreach to market entry via cross-border bids.

### Features used for clustering

| Feature | Description |
|---|---|
| `total_contracts` | Volume of procurement activity |
| `total_award_value` | Cumulative spend |
| `avg_contract_value` | Typical deal size |
| `cpv_diversity` | Breadth of categories purchased |
| `single_bidder_rate` | Historical competition level |
| `cross_border_rate` | Openness to non-domestic suppliers |

**Algorithm:** K-means, k=6. Silhouette score: **0.73** (strong cluster separation).

```python
# Core segmentation loop
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(buyer_features[FEATURE_COLS])

kmeans = KMeans(n_clusters=6, random_state=42, n_init=10)
buyer_features["cluster"] = kmeans.fit_predict(X_scaled)
```

### Six Buyer Personas

| Cluster | Label | Buyers | Key Signal |
|---|---|---:|---|
| 0 | Occasional Construction Buyers | 5,616 | 7% single-bidder rate — competitive |
| 1 | Single-Bidder Health Buyers | 4,016 | 97% single-bidder rate — restricted market |
| 2 | High-Volume Power Buyers | 263 | Large spend, high frequency |
| 3 | Mega-Contract Outlier | 1 | Extreme single buyer |
| 4 | National Centralized Agencies | 3 | Government-level volume |
| 5 | Cross-Border Buyers | 266 | 86% cross-border award rate — open to EU suppliers |

**Strategic note:** Cluster 5 (Cross-Border Buyers) is the highest-priority segment for Microsoft, representing buyers already comfortable awarding contracts to suppliers outside their own country.

### Notebook

| Notebook | Purpose |
|---|---|
| [ML/k-means/04_kmeans_buyer_segmentation.ipynb](ML/k-means/04_kmeans_buyer_segmentation.ipynb) | Full segmentation pipeline |

**Output tables:** `workspace.gold.buyer_profiles_clustered`, `workspace.gold.cluster_profiles`

---

## 7. Component 3 — Bid Prioritization Assistant

### What it does

A browser-based decision-support tool deployed as a Streamlit app on Databricks Apps. It reads from the Gold layer, ranks open tenders using a deterministic Microsoft Opportunity Score (0–100), and presents results through a business interface designed for a non-technical sales audience.

**Design choice:** Deterministic scoring was chosen over an LLM-first approach to guarantee transparency, avoid hallucination on IDs/deadlines/values, and ensure reproducibility. An optional LLM layer for natural-language explanation is available but disabled by default.

### Microsoft Opportunity Score

```python
WEIGHTS = {
    "strategic_fit":       0.30,   # cloud, Azure, cybersecurity, AI, data, software
    "win_probability":     0.20,   # procedure type, competition signals, single-bidder prob
    "commercial_value":    0.15,   # contract value, log-damped
    "buyer_attractiveness":0.15,   # historical buyer metrics
    "urgency":             0.10,   # time to submission deadline
    "data_confidence":     0.10,   # completeness of critical fields
}
# Score is a weighted sum, each component normalized to 0–100
opportunity_score = sum(component * WEIGHTS[k] for k, component in kpi.items())
```

| Component | Weight | Description |
|---|---:|---|
| Strategic fit | 30% | Microsoft-relevant technology alignment (cloud, Azure, cybersecurity, AI) |
| Win probability | 20% | Procedure type, competition indicators, single-bidder probability |
| Commercial value | 15% | Contract size with log-damping to avoid extreme outlier dominance |
| Buyer attractiveness | 15% | Historical procurement behavior from buyer profiles |
| Urgency | 10% | Deadline pressure — days until submission close |
| Data confidence | 10% | Completeness of fields used in scoring |

### Key Capabilities

- Quick presets: "Top Microsoft-fit," "Cloud opportunities above €500k," "Cybersecurity tenders," "Spain-focused," "Low-competition awarded contracts"
- Buyer persona labels from K-means clusters, with fallback to CPV classification when buyer history is unavailable
- Awarded contracts view for market intelligence (separate from open opportunities)
- Treemap visualization of opportunity mix by buyer profile type
- Graceful degradation if Gold tables are partially unavailable

### Code Structure

| File | Role |
|---|---|
| [Chatbot_app/07_app.py](Chatbot_app/07_app.py) | Streamlit interface and main coordination |
| [Chatbot_app/app.yaml](Chatbot_app/app.yaml) | Databricks App launch config |
| [Chatbot_app/src/config.py](Chatbot_app/src/config.py) | Environment and table config |
| [Chatbot_app/src/gold_contract.py](Chatbot_app/src/gold_contract.py) | Safety layer — approves only current Gold tables |
| [Chatbot_app/src/data_access.py](Chatbot_app/src/data_access.py) | SQL queries for candidates, profiles, predictions |
| [Chatbot_app/src/retrieval.py](Chatbot_app/src/retrieval.py) | Intent routing, filtering, fallback logic |
| [Chatbot_app/src/opportunity_scoring.py](Chatbot_app/src/opportunity_scoring.py) | Microsoft Opportunity Score engine |
| [Chatbot_app/src/formatting.py](Chatbot_app/src/formatting.py) | Card and summary rendering |
| [Chatbot_app/src/ui_components.py](Chatbot_app/src/ui_components.py) | Microsoft-style UI: cards, KPI bars, score rings, treemap |

---

## 8. Component 4 — Procurement Analytics Dashboard

### What it does

A Databricks Lakeview dashboard ([Analytics/Procurement Analytics Dashboard.lvdash.json](Analytics/Procurement%20Analytics%20Dashboard.lvdash.json)) that provides executive-level visibility into EU procurement activity. While the Bid Prioritization Assistant is designed for individual opportunity screening, this dashboard gives a market-wide view — total volume, spend trends, sector breakdown, and top awards — for strategic reporting and management review.

### Views

| Dataset | Description |
|---|---|
| Executive KPIs | Total notices, open vs. awarded split, total estimated contract value |
| Daily Trends | Award value and notice volume over time (from May 2026 onward) |
| Buyers by Country | Buyer count, notice volume, and total spend ranked by country |
| CPV Categories | Top 20 sectors by contract value and by notice count |
| High Value Awards | Top 20 awarded contracts by value with buyer name, title, and country |
| Awards by Procedure | Procedure-type breakdown — count, total value, average value |

### Data sources

All queries run against the Gold layer in Unity Catalog:

| Table | Role in dashboard |
|---|---|
| `workspace.gold.daily_activity` | Executive KPIs and daily trend charts |
| `workspace.gold.buyer_profiles` | Buyers by country aggregation |
| `workspace.gold.cpv_summary` | Sector breakdown by count and value |
| `workspace.gold.dim_cpv` | CPV code labels |
| `workspace.gold.awards_analysis` | High-value awards and procedure-type views |

### Deployment

The `.lvdash.json` file is a native Databricks Lakeview definition. To deploy:
1. Open the Databricks workspace and navigate to **Dashboards**
2. Select **Import** and upload `Analytics/Procurement Analytics Dashboard.lvdash.json`
3. Attach a SQL Warehouse with `Can use` permission
4. Ensure the Gold tables above have `Can select` permissions for the dashboard service principal

---

## 9. Data Model

### Silver Layer

| Table | Description |
|---|---|
| `workspace.silver.contract_notices` | Parsed open tenders (CN) |
| `workspace.silver.contract_award_notices` | Parsed closed tenders (CAN), with `notice_subtype` filter |

### Gold Layer

| Table | Description | Primary Consumer |
|---|---|---|
| `workspace.gold.notices_unified` | All notices, open and awarded | Chatbot |
| `workspace.gold.ml_features_train` | Frozen training features | Single-Bidder Classifier |
| `workspace.gold.ml_features_test` | Frozen test features | Single-Bidder Classifier |
| `workspace.gold.cn_predictions` | Single-bidder probability per CN | Chatbot, Scoring engine |
| `workspace.gold.buyer_profiles` | Aggregated buyer metrics | Segmentation, Chatbot |
| `workspace.gold.buyer_profiles_clustered` | Buyers with cluster assignment | Chatbot |
| `workspace.gold.cluster_profiles` | Persona label per cluster | Chatbot |

---

## 10. Results & Key Findings

### Single-Bidder Classifier

- ROC-AUC 0.771 with four categorical features, no engineered combinations
- The model is better at identifying competitive contracts (multiple bidders) than truly single-bidder ones — a safe asymmetry for sales screening
- Adding contract value improved AUC marginally but introduced train/inference parity risk and was excluded
- Base rate of 45.3% single-bidder in training data confirms the EU procurement market is structurally competitive at the aggregate level, but highly variable by segment

### Buyer Segmentation

- Silhouette score of 0.73 at k=6 indicates strong, natural cluster structure — the market does segment meaningfully
- The sharpest business insight: Clusters 0 and 1 cleanly separate competitive (7% single-bidder) from restricted (97% single-bidder) buyer populations, even though they overlap in size and geography
- Cluster 5 (266 buyers, 86% cross-border award rate) is disproportionately valuable for Microsoft's EU sales motion — these buyers actively select non-domestic suppliers
- Two extreme outlier clusters (1 mega-buyer, 3 national agencies) suggest the EU market has a heavy-tail structure in procurement volume

### Bid Prioritization Assistant

- Deterministic scoring provides full explainability — every score can be decomposed into six weighted components
- Integrating single-bidder probability as a scoring component creates a closed loop: the ML model feeds the application
- The hybrid approach (deterministic scoring + optional LLM explanation) avoids hallucination on legally sensitive fields (notice IDs, values, deadlines) while preserving natural-language summarization for analysts

---

## 11. Known Limitations

### Single-Bidder Classifier
- 30-day training window; no seasonality or multi-year trend captured
- No buyer historical features in final model (would require multi-year historical data not available in TED's public API window)
- Selection bias: trained only on published CANs — tenders that were cancelled or never closed are absent
- Negotiated-without-call procedure (Article 32, EU Directive 2014/24) is common in training data but rare in live CN data, inflating predicted probabilities for some segments

### Buyer Segmentation
- Buyers absent from the 30-day window are unrepresented in clusters
- Cluster IDs are not stable across re-runs; only persona labels carry semantic meaning
- Clusters 3 and 4 (1 and 3 buyers respectively) have insufficient size for statistical confidence
- Persona labels require manual validation after each re-run

### Chatbot
- Not a replacement for formal bid/no-bid process, legal review, or eligibility verification
- Score quality depends on freshness and completeness of Gold tables
- Without clustered buyer profiles, falls back to CPV/title-based classification
- Single-bidder probability is only as reliable as the underlying classifier

---

## 12. Technology Stack

| Component | Technology |
|---|---|
| Data ingestion | Python, TED v3 REST API, Databricks notebooks |
| Bronze storage | DBFS Volumes (raw XML) |
| Data processing | PySpark |
| Silver / Gold storage | Delta Lake, Unity Catalog |
| ML training | scikit-learn, XGBoost |
| Clustering | scikit-learn KMeans, Spark MLlib |
| Feature engineering | PySpark, pandas |
| Application | Streamlit on Databricks Apps |
| Query engine | Databricks SQL Warehouse |
| Testing | pytest (no Databricks dependency) |
| Version control | GitHub |

---

## 13. Team & Credits

**Institution:** IE University, School of Science and Technology  
**Program:** Master in Business Analytics & Data Science (MBDS)  
**Partner:** Microsoft (Public Sector Sales)  
**Duration:** 6 weeks, September 2025  
**Supervisor:** Jorge Centeno Centeno

| Name | Role |
|---|---|
| Juan Camilo Luján | Data engineering, ML pipeline |
| Diego Gaitán Castro | ML modeling, EDA |
| Madelyn Ehni | Buyer segmentation, analysis |
| Isha Shah | Chatbot application, scoring |
| Sebastião Clemente | EDA, segmentation |

**AI use disclosure:** AI tools (including Claude) were used for code review, debugging assistance, and documentation drafting. All modeling decisions, architecture choices, and analytical conclusions are the team's own.

---

## 14. References

- European Commission. (n.d.). *Access to public procurement*. Single Market Scoreboard. https://single-market-scoreboard.ec.europa.eu
- Fazekas, M., & Kocsis, G. (2020). Uncovering high-level corruption: Cross-national objective corruption risk indicators using public procurement data. *British Journal of Political Science*, 50(1), 155–164.
- Wachs, J., Fazekas, M., & Kertész, J. (2021). Corruption risk in contracting markets: A network science perspective. *International Journal of Data Science and Analytics*, 12, 45–60.
- European Parliament and Council. (2014). *Directive 2014/24/EU on public procurement* (Article 32: Negotiated procedure without prior publication).
- TED (Tenders Electronic Daily). (n.d.). *TED v3 API documentation*. European Publications Office.

---

*Capstone project — IE University MBDS · 2025. All data sourced from the public TED API. No confidential Microsoft or buyer data used.*
