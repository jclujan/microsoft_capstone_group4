WITH bins AS (
  SELECT
    CASE
      WHEN award_value_eur <= 50000 THEN 1
      WHEN award_value_eur <= 100000 THEN 2
      WHEN award_value_eur <= 250000 THEN 3
      WHEN award_value_eur <= 500000 THEN 4
      WHEN award_value_eur <= 750000 THEN 5
      WHEN award_value_eur <= 1000000 THEN 6
      WHEN award_value_eur <= 2000000 THEN 7
      WHEN award_value_eur <= 3000000 THEN 8
      WHEN award_value_eur <= 5000000 THEN 9
      WHEN award_value_eur <= 7500000 THEN 10
      WHEN award_value_eur <= 10000000 THEN 11
      WHEN award_value_eur <= 15000000 THEN 12
      WHEN award_value_eur <= 25000000 THEN 13
      WHEN award_value_eur <= 50000000 THEN 14
      WHEN award_value_eur <= 100000000 THEN 15
      ELSE 16
    END as bin_order,
    CASE
      WHEN award_value_eur <= 50000 THEN '€0–€50K'
      WHEN award_value_eur <= 100000 THEN '€50K–€100K'
      WHEN award_value_eur <= 250000 THEN '€100K–€250K'
      WHEN award_value_eur <= 500000 THEN '€250K–€500K'
      WHEN award_value_eur <= 750000 THEN '€500K–€750K'
      WHEN award_value_eur <= 1000000 THEN '€750K–€1M'
      WHEN award_value_eur <= 2000000 THEN '€1M–€2M'
      WHEN award_value_eur <= 3000000 THEN '€2M–€3M'
      WHEN award_value_eur <= 5000000 THEN '€3M–€5M'
      WHEN award_value_eur <= 7500000 THEN '€5M–€7.5M'
      WHEN award_value_eur <= 10000000 THEN '€7.5M–€10M'
      WHEN award_value_eur <= 15000000 THEN '€10M–€15M'
      WHEN award_value_eur <= 25000000 THEN '€15M–€25M'
      WHEN award_value_eur <= 50000000 THEN '€25M–€50M'
      WHEN award_value_eur <= 100000000 THEN '€50M–€100M'
      ELSE '€100M+'
    END as bin_label,
    CASE
      WHEN award_value_eur <= 50000 THEN 25000
      WHEN award_value_eur <= 100000 THEN 75000
      WHEN award_value_eur <= 250000 THEN 175000
      WHEN award_value_eur <= 500000 THEN 375000
      WHEN award_value_eur <= 750000 THEN 625000
      WHEN award_value_eur <= 1000000 THEN 875000
      WHEN award_value_eur <= 2000000 THEN 1500000
      WHEN award_value_eur <= 3000000 THEN 2500000
      WHEN award_value_eur <= 5000000 THEN 4000000
      WHEN award_value_eur <= 7500000 THEN 6250000
      WHEN award_value_eur <= 10000000 THEN 8750000
      WHEN award_value_eur <= 15000000 THEN 12500000
      WHEN award_value_eur <= 25000000 THEN 20000000
      WHEN award_value_eur <= 50000000 THEN 37500000
      WHEN award_value_eur <= 100000000 THEN 75000000
      ELSE 100000000
    END as bin_midpoint
  FROM
    workspace.gold.awards_analysis
  WHERE
    award_value_eur IS NOT NULL
    AND award_value_eur > 0
)
SELECT
  bin_order,
  bin_label,
  bin_midpoint,
  COUNT(*) as award_count
FROM
  bins
GROUP BY
  bin_order,
  bin_label,
  bin_midpoint
ORDER BY
  bin_order
