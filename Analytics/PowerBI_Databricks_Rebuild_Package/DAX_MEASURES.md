# Suggested DAX Measures

These assume you import or connect to the Gold tables directly.

```DAX
Total Notices =
SUM('daily_activity'[cn_count]) + SUM('daily_activity'[can_count])

Contract Notices =
SUM('daily_activity'[cn_count])

Award Notices =
SUM('daily_activity'[can_count])

Total Estimated Value EUR =
SUM('daily_activity'[total_award_value_eur])

Total Awards =
COUNTROWS('awards_analysis')

Total Award Value EUR =
SUM('awards_analysis'[award_value_eur])

Average Award Value EUR =
AVERAGE('awards_analysis'[award_value_eur])

Median Award Value EUR =
MEDIAN('awards_analysis'[award_value_eur])

Largest Award EUR =
MAX('awards_analysis'[award_value_eur])
```
