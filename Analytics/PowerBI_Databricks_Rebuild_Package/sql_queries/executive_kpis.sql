SELECT
  SUM(cn_count + can_count) as total_notices,
  SUM(cn_count) as contract_notices,
  SUM(can_count) as award_notices,
  SUM(total_award_value_eur) as total_estimated_value
FROM
  daily_activity
