# Canonical Metric Definitions

## Viewing Metrics

| Metric | Definition | Formula | Notes |
|---|---|---|---|
| **TVT (Total View Time)** | Total milliseconds of content watched | `SUM(tvt_millisec)` | Always convert: `/3600000.0` for hours |
| **AVT (Average View Time)** | Average watch time per user per day | `TVT / unique_viewers / days` | Used for engagement depth |
| **Linear TVT Share** | Linear TVT as % of total platform TVT | `linear_tvt / total_tvt * 100` | Currently ~6.5% US (target: 9.0%) |
| **Qualified View** | Session with 5+ minutes of viewing | `tvt_millisec >= 300000` | Standard engagement threshold |
| **5min Linear Conversion** | % of linear impressions → 5min+ views | `qualified_views / impressions * 100` | Key funnel metric |

## User Metrics

| Metric | Definition | Notes |
|---|---|---|
| **Linear-only viewers** | Users with LINEAR tvt but no MOVIE/SERIES tvt in period | Currently ~4% of users |
| **Linear+VOD viewers** | Users with both LINEAR and MOVIE/SERIES tvt | Currently ~12% (was 18% before unpinning) |
| **VOD-only viewers** | Users with MOVIE/SERIES tvt but no LINEAR | Majority of users |
| **Linear first viewers** | Users whose first-ever Tubi view was LINEAR, 5min+ | 3-5% of new qualified viewers/month |

## Discovery / Funnel Metrics

| Metric | Definition | Source Table |
|---|---|---|
| **Impressions** | Number of times linear content was presented to user | `dsac_viewpres_vidsession_sample.presentations` |
| **Highlight rate** | % of impressions where user paused/highlighted | Event stream |
| **CTR (Click-through rate)** | % of presentations → tune-in | `conversions / presentations * 100` |
| **Tune-in conversion** | % of clicks that result in 5min+ viewing | session + presentation join |
| **Session attribution** | Entry point of a linear session | `video_session.page_source + container_slug` |

## Entry Point TVT Share (Sept 2024 baseline)

| Source | TVT Share |
|---|---|
| Homepage | 38.6% |
| Deeplink | 28.0% |
| Linear Browse/EPG | 15.9% |
| Other | 15.5% |
| Search | 2.0% |

## Content Performance Metrics

| Metric | Definition |
|---|---|
| **Channel TVT** | Total hours watched per channel |
| **Channel AVT** | Average hours/day per viewer per channel |
| **Channel performance benchmark** | Median: 98k hrs/mo, Mean: 212k hrs/mo |
| **Underperforming threshold** | <52k hrs/mo (bottom 33%) |
| **AVT benchmark** | Median: 1.5 hrs/day, Mean: 1.9 hrs/day |

## Monetization Metrics

| Metric | Definition |
|---|---|
| **Fill rate** | % of ad break slots actually filled with ads |
| **Ad load** | Minutes of ads per hour of content |
| **CPM** | Cost per thousand ad impressions |
| **Revenue per linear hour** | Total linear revenue / total linear TVT hours |
| **Ad slate rate** | % of ad breaks showing slate (unfilled) |

## Platform Distribution (Linear TVT)

| Platform | Linear TVT Share | Notes |
|---|---|---|
| Amazon Fire TV | 29% | #1 for linear (due to Live tab deeplinks) |
| Roku | 18% | #1 for VOD, #2 for linear |
| Android TV | 10% | |
| OTT total | 82% | |
| Mobile total | 14% | |
| Web | 4% | |
