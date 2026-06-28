# Power BI Rebuild Package

This ZIP converts your Databricks Lakeview Dashboard JSON into a Power BI rebuild package.

## What is included

- `sql_queries/` — one SQL file per Databricks dataset
- `SQL_QUERY_INDEX.md` — list of all extracted datasets
- `VISUAL_MAPPING.md` — Databricks visual to Power BI visual mapping
- `PAGE_LAYOUT_GUIDE.md` — grid positions from the original dashboard
- `DAX_MEASURES.md` — suggested Power BI measures
- `Procurement_Analytics_PowerBI_Theme.json` — Power BI theme file
- `source_dashboard.json` — original dashboard export

## How to use in Power BI Desktop

1. Open Power BI Desktop.
2. Connect to Databricks using the Databricks connector.
3. Import or DirectQuery the Gold tables:
   - `workspace.gold.daily_activity`
   - `workspace.gold.buyer_profiles`
   - `workspace.gold.cpv_summary`
   - `workspace.gold.dim_cpv`
   - `workspace.gold.awards_analysis`
4. Add the DAX measures from `DAX_MEASURES.md`.
5. Import the theme using:
   View → Themes → Browse for themes.
6. Rebuild each page using `VISUAL_MAPPING.md` and `PAGE_LAYOUT_GUIDE.md`.
7. Save the report as a `.pbix` file.

## Original Dashboard Pages

- Overview & Activity
- Buyer & CPV Analysis
- Awards & Opportunities
