# Reusable SQL Query Patterns

## Standard Filters (always include)

```sql
-- US only, positive TVT, date-partitioned
WHERE country = 'US'
  AND date >= CURRENT_DATE - INTERVAL {days} DAYS
  AND tvt_millisec > 0
```

## Linear Sessions Only

```sql
WHERE content_type = 'LINEAR'
  AND country = 'US'
  AND date >= CURRENT_DATE - INTERVAL {days} DAYS
  AND tvt_millisec > 0
```

## Join Video Session to Content Info

```sql
FROM core_prod.session.video_session vs
JOIN core_prod.tubidw.content_info ci
    ON vs.content_id = ci.content_id
```

## Join to EPG for Program-Level Linear Data

```sql
FROM core_prod.tubidw.linear_epg_video_sessions lev
LEFT JOIN core_prod.tubidw.epg_schedules es
    ON lev.schedule_id = es.id
```

## User Segment CTE

```sql
WITH user_segments AS (
    SELECT
        device_id,
        MAX(CASE WHEN content_type = 'LINEAR' THEN 1 ELSE 0 END) AS has_linear,
        MAX(CASE WHEN content_type IN ('MOVIE', 'SERIES') THEN 1 ELSE 0 END) AS has_vod,
        SUM(CASE WHEN content_type = 'LINEAR' THEN tvt_millisec ELSE 0 END) / 3600000.0 AS linear_hours,
        SUM(CASE WHEN content_type IN ('MOVIE', 'SERIES') THEN tvt_millisec ELSE 0 END) / 3600000.0 AS vod_hours,
        SUM(tvt_millisec) / 3600000.0 AS total_hours
    FROM core_prod.session.video_session
    WHERE country = 'US'
      AND date >= CURRENT_DATE - INTERVAL {days} DAYS
      AND tvt_millisec > 0
    GROUP BY device_id
)
```

## New vs Returning User CTE

```sql
WITH user_tenure AS (
    SELECT
        vs.device_id,
        CASE
            WHEN dfm.device_first_view_ts >= CURRENT_DATE - INTERVAL 7 DAYS THEN 'new_7d'
            WHEN dfm.device_first_view_ts >= CURRENT_DATE - INTERVAL 30 DAYS THEN 'new_30d'
            ELSE 'returning'
        END AS cohort
    FROM core_prod.session.video_session vs
    JOIN core_prod.tubidw.device_first_metrics dfm ON vs.device_id = dfm.device_id
    WHERE vs.country = 'US'
      AND vs.date >= CURRENT_DATE - INTERVAL {days} DAYS
    GROUP BY vs.device_id, dfm.device_first_view_ts
)
```

## Platform Grouping

```sql
CASE
    WHEN platform IN ('ROKU', 'AMAZONFIRETV', 'SAMSUNG', 'VIZIO', 'LGTV', 'ANDROIDTV') THEN 'OTT'
    WHEN platform IN ('IPHONE', 'IPAD', 'ANDROID', 'FIRETABLET') THEN 'Mobile'
    WHEN platform IN ('PS5', 'XBOX', 'NINTENDO') THEN 'Gaming'
    WHEN platform = 'WEB' THEN 'Web'
    ELSE 'Other'
END AS platform_group
```

## Engagement Tier Classification

```sql
CASE
    WHEN tvt_millisec < 10000 THEN 'bounce'
    WHEN tvt_millisec < 60000 THEN 'brief_try'
    WHEN tvt_millisec < 300000 THEN 'sampled'
    WHEN tvt_millisec < 1800000 THEN 'engaged'
    WHEN tvt_millisec < 3600000 THEN 'deep'
    ELSE 'very_deep'
END AS engagement_tier
```

## Presentation → Watch Funnel

```sql
SELECT
    container,
    page_type,
    COUNT(*) AS presentations,
    SUM(CASE WHEN tvt_sec > 0 THEN 1 ELSE 0 END) AS watched,
    ROUND(SUM(CASE WHEN tvt_sec > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS ctr_pct,
    SUM(tvt_sec) / 3600.0 AS total_watch_hours
FROM core_dev.dsa.dsac_viewpres_vidsession_sample
WHERE ds >= CURRENT_DATE - INTERVAL {days} DAYS
GROUP BY container, page_type
```

## Daily Trend Template

```sql
SELECT
    date AS dt,
    COUNT(DISTINCT device_id) AS unique_viewers,
    COUNT(*) AS sessions,
    SUM(tvt_millisec) / 3600000.0 AS total_hours
FROM core_prod.session.video_session
WHERE {filters}
GROUP BY date
ORDER BY date
```

## CLI Usage

```bash
# Run a canonical query
python -m linear_data.cli run linear_tvt_share --days 30

# Run raw SQL
python -m linear_data.cli sql "SELECT COUNT(*) FROM core_prod.session.video_session WHERE date = CURRENT_DATE - 1 AND content_type = 'LINEAR'"

# List all canonical queries
python -m linear_data.cli list

# Test connection
python -m linear_data.cli test
```
