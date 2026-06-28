SELECT
  CASE
    WHEN LENGTH(buyer_name) <= 50 THEN buyer_name
    ELSE CONCAT(SUBSTRING(buyer_name, 1, 47), '...')
  END as buyer_name,
  SUM(award_value_eur) as total_value,
  COUNT(*) as award_count,
  AVG(award_value_eur) as avg_award_value
FROM
  workspace.gold.awards_analysis
WHERE
  award_value_eur IS NOT NULL
GROUP BY
  buyer_name
ORDER BY
  total_value DESC
LIMIT 15
