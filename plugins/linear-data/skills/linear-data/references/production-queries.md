# Production-Verified Linear Queries

> These queries are verified against production Databricks. Use as-is or adapt.
> Parameters use `:date_range.min`, `:date_range.max`, `:country` syntax from Databricks SQL dashboards.
> For CLI usage, replace with literal values.

## Additional Tables Discovered

### `core_prod.content.content_info` (preferred for content metadata)

Note: content_info exists in BOTH `core_prod.content` and `core_prod.tubidw`. The queries below use `core_prod.content.content_info`.

### `core_prod.analytics.viewable_impression` — Container Impression Tracking

| Column | Type | Description |
|---|---|---|
| `container_id` | string | Container slug (e.g., `recommended_linear_channels`) |
| `date` | date | Partition key |
| `platform` | string | Device platform |
| `row_pos` | int | Row position of container on page |
| `personalization_id` | string | Unique impression ID |
| `device_id` | string | Device identifier |

**Key Linear Containers:**
- `recommended_linear_channels`
- `live_news`
- `sports_on_tubi`
- `entertainment`
- `news`
- `sports_on_now`

### `core_dev.dsa.dsac_single_title_reporting_bymonth` — Pre-Aggregated Monthly Reporting

| Column | Type | Description |
|---|---|---|
| `dt` | date | Month (truncated) |
| `program_id` | bigint | Program identifier |
| `program_name` | string | Program/channel name |
| `primary_genre` | string | Genre |
| `content_type` | string | `linear`, `movie`, `series` |
| `platform` | string | Platform or `All Platforms` |
| `country` | string | Country code |
| `tvt_hours` | float | Total view time in hours |
| `d1_tvt_hours` | float | Day-1 TVT hours |
| `viewers` | bigint | Unique viewers |
| `d1_viewers` | bigint | Day-1 unique viewers |
| `conversion_5min_pct` | float | 5-minute conversion % |
| `d1_conversion_5min_pct` | float | Day-1 5-min conversion % |
| `total_revenue` | float | Revenue |

### `core_prod.events.presentation_event` — Full Presentation Event

| Column | Type | Description |
|---|---|---|
| `device_id` | string | Device identifier |
| `user_id` | string | User ID |
| `personalization_id` | string | Unique presentation ID |
| `date` | date | Partition key |
| `containers` | array | Array of container structs with `.id` field |

---

## Query 1: Channel Performance Dashboard

Full channel performance with TVT, conversion, D1 metrics, revenue, and homepage position.

```sql
WITH content_info AS (
    SELECT DISTINCT
        program_id,
        program_name,
        primary_genre,
        import_id
    FROM core_prod.content.content_info
    WHERE content_type = 'LINEAR'
),

performance AS (
    SELECT DISTINCT
        c.program_id,
        c.program_name,
        c.primary_genre,
        c.import_id,
        SUM(v.tvt_millisec) / 3600000.0 AS tvt_hour,
        SUM(CASE WHEN DATE_TRUNC('day', device_first_view_ts) = DATE_TRUNC('day', start_ts)
            THEN v.tvt_millisec END) / 3600000.0 AS d1_tvt_hour,
        APPROX_COUNT_DISTINCT(CASE WHEN v.tvt_millisec > 300000
            AND DATE_TRUNC('day', device_first_view_ts) = DATE_TRUNC('day', start_ts)
            THEN v.device_id END, .03) AS d1_qualified_devices,
        APPROX_COUNT_DISTINCT(CASE WHEN v.tvt_millisec > 300000
            THEN v.device_id END, .03) AS qualified_devices,
        APPROX_COUNT_DISTINCT(CASE WHEN v.tvt_millisec > 10000
            AND DATE_TRUNC('day', device_first_view_ts) = DATE_TRUNC('day', start_ts)
            THEN v.device_id END, .03) AS d1_devices,
        APPROX_COUNT_DISTINCT(CASE WHEN v.tvt_millisec > 10000
            THEN v.device_id END, .03) AS total_viewer_devices,
        APPROX_COUNT_DISTINCT(v.device_id, .03) AS total_visitor_devices,
        APPROX_COUNT_DISTINCT(CASE WHEN DATE_TRUNC('day', device_first_view_ts) = DATE_TRUNC('day', start_ts)
            THEN v.device_id END, .03) AS total_d1_visitor_devices
    FROM core_prod.tubidw.video_session v
    JOIN content_info c ON v.content_id = c.program_id
    WHERE v.content_type = 'LINEAR'
      AND ds BETWEEN :date_range_min AND :date_range_max
    GROUP BY 1, 2, 3, 4
    ORDER BY tvt_hour DESC
),

presentations AS (
    SELECT
        c.program_id,
        c.program_name,
        c.primary_genre,
        MEDIAN(CASE WHEN content_promotional_lever = 'PROMOTIONAL_LEVER_NONE' THEN row_num END) AS avg_row_pos,
        MEDIAN(CASE WHEN content_promotional_lever = 'PROMOTIONAL_LEVER_NONE' THEN col_num END) AS avg_col_pos,
        MEDIAN(CASE WHEN content_promotional_lever = 'PROMOTIONAL_LEVER_PROMOTER_SVC_PINNING' THEN row_num END) AS avg_pinned_row_pos,
        MEDIAN(CASE WHEN content_promotional_lever = 'PROMOTIONAL_LEVER_PROMOTER_SVC_PINNING' THEN col_num END) AS avg_pinned_col_pos
    FROM core_dev.dsa.dsac_viewpres_vidsession_sample p
    JOIN content_info c ON p.program_id = c.program_id
    WHERE p.program_id IS NOT NULL
      AND p.page_type = 'HomePage'
      AND ds BETWEEN :date_range_min AND :date_range_max
    GROUP BY 1, 2, 3
),

epg_rev AS (
    SELECT DISTINCT
        c.program_id,
        c.program_name,
        c.primary_genre,
        SUM(total_revenue) AS rev
    FROM core_prod.tubidw.content_earnings_daily e
    JOIN content_info c ON e.content_id = c.program_id
    WHERE ds BETWEEN :date_range_min AND :date_range_max
    GROUP BY 1, 2, 3
)

SELECT
    p.program_id,
    p.program_name,
    p.primary_genre,
    p.import_id,
    p.tvt_hour,
    p.d1_tvt_hour,
    p.d1_devices,
    p.total_viewer_devices,
    p.tvt_hour / p.total_viewer_devices AS AVT,
    p.d1_tvt_hour / p.d1_devices AS D1_AVT,
    p.qualified_devices / p.total_visitor_devices AS five_min_conversion,
    p.d1_qualified_devices / p.total_d1_visitor_devices AS d1_5min_conversion,
    r.rev,
    x.avg_row_pos,
    x.avg_col_pos,
    x.avg_pinned_row_pos,
    x.avg_pinned_col_pos
FROM performance p
LEFT JOIN epg_rev r ON p.program_id = r.program_id
LEFT JOIN presentations x ON p.program_id = x.program_id
ORDER BY p.tvt_hour DESC
```

---

## Query 2: Monthly Channel Trend with Positioning

Uses pre-aggregated monthly reporting table for historical trends.

```sql
WITH base AS (
    SELECT
        dt,
        program_id,
        program_name,
        primary_genre,
        import_id,
        tvt_hours,
        d1_tvt_hours,
        viewers,
        d1_viewers,
        tvt_hours / viewers AS AVT,
        d1_tvt_hours / d1_viewers AS d1_AVT,
        conversion_5min_pct,
        d1_conversion_5min_pct,
        total_revenue
    FROM core_dev.dsa.dsac_single_title_reporting_bymonth
    WHERE content_type = 'linear'
      AND platform = 'All Platforms'
      AND dt >= '2021-01-01'
      AND array_contains(:country, country)
    ORDER BY tvt_hours DESC
),

content AS (
    SELECT c.program_id
    FROM core_prod.content.content_info c
    WHERE content_type = 'LINEAR'
),

presentations AS (
    SELECT
        DATE_TRUNC('month', ds) AS ms,
        p.program_id,
        MEDIAN(CASE WHEN content_promotional_lever = 'PROMOTIONAL_LEVER_NONE' THEN row_num END) AS avg_row_pos,
        MEDIAN(CASE WHEN content_promotional_lever = 'PROMOTIONAL_LEVER_NONE' THEN col_num END) AS avg_col_pos,
        MEDIAN(CASE WHEN content_promotional_lever = 'PROMOTIONAL_LEVER_PROMOTER_SVC_PINNING' THEN row_num END) AS avg_pinned_row_pos,
        MEDIAN(CASE WHEN content_promotional_lever = 'PROMOTIONAL_LEVER_PROMOTER_SVC_PINNING' THEN col_num END) AS avg_pinned_col_pos
    FROM core_dev.dsa.dsac_viewpres_vidsession_sample p
    JOIN content c ON p.program_id = c.program_id
    WHERE p.program_id IS NOT NULL
      AND p.page_type = 'HomePage'
      AND array_contains(:country, country)
    GROUP BY 1, 2
)

SELECT
    b.*,
    p.avg_row_pos,
    p.avg_col_pos,
    p.avg_pinned_row_pos,
    p.avg_pinned_col_pos
FROM base b
LEFT JOIN presentations p ON b.program_id = p.program_id AND b.dt = p.ms
```

---

## Query 3: EPG Program-Level Performance (Schedule-Aware)

Full program airing performance with live broadcast flag, revenue, avg minute audience, and presentation positioning.

```sql
WITH content_info AS (
    SELECT DISTINCT program_id, primary_genre
    FROM core_prod.content.content_info
    WHERE content_type = 'LINEAR'
),

device_first_metrics AS (
    SELECT DISTINCT device_id, device_first_view_ts
    FROM core_prod.tubidw.device_first_metrics
),

epg_performance AS (
    SELECT DISTINCT
        v.start_air_ts,
        v.end_air_ts,
        v.content_id,
        v.callsign,
        v.schedule_id,
        v.program_title,
        v.episode_title,
        SUM(v.tvt_millisec) / 3600000.0 AS tvt_hour,
        SUM(CASE WHEN DATE_TRUNC('day', device_first_view_ts) = DATE_TRUNC('day', start_air_ts)
            THEN v.tvt_millisec END) / 3600000.0 AS d1_tvt_hr,
        APPROX_COUNT_DISTINCT(CASE WHEN v.tvt_millisec > 300000 THEN v.device_id END, .03) AS qualified_devices,
        APPROX_COUNT_DISTINCT(CASE WHEN v.tvt_millisec > 300000
            AND DATE_TRUNC('day', device_first_view_ts) = DATE_TRUNC('day', start_air_ts)
            THEN v.device_id END, .03) AS d1_qualified_devices,
        APPROX_COUNT_DISTINCT(CASE WHEN v.tvt_millisec > 10000
            AND DATE_TRUNC('day', device_first_view_ts) = DATE_TRUNC('day', start_air_ts)
            THEN v.device_id END, .03) AS d1_devices,
        APPROX_COUNT_DISTINCT(CASE WHEN v.tvt_millisec > 10000 THEN v.device_id END, .03) AS total_viewer_devices,
        APPROX_COUNT_DISTINCT(v.device_id, .03) AS total_visitor_devices,
        APPROX_COUNT_DISTINCT(CASE WHEN DATE_TRUNC('day', device_first_view_ts) = DATE_TRUNC('day', start_air_ts)
            THEN v.device_id END, .03) AS d1_visitor_devices,
        CASE
            WHEN DATEDIFF(minute, start_air_ts, end_air_ts) IS NOT NULL
                AND DATEDIFF(minute, start_air_ts, end_air_ts) != 0
            THEN (SUM(tvt_millisec) / 60000.0)::float * 1.0 / DATEDIFF(minute, start_air_ts, end_air_ts)
            ELSE 1
        END AS avg_min_audience
    FROM core_prod.tubidw.linear_epg_video_sessions v
    LEFT JOIN device_first_metrics d ON v.device_id = d.device_id
    WHERE v.start_air_ts BETWEEN :date_range_min AND :date_range_max
      AND array_contains(:country, country)
    GROUP BY 1, 2, 3, 4, 5, 6, 7
    ORDER BY tvt_hour DESC
),

epg_rev AS (
    SELECT DISTINCT
        epg_schedule_id,
        SUM(total_revenue) AS rev
    FROM core_prod.tubidw.linear_epg_earnings_hourly
    WHERE hs BETWEEN :date_range_min AND :date_range_max
      AND array_contains(:country, country)
    GROUP BY 1
),

schedule_info AS (
    SELECT DISTINCT id, content_id_type, live_broadcast
    FROM core_prod.tubidw.epg_schedules
    WHERE start_time BETWEEN :date_range_min AND :date_range_max
),

presentations AS (
    SELECT
        pres_ts,
        p.program_id,
        p.content_promotional_lever,
        p.row_num,
        p.col_num
    FROM core_dev.dsa.dsac_viewpres_vidsession_sample p
    JOIN content_info c ON p.program_id = c.program_id
    WHERE ds BETWEEN :date_range_min AND :date_range_max
      AND p.program_id IS NOT NULL
      AND p.page_type = 'HomePage'
      AND array_contains(:country, country)
)

SELECT
    p.start_air_ts,
    p.end_air_ts,
    from_utc_timestamp(p.start_air_ts, 'America/New_York') AS start_air_ts_est,
    from_utc_timestamp(p.end_air_ts, 'America/New_York') AS end_air_ts_est,
    DATE_DIFF(MINUTE, p.start_air_ts, p.end_air_ts) AS duration_min,
    p.content_id,
    p.callsign,
    s.content_id_type,
    s.live_broadcast,
    c.primary_genre,
    p.schedule_id,
    p.program_title,
    p.episode_title,
    p.tvt_hour,
    p.d1_tvt_hr,
    p.d1_devices,
    p.total_viewer_devices,
    p.tvt_hour / p.total_viewer_devices AS AVT,
    p.d1_tvt_hr / p.d1_devices AS D1_AVT,
    p.qualified_devices / p.total_visitor_devices AS five_min_conversion,
    p.d1_qualified_devices / p.d1_visitor_devices AS D1_5_min_conversion,
    p.avg_min_audience,
    r.rev,
    MEDIAN(CASE WHEN pr.content_promotional_lever = 'PROMOTIONAL_LEVER_NONE' THEN pr.row_num END) AS avg_row_pos,
    MEDIAN(CASE WHEN pr.content_promotional_lever = 'PROMOTIONAL_LEVER_NONE' THEN pr.col_num END) AS avg_col_pos,
    MEDIAN(CASE WHEN pr.content_promotional_lever = 'PROMOTIONAL_LEVER_PROMOTER_SVC_PINNING' THEN pr.row_num END) AS avg_pinned_row_pos,
    MEDIAN(CASE WHEN pr.content_promotional_lever = 'PROMOTIONAL_LEVER_PROMOTER_SVC_PINNING' THEN pr.col_num END) AS avg_pinned_col_pos
FROM epg_performance p
LEFT JOIN epg_rev r ON p.schedule_id = r.epg_schedule_id
LEFT JOIN content_info c ON p.content_id = c.program_id
LEFT JOIN schedule_info s ON p.schedule_id = s.id
LEFT JOIN presentations pr
    ON pr.pres_ts BETWEEN p.start_air_ts AND p.end_air_ts
    AND pr.program_id = p.content_id
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23
ORDER BY p.start_air_ts DESC
```

---

## Query 4: Linear Container Row Position Analysis

Track where linear containers appear on homepage over time for a specific device.

```sql
WITH device AS (
    SELECT
        container_id,
        date,
        CASE
            WHEN UPPER(platform) IN ('IPHONE','ANDROID','ANDROID-SAMSUNG','ANDROID_SAMSUNG',
                'FOR_SAMSUNG','IOS_WEB','IOS','IPAD','FIRETABLET') THEN 'MOBILE'
            WHEN UPPER(platform) IN ('WEB') THEN 'WEB'
            ELSE 'OTT'
        END AS platform_type,
        row_pos,
        personalization_id,
        vi.device_id
    FROM core_prod.analytics.viewable_impression vi
    WHERE vi.date >= CURRENT_DATE - INTERVAL 45 DAYS
      AND container_id IN (
          'recommended_linear_channels', 'live_news', 'sports_on_tubi',
          'entertainment', 'news', 'sports_on_now'
      )
)

SELECT
    date,
    platform_type,
    container_id,
    AVG(row_pos) AS average_row_position,
    APPROX_PERCENTILE(row_pos, 0.5) AS median_row_position,
    APPROX_PERCENTILE(row_pos, 0.9) AS p90_row_position,
    COUNT(DISTINCT personalization_id) AS total_impressions,
    COUNT(DISTINCT device_id) AS total_devices
FROM device
GROUP BY 1, 2, 3
```

---

## Query 5: Container Impression History (Per Device)

```sql
SELECT date, container_id, COUNT(*) AS cnt
FROM core_prod.analytics.viewable_impression vi
WHERE device_id = :device_id
  AND date >= CURRENT_DATE - INTERVAL 1 YEAR
  AND container_id IN (
      'recommended_linear_channels', 'live_news', 'sports_on_tubi',
      'entertainment', 'news', 'sports_on_now'
  )
GROUP BY container_id, date
ORDER BY container_id ASC
```

---

## Query 6: Presentation Event Container Ordering

Understand container ordering from raw presentation events.

```sql
WITH tmp AS (
    SELECT date, pe.device_id, pe.user_id, pe.personalization_id, pe.containers
    FROM core_prod.events.presentation_event pe
    WHERE device_id = :device_id
      AND date >= CURRENT_DATE - INTERVAL 7 DAYS
),

container_df AS (
    SELECT date, device_id, user_id, personalization_id,
           POSEXPLODE(containers) AS (container_idx, container)
    FROM tmp
),

content_df AS (
    SELECT date, user_id, device_id, personalization_id,
           container_idx, container.id AS container_id
    FROM container_df
)

SELECT *
FROM content_df
WHERE container_id IN (
    'recommended_linear_channels', 'live_news', 'sports_on_tubi',
    'entertainment', 'news', 'sports_on_now'
)
ORDER BY date, personalization_id, container_idx
```

---

## Key Patterns From Production Queries

### Content Promotional Lever Values
- `PROMOTIONAL_LEVER_NONE` — organic placement
- `PROMOTIONAL_LEVER_PROMOTER_SVC_PINNING` — pinned by promoter service

### APPROX_COUNT_DISTINCT Usage
Production queries use `APPROX_COUNT_DISTINCT(expr, .03)` with 3% relative error for performance on large datasets.

### D1 (Day-1) Metrics Pattern
```sql
-- Day-1 = user's first day on platform
DATE_TRUNC('day', device_first_view_ts) = DATE_TRUNC('day', start_ts)
```

### Viewer vs Visitor Distinction
- **Visitor**: any device that touched the content (`device_id` appears)
- **Viewer**: device with >10s watch time (`tvt_millisec > 10000`)
- **Qualified viewer**: device with >5min watch time (`tvt_millisec > 300000`)

### Average Minute Audience
```sql
(SUM(tvt_millisec) / 60000.0) / DATEDIFF(minute, start_air_ts, end_air_ts)
```
Represents average number of viewers watching at any given minute during the program.
