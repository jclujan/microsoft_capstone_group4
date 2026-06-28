SELECT
  buyer_name,
  project_title,
  award_value_eur,
  buyer_country,
  publication_date
FROM
  workspace.gold.awards_analysis
WHERE
  award_value_eur IS NOT NULL
ORDER BY
  award_value_eur DESC
LIMIT 20
