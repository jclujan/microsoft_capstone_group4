SELECT
  buyer_country,
  COUNT(DISTINCT buyer_name) as buyer_count,
  SUM(total_contracts) as notice_count,
  SUM(total_awarded_value_eur) as total_value
FROM
  workspace.gold.buyer_profiles
GROUP BY
  buyer_country
ORDER BY
  total_value DESC
