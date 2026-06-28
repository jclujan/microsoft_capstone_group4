# Dashboard Methodology

## Overview

The Procurement Analytics Dashboard was developed to provide executive
and operational insights into European Union public procurement activity
using business-ready Gold tables produced through the Databricks
Medallion Architecture.

Rather than performing transformations within the dashboard, all
business logic, validation, and aggregations are completed during the
Gold layer ETL process. The dashboard therefore acts purely as a
visualization and reporting layer, ensuring consistency, performance,
and reproducibility.

------------------------------------------------------------------------

## Architecture

``` text
TED v3 API
      │
      ▼
Bronze Layer (Raw XML)
      │
      ▼
Silver Layer (Parsed Delta Tables)
      │
      ▼
Gold Layer (Business-ready Analytics)
      │
      ▼
Databricks Lakeview Dashboard
```

------------------------------------------------------------------------

## Dashboard Design Principles

-   All visualizations query Gold-layer tables directly.
-   Business logic is centralized within the Gold layer.
-   No calculations are performed inside dashboard visualizations.
-   Dashboard pages follow an executive → analytical → operational
    workflow.
-   Every visual is backed by reusable SQL queries.

------------------------------------------------------------------------

## Dashboard Structure

### 1. Overview & Activity

Provides a high-level summary of procurement activity.

**Visualizations**

-   Executive KPI Cards
-   Daily Notice Activity
-   Daily Award Value Trends

**Primary Gold Tables**

-   `workspace.gold.daily_activity`

------------------------------------------------------------------------

### 2. Buyer & CPV Analysis

Explores procurement activity by geography and sector.

**Visualizations**

-   Procurement Spending by Country
-   Procurement Spending by CPV Sector
-   Contract Count by CPV Sector
-   CPV Category Drill-down Table

**Primary Gold Tables**

-   `workspace.gold.buyer_profiles`
-   `workspace.gold.cpv_summary`
-   `workspace.gold.dim_cpv`

------------------------------------------------------------------------

### 3. Awards & Opportunities

Analyzes historical procurement awards and spending.

**Visualizations**

-   Award KPI Cards
-   Buyer Concentration
-   Award Size Distribution
-   Procedure Type Distribution
-   High-Value Awards Table

**Primary Gold Tables**

-   `workspace.gold.awards_analysis`

------------------------------------------------------------------------

## Gold Tables Used

  Gold Table          Purpose
  ------------------- -------------------------------------------
  `daily_activity`    KPI cards and daily procurement trends
  `buyer_profiles`    Buyer-level aggregations
  `cpv_summary`       Sector summaries
  `dim_cpv`           CPV code descriptions
  `awards_analysis`   Award statistics and opportunity analysis

------------------------------------------------------------------------

## Repository Contents

``` text
Analytics/
├── Procurement Analytics Dashboard.lvdash.json
├── Documentation/
│   ├── Dashboard_Guide.md
│   ├── Dashboard_Methodology.md
│   └── Screenshots/
└── PowerBI_Databricks_Rebuild_Package/
```

The repository includes the native Databricks Lakeview dashboard,
supporting documentation, screenshots of each dashboard page, and a
complete Power BI reconstruction package containing extracted SQL
queries, dashboard layout specifications, DAX measures, and a Power BI
theme.

------------------------------------------------------------------------

## Methodology Summary

The dashboard follows a reporting-first methodology in which the
Medallion Architecture performs all data preparation while the dashboard
focuses exclusively on presentation. This separation improves
maintainability, ensures all metrics originate from a single trusted
source, and allows the same analytical model to be reused across both
Databricks Lakeview and Microsoft Power BI.
