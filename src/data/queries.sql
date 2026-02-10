-- CloudGuard AI - BigQuery Billing Queries
-- Optimized queries for cost-efficient billing analysis

-- Query 1: Current Month-to-Date Spend by Service
-- Uses partitioning to query only current month's data
WITH current_month_costs AS (
  SELECT
    service.description AS service_name,
    sku.description AS sku_name,
    SUM(cost) AS total_cost,
    SUM(CASE WHEN DATE(usage_start_time) = CURRENT_DATE() THEN cost ELSE 0 END) AS today_cost,
    MIN(usage_start_time) AS first_seen,
    MAX(usage_end_time) AS last_seen
  FROM `{project_id}.{dataset}.gcp_billing_export_v1_*`
  WHERE 
    _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_TRUNC(CURRENT_DATE(), MONTH))
    AND cost > 0
  GROUP BY service_name, sku_name
)
SELECT
  service_name,
  sku_name,
  total_cost,
  today_cost,
  first_seen,
  last_seen,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), first_seen, HOUR) AS hours_running,
  total_cost / NULLIF(TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), first_seen, HOUR), 0) AS cost_per_hour
FROM current_month_costs
ORDER BY total_cost DESC
LIMIT 10;

-- Query 2: Cost Velocity Analysis
-- Detects spending rate changes
WITH hourly_costs AS (
  SELECT
    TIMESTAMP_TRUNC(usage_start_time, HOUR) AS hour,
    SUM(cost) AS hourly_spend
  FROM `{project_id}.{dataset}.gcp_billing_export_v1_*`
  WHERE 
    _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY))
    AND cost > 0
  GROUP BY hour
)
SELECT
  hour,
  hourly_spend,
  AVG(hourly_spend) OVER (
    ORDER BY hour
    ROWS BETWEEN 24 PRECEDING AND CURRENT ROW
  ) AS rolling_24h_avg,
  STDDEV(hourly_spend) OVER (
    ORDER BY hour
    ROWS BETWEEN 24 PRECEDING AND CURRENT ROW
  ) AS rolling_24h_stddev
FROM hourly_costs
ORDER BY hour DESC
LIMIT 168;  -- 7 days

-- Query 3: Resource-Level Cost Breakdown
-- Identifies specific resources and their costs
SELECT
  project.id AS project_id,
  service.description AS service_name,
  sku.description AS sku_name,
  labels.value AS resource_name,
  location.region AS region,
  SUM(cost) AS total_cost,
  COUNT(DISTINCT DATE(usage_start_time)) AS days_active
FROM `{project_id}.{dataset}.gcp_billing_export_v1_*`,
  UNNEST(labels) AS labels
WHERE 
  _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_TRUNC(CURRENT_DATE(), MONTH))
  AND cost > 0
  AND labels.key = 'goog-compute-instance-name'  -- Adjust based on resource type
GROUP BY project_id, service_name, sku_name, resource_name, region
ORDER BY total_cost DESC
LIMIT 20;

-- Query 4: Daily Spend Pattern (for baseline tracking)
SELECT
  DATE(usage_start_time) AS date,
  EXTRACT(DAYOFWEEK FROM usage_start_time) AS day_of_week,
  SUM(cost) AS daily_spend
FROM `{project_id}.{dataset}.gcp_billing_export_v1_*`
WHERE 
  _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
  AND cost > 0
GROUP BY date, day_of_week
ORDER BY date DESC;

-- Query 5: Top Cost Contributors (Current Month)
-- Simplified query for watcher service
SELECT
  service.description AS service_name,
  SUM(cost) AS total_cost,
  ROUND(SUM(cost) / (SELECT SUM(cost) 
    FROM `{project_id}.{dataset}.gcp_billing_export_v1_*`
    WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_TRUNC(CURRENT_DATE(), MONTH))
  ) * 100, 2) AS percentage_of_total
FROM `{project_id}.{dataset}.gcp_billing_export_v1_*`
WHERE 
  _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_TRUNC(CURRENT_DATE(), MONTH))
  AND cost > 0
GROUP BY service_name
ORDER BY total_cost DESC
LIMIT 5;
