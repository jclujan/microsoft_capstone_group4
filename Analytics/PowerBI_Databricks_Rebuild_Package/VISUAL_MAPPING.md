# Power BI Visual Mapping


## Overview & Activity

| Databricks Widget | Databricks Type | Power BI Visual | Dataset | Suggested Fields |
|---|---:|---|---|---|
| Total Notices | counter | Card | executive_kpis | total_notices |
| Contract Notices | counter | Card | executive_kpis | contract_notices |
| Award Notices | counter | Card | executive_kpis | award_notices |
| Total Estimated Value  (EUR) | counter | Card | executive_kpis | total_estimated_value |
| Daily Notice Activity Shows Cyclical Pattern | line | Line chart | daily_trends | activity_date, total_notices |
| Daily Award Value Spiked in May  | bar | Clustered bar/column chart | daily_trends | activity_date, total_award_value_eur |

## Buyer & CPV Analysis

| Databricks Widget | Databricks Type | Power BI Visual | Dataset | Suggested Fields |
|---|---:|---|---|---|
| Spending is Concentrated in France and Italy | choropleth-map | Filled map | buyers_by_country | total_value, buyer_country |
| Construction and Public Utilities  Receive the Most Spending | bar | Clustered bar/column chart | cpv_by_value | total_value, sector_name |
| Construction and Medical Equipment  Have the Most Contracts | bar | Clustered bar/column chart | cpv_by_count | contract_count, sector_name |
| CPV Category Drill Down | table | Table | cpv_categories | sector_name, contract_count, total_value, distinct_buyers |

## Awards & Opportunities

| Databricks Widget | Databricks Type | Power BI Visual | Dataset | Suggested Fields |
|---|---:|---|---|---|
| Total Awards | counter | Card | award_kpis | total_awards |
| Total Award Value | counter | Card | award_kpis | total_value |
| Median Award | counter | Card | award_kpis | median_value |
| Largest Award | counter | Card | award_kpis | largest_award |
| The Biggest Spenders are French, Italian and Spanish Buyers | bar | Clustered bar/column chart | buyer_concentration | total_value, buyer_name |
| Award Spending is Concentrated in  Open Procurement procedures | pie | Donut chart or pie chart | awards_by_procedure | total_value, procedure_type |
| High-Value Opportunities | table | Table | high_value_awards | buyer_name, project_title, award_value_eur, buyer_country, publication_date |
| Most Procurement Awards are Under €250K | bar | Clustered bar/column chart | award_size_distribution | bin_label, award_count |