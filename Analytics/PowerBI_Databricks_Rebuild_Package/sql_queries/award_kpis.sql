SELECT
  COUNT(*) as total_awards,
  SUM(award_value_eur) as total_value,
  AVG(award_value_eur) as avg_value,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY award_value_eur) as median_value,
  MAX(award_value_eur) as largest_award
FROM
  workspace.gold.awards_analysis
WHERE
  award_value_eur IS NOT NULL
