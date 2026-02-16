# Dimensions Glossary — Linear Data

> Canonical dimension definitions for Tubi Linear/FAST TV analysis.

## Platform Dimensions

| Dimension | Column | Values | Notes |
|---|---|---|---|
| Platform Type | `platform` | OTT, Mobile, Web | OTT = connected TV devices |
| Device Platform | `device_platform` | roku, amazon_fire_tv, android_tv, samsung, lg, vizio, ios, android, web | Specific device/OS |
| App Version | `app_version` | varies | Major.Minor.Patch |

## Content Dimensions

| Dimension | Column | Values | Notes |
|---|---|---|---|
| Content Type | `content_type` | LINEAR, VOD | LINEAR = live channels |
| Channel | `content_id` | numeric ID | For LINEAR, content_id = channel |
| Channel Name | `title` (via content_info) | string | Human-readable channel name |
| Genre | `category` | Entertainment, News, Sports | Top-level genre |
| Sub-genre | `sub_category` | True Crime, Sci-Fi, Comedy, etc. | Detailed category |

## User Dimensions

| Dimension | Column | Values | Notes |
|---|---|---|---|
| User ID | `user_id` | numeric or NULL | NULL = unregistered (~60-70% of viewers) |
| Device ID | `device_id` | string | Always present, unique per device |
| User Segment | derived | linear_only, linear_vod, vod_only | Based on content_type mix in period |
| Registration Status | `user_id IS NOT NULL` | boolean | Only ~30-40% are registered |

## Session Dimensions

| Dimension | Column | Values | Notes |
|---|---|---|---|
| Session ID | `session_id` | string | Unique per viewing session |
| Entry Point | `page_source` | homepage, deeplink, epg, search, crm, direct, unknown | 49.8% are unattributed |
| Country | `country` | US, MX, CA, GB, etc. | Filter on country='US' for US metrics |

## Time Dimensions

| Dimension | Column | Values | Notes |
|---|---|---|---|
| Date | `date` | YYYY-MM-DD | **Always filter on this partition key** |
| Hour | `hour` | 0-23 | For time-of-day analysis |
| Day of Week | derived from `date` | Mon-Sun | Weekday vs weekend patterns |

## Monetization Dimensions

| Dimension | Column | Values | Notes |
|---|---|---|---|
| Revenue | from `content_earnings_daily` | numeric | Daily channel-level revenue |
| Ad Impressions | from `viewable_impression` | count | Container-level impressions |
| Fill Rate | derived | percentage | Ads served / ad slots available |
