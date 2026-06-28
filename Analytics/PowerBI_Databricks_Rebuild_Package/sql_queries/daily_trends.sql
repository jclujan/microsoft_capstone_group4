SELECT
  activity_date,
  total_award_value_eur,
  cn_count + can_count as total_notices
FROM
  workspace.gold.daily_activity
WHERE
  activity_date >= '2026-05-01'
  AND total_award_value_eur IS NOT NULL
ORDER BY
  activity_date
