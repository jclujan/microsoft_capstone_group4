SELECT
  CASE
    WHEN s.cpv_division = '45' THEN 'Construction'
    WHEN s.cpv_division = '71' THEN 'Engineering Services'
    WHEN s.cpv_division = '72' THEN 'IT Services'
    WHEN s.cpv_division = '79' THEN 'Business Services'
    WHEN s.cpv_division = '30' THEN 'Office & Computing'
    WHEN s.cpv_division = '33' THEN 'Medical Equipment'
    WHEN s.cpv_division = '34' THEN 'Transport Equipment'
    WHEN s.cpv_division = '50' THEN 'Repair & Maintenance'
    WHEN s.cpv_division = '60' THEN 'Transport Services'
    WHEN s.cpv_division = '80' THEN 'Education & Training'
    WHEN s.cpv_division = '85' THEN 'Health & Social Services'
    WHEN s.cpv_division = '90' THEN 'Waste & Cleaning'
    WHEN s.cpv_division = '09' THEN 'Energy & Utilities'
    WHEN s.cpv_division = '15' THEN 'Food & Beverages'
    WHEN s.cpv_division = '18' THEN 'Clothing & Textiles'
    WHEN s.cpv_division = '22' THEN 'Printed Materials'
    WHEN s.cpv_division = '24' THEN 'Chemicals'
    WHEN s.cpv_division = '39' THEN 'Furniture'
    WHEN s.cpv_division = '48' THEN 'Software'
    WHEN s.cpv_division = '55' THEN 'Hotel & Catering'
    WHEN s.cpv_division = '63' THEN 'Travel & Logistics'
    WHEN s.cpv_division = '64' THEN 'Postal Services'
    WHEN s.cpv_division = '66' THEN 'Financial Services'
    WHEN s.cpv_division = '70' THEN 'Real Estate'
    WHEN s.cpv_division = '73' THEN 'Research Services'
    WHEN s.cpv_division = '75' THEN 'Administration'
    WHEN s.cpv_division = '76' THEN 'Oil & Gas'
    WHEN s.cpv_division = '77' THEN 'Agricultural Services'
    WHEN s.cpv_division = '92' THEN 'Recreation & Culture'
    ELSE d.cpv_label
  END as sector_name,
  s.contract_count,
  s.total_award_value_eur as total_value,
  s.distinct_buyers
FROM
  workspace.gold.cpv_summary s
    LEFT JOIN workspace.gold.dim_cpv d
      ON s.cpv_division = d.cpv_division
ORDER BY
  s.total_award_value_eur DESC
LIMIT 20
