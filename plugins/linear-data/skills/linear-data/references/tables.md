# Databricks Tables Reference

> Source: Data Access Guide SSOT. Accuracy verified against production queries.

## Connection

```
DATABRICKS_HOST=<workspace>.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<warehouse_id>
DATABRICKS_TOKEN=<PAT>
DATABRICKS_CATALOG=core_prod
DATABRICKS_SCHEMA=tubidw
```

## Schema Map

| Schema | Purpose |
|---|---|
| `core_prod.session` | Primary video session data |
| `core_prod.tubidw` | Dimensional warehouse — content, EPG, earnings |
| `core_prod.aggregated` | Pre-aggregated metrics (daily/weekly rollups) |
| `core_prod.content` | Content metadata |
| `core_prod.dsa` | Display Signal Analysis — presentation & click tracking |
| `core_prod.client_raw` | Raw client-side event logs (JSON payloads) |
| `core_prod.analytics` | Analytics event stream |
| `core_prod.kpi` | KPI rollup tables |
| `core_prod.events` | Event-level data |
| `core_dev.dsa` | DSA sample/dev datasets |
| `core_dev.statsig` | Experiment results (A/B tests via Statsig) |

## Core Tables

### `core_prod.session.video_session` — Primary Viewing Data

The single most important table. One row per viewing session.

| Column | Type | Description |
|---|---|---|
| `device_id` | string | Anonymous device identifier |
| `user_id` | string | Registered user ID (NULL if anonymous) |
| `content_id` | bigint | Unique content identifier |
| `content_type` | string | `LINEAR`, `MOVIE`, `SERIES`, `SPORTS_EVENT` |
| `tvt_millisec` | bigint | Total Viewing Time in milliseconds |
| `start_ts` | timestamp | Session start (UTC) |
| `date` | date | **Partition key — always filter on this** |
| `platform` | string | Device platform |
| `page_source` | string | Where user navigated from |
| `container_slug` | string | UI container that surfaced the content |
| `country` | string | ISO country code |
| `program_id` | bigint | Parent program/series ID |

### `core_prod.tubidw.content_info` — Content Metadata

| Column | Type | Description |
|---|---|---|
| `content_id` | bigint | Primary key |
| `content_name` | string | Title |
| `content_type` | string | `MOVIE`, `SERIES`, `LINEAR`, `SPORTS_EVENT` |
| `program_id` | bigint | Parent program ID |
| `program_name` | string | Series/program name |
| `duration` | float | Duration in **minutes** (not ms!) |
| `active` | boolean | Currently available |
| `primary_genre` | string | Primary genre |

### `core_prod.tubidw.linear_epg_video_sessions` — Linear EPG Viewing

Schedule-aware linear viewing. Use when you need **program-level** data (not just channel).

| Column | Type | Description |
|---|---|---|
| `content_id` | bigint | Linear channel ID |
| `schedule_id` | bigint | EPG schedule entry ID |
| `program_title` | string | Name of the airing program |
| `tvt_millisec` | bigint | Viewing time |
| `start_air_ts` | timestamp | Program air start |
| `end_air_ts` | timestamp | Program air end |
| `device_id` | string | Device identifier |
| `platform` | string | Device platform |

### `core_prod.tubidw.epg_schedules` — Linear Schedule Grid

| Column | Type | Description |
|---|---|---|
| `id` | bigint | Schedule ID (join to linear_epg_video_sessions) |
| `content_id_type` | string | Type of scheduled content |
| `live_broadcast` | boolean | Whether it's live |
| `start_air_ts` | timestamp | Air start |
| `end_air_ts` | timestamp | Air end |

### `core_prod.tubidw.recent_analytics` — Event Stream

Navigation and interaction events. For funnel analysis, page transitions.

| Column | Type | Description |
|---|---|---|
| `device_id` | string | Device identifier |
| `ts` | timestamp | Event timestamp |
| `event_name` | string | Event type (e.g., `NavigateToPageEvent`) |
| `page_type` | string | Current page |
| `dest_page_type` | string | Destination page |
| `component_type` | string | UI component interacted with |
| `container_slug` | string | Container slug |
| `platform` | string | Device platform |
| `country` | string | Country code |

### `core_dev.dsa.dsac_viewpres_vidsession_sample` — Presentation Tracking

What content was shown to users and whether they watched. Critical for CTR and funnel.

| Column | Type | Description |
|---|---|---|
| `program_id` | bigint | Program identifier |
| `device_id` | string | Device identifier |
| `page_type` | string | Page where content was presented |
| `row_num` | int | Row position on page |
| `col_num` | int | Column position in row |
| `container` | string | Container name |
| `pres_dwell_sec` | float | How long item was visible |
| `tvt_sec` | float | Resulting viewing time (0 = no conversion) |
| `ds` | date | **Partition key** |

### `core_prod.tubidw.device_first_metrics` — New User Identification

| Column | Type | Description |
|---|---|---|
| `device_id` | string | Device identifier |
| `device_first_view_ts` | timestamp | First-ever view timestamp |

### Revenue Tables

| Table | Key Columns | Granularity |
|---|---|---|
| `core_prod.tubidw.content_earnings_daily` | `content_id`, `revenue`, `date` | Daily per content |
| `core_prod.tubidw.linear_epg_earnings_hourly` | `epg_schedule_id`, `total_revenue`, `hs` | Hourly per schedule |

### `core_prod.client_raw.client_logs` — Raw Client Events

| Column | Type | Description |
|---|---|---|
| `log_subtype` | string | Event type key |
| `platform` | string | Device platform |
| `message` | string | **JSON blob** — parse with `get_json_object()` |
| `device_id` | string | Device identifier |
| `recv_timestamp` | timestamp | Server receive time |

## Table Relationships

```
video_session
  ├── content_id → content_info (content_name, duration, primary_genre)
  ├── content_id → linear_epg_video_sessions (schedule_id, program_title)
  │                   └── schedule_id → epg_schedules (live_broadcast, air times)
  ├── device_id  → device_first_metrics (device_first_view_ts)
  └── content_id → content_earnings_daily (revenue)

recent_analytics
  └── device_id, event_name, page_type, container_slug

dsac_viewpres_vidsession_sample
  └── program_id, container, row_num, col_num, tvt_sec

client_logs
  └── device_id, log_subtype, message (JSON)
```

## Platform Values

| Category | Values |
|---|---|
| CTV | `ROKU`, `AMAZONFIRETV`, `SAMSUNG`, `VIZIO`, `LGTV`, `ANDROIDTV` |
| Mobile | `IPHONE`, `IPAD`, `ANDROID`, `FIRETABLET` |
| Gaming | `PS5`, `XBOX`, `NINTENDO` |
| Web | `WEB` |

## Page Source Values

`HomePage`, `VideoPlayerPage`, `LinearBrowsePage`, `SearchPage`, `ForYouPage`, `ContentDetailsPage`

## Key Gotchas

1. **Always filter on partition key** (`date` or `ds`) — queries without it do full table scans
2. **TVT can be negative** — always add `WHERE tvt_millisec > 0`
3. **`content_info.duration` is minutes**, not milliseconds — convert: `ci.duration * 60000.0`
4. **All timestamps are UTC**
5. **Linear `content_id` = channel**, not program — use `linear_epg_video_sessions` for program-level
6. **Only ~30-40% of viewers are registered** — be explicit about registered vs all users
7. **Roku client_logs incomplete** for some features (e.g., BWW) — use `recent_analytics` instead
8. **JSON in client_logs**: `get_json_object(message, '$.fieldName')`, cast as needed

## TVT Conversions

| From | To | Formula |
|---|---|---|
| ms → seconds | `tvt_millisec / 1000.0` |
| ms → minutes | `tvt_millisec / 60000.0` |
| ms → hours | `tvt_millisec / 3600000.0` |

## Engagement Tiers

| Tier | Threshold |
|---|---|
| Bounce/Surf | < 10 seconds |
| Brief try | 10s – 1 min |
| Sampled | 1 – 5 min |
| Engaged (qualified view) | 5+ min |
| Deep engagement | 30+ min |
| Very deep | 60+ min |

## Experiment (Statsig) Tables

For experiment `my_experiment`:

| Table | Purpose |
|---|---|
| `core_dev.statsig.first_exposures_my_experiment` | User group assignments |
| `core_dev.statsig.results_cumulative_my_experiment` | Aggregated results |
| `core_dev.statsig.pulse_dimensions_my_experiment` | Segment breakdowns |
