# Procurement Analytics Dashboard

## Overview

The Procurement Analytics Dashboard provides an executive-level view of EU procurement activity using Gold-layer tables generated through the Databricks Medallion Architecture.

The dashboard consists of three analytical pages.

---

# 1. Overview & Activity

Provides a high-level summary of procurement activity across the dataset.

### Executive KPIs

- Total Notices
- Contract Notices
- Award Notices
- Total Estimated Procurement Value

![Overview KPIs](Screenshots/overview_activity.png)

### Daily Activity

Shows procurement publication volume and total award value over time.

Key insight:
- Procurement activity follows cyclical publication patterns.
- Award spending peaked during May 2026.

---

# 2. Buyer & CPV Analysis

Provides geographical and sector-level procurement insights.

## Procurement Value by Country

![Country Map](Screenshots/buyer_cpv_map.png)

Key insights

- France records over €28B in procurement spending.
- Italy exceeds €19B.
- Spain exceeds €10B.
- Poland exceeds €9B.

## Sector Analysis

![Sector Charts](Screenshots/buyer_cpv_charts.png)

Key insights

- Construction dominates procurement spending.
- Medical Equipment has the largest number of procurement notices.

## CPV Detail Table

![CPV Table](Screenshots/buyer_cpv_table.png)

Allows detailed exploration of procurement sectors.

---

# 3. Awards & Opportunities

Provides insight into completed procurement awards.

## Award KPIs

![Award KPIs](Screenshots/awards_kpis.png)

Displays

- Total awards
- Total award value
- Median award
- Largest award

## Award Distribution

![Awards Charts](Screenshots/awards_distribution.png)

Key insights

- Over 60% of awards are below €250K.
- Open procurement procedures account for the largest share of procurement spending.

## High Value Awards

![Award Table](Screenshots/awards_table.png)

Lists the highest-value procurement awards for further investigation.
