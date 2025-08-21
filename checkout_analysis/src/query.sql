WITH t AS (
  SELECT
    time,
    (regexp_replace(time,'h',''))::int AS hour,
    today,
    yesterday,
    same_day_last_week,
    avg_last_week,
    avg_last_month
  FROM checkout
)
SELECT
  hour,
  time,
  today,
  yesterday,
  same_day_last_week,
  avg_last_week,
  avg_last_month,

  -- percent differences (rounded)
  ROUND(100.0*(today - yesterday) / NULLIF(yesterday,0), 2) AS pct_vs_yesterday,
  ROUND(100.0*(today - same_day_last_week) / NULLIF(same_day_last_week,0), 2) AS pct_vs_same_day_last_week,
  ROUND(100.0*(today - avg_last_week) / NULLIF(avg_last_week,0), 2) AS pct_vs_avg_last_week,
  ROUND(100.0*(today - avg_last_month) / NULLIF(avg_last_month,0), 2) AS pct_vs_avg_last_month,

  CASE
    -- spike conditions
    WHEN today >= 2 * avg_last_week AND today >= 2 * avg_last_month THEN 'spike'
    -- drop conditions
    WHEN today <= 0.5 * avg_last_week AND today <= 0.5 * avg_last_month THEN 'drop'
    ELSE 'ok'
  END AS anomaly_flag


FROM t
ORDER BY hour;
