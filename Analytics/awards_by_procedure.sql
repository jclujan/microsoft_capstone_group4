SELECT
  procedure_type,
  COUNT(*) as award_count,
  SUM(award_value_eur) as total_value,
  AVG(award_value_eur) as avg_value
FROM
  workspace.gold.awards_analysis
WHERE
  award_value_eur IS NOT NULL
  AND procedure_type IS NOT NULL
  AND procedure_type != ''
GROUP BY
  procedure_type
ORDER BY
  total_value DESC
