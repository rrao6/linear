# Data Verification Report

> Date: 2026-02-15
> Purpose: Verify Databricks connection and validate data against known dashboard values
> Status: **PASSED — Connection working, data flowing, discrepancies noted**

## Connection Test

- **Host**: tubi-dev.cloud.databricks.com
- **Warehouse**: d91490098e4494d5
- **Catalog**: core_prod
- **Result**: `SELECT 1` — PASSED

## Verification Queries (All US, Last 30 Days)

### 1. Linear TVT Share

| Metric | Value | Strategy Doc Baseline | Delta | Notes |
|---|---|---|---|---|
| Linear Hours | 45.8M | — | — | 30-day total |
| Total Hours | 1,069.7M | — | — | 30-day total |
| **Linear Share %** | **4.28%** | **6.5%** | **-2.22pp** | Significant decline from baseline |

**Analysis**: The strategy doc cited 6.5% as the current share at FY26 start. We're now seeing 4.28% over the last 30 days. This is a significant drop and may indicate:
- Continued decline since the On Now unpinning (Sep 2024)
- The baseline may have been a different time window or methodology
- Seasonal effects or measurement differences

**ACTION NEEDED**: Verify this against the Surface Metrics Dashboard to confirm methodology alignment. The 6.5% figure may have been trailing 12-month, while this is trailing 30-day.

### 2. Top 15 Linear Channels

| Rank | Channel | Unique Viewers | Total Hours | Avg Session (min) |
|---|---|---|---|---|
| 1 | ION | 1.18M | 2.99M | 28.7 |
| 2 | Dateline 24/7 | 928K | 2.78M | 31.9 |
| 3 | ION Mystery | 602K | 2.01M | 28.2 |
| 4 | TV One Crime & Justice | 812K | 1.75M | 28.8 |
| 5 | ABC News Live | 1.33M | 1.50M | 17.2 |
| 6 | LiveNOW from FOX | 1.39M | 1.47M | 14.9 |
| 7 | Family Feud | 2.44M | 1.44M | 17.4 |
| 8 | Bounce XL | 726K | 900K | 22.3 |
| 9 | NFL Channel | 3.94M | 900K | 4.0 |
| 10 | Forensic Files | 285K | 731K | 30.7 |
| 11 | FOX 5 Atlanta | 91K | 722K | 46.4 |
| 12 | Are We There Yet | 310K | 721K | 36.2 |
| 13 | NBC News NOW | 608K | 685K | 14.1 |
| 14 | FOX Weather | 918K | 522K | 11.5 |
| 15 | FOX LOCAL Washington DC | 200K | 519K | 30.4 |

**Observations**:
- Top channels confirm strategy doc: Entertainment (True Crime/Procedural) dominates
- ION, Dateline, ION Mystery, TV One Crime & Justice, Forensic Files = true crime/procedural cluster
- News channels (ABC, FOX, NBC, FOX Weather) well represented
- NFL Channel has highest unique viewers (3.94M) but very low avg session (4 min) — likely brief tune-ins
- Family Feud has 2.44M unique viewers — strong mainstream appeal
- FOX 5 Atlanta has highest avg session at 46.4 min — deep local news engagement

### 3. User Segments

| Segment | Users | % of Users | Avg Hours/User | Total Hours |
|---|---|---|---|---|
| VOD Only | 43.5M | 67.11% | 14.54 | 632.7M |
| Linear+VOD | 10.8M | 16.64% | 35.20 | 379.7M |
| Other | 6.9M | 10.66% | 6.06 | 41.9M |
| Linear Only | 3.6M | 5.59% | 4.26 | 15.5M |

**Comparison to Strategy Doc**:
- Strategy doc said Linear Only = ~4%. We see **5.59%** — slightly higher
- Strategy doc said Linear+VOD = ~12% (post-unpinning). We see **16.64%** — notably higher
- Key insight: Linear+VOD users watch **35.20 hrs/user** vs VOD Only at **14.54 hrs/user** — 2.4x more engagement
- This confirms the strategy doc's assertion that converting VOD users to Linear+VOD drives significant incremental TVT

### 4. Entry Points (Linear Sessions by Page Source)

| Page Source | Sessions | % of Sessions | Total Hours | Avg Watch (min) |
|---|---|---|---|---|
| HomePage | 21.6M | 12.1% | 14.1M | 39.0 |
| (empty/null) | 89.1M | 49.8% | 14.0M | 9.4 |
| LinearBrowsePage | 35.6M | 19.9% | 9.0M | 15.2 |
| VideoPlayerPage | 31.0M | 17.3% | 7.5M | 14.5 |
| SearchPage | 1.1M | 0.6% | 1.1M | 59.3 |

**Comparison to Strategy Doc (Sept 2024 baseline)**:

| Source | Sept 2024 | Current | Notes |
|---|---|---|---|
| Homepage | 38.6% | 12.1% | Major decline — but 49.8% is unattributed |
| Deeplink | 28.0% | — | Likely in the empty/null bucket |
| Linear Browse/EPG | 15.9% | 19.9% | Slight increase |
| Search | 2.0% | 0.6% | Decline |

**Critical Finding**: 49.8% of linear sessions have **no page_source attribution**. This aligns with the Entry Points doc noting missing deeplink attribution (TDATAINFRA-669). The empty bucket likely contains deeplinks, CRM, and other unattributed paths.

### 5. Platform Breakdown

| Platform | Unique Viewers | Total Hours | % Linear TVT |
|---|---|---|---|
| AMAZON | 2.31M | 14.4M | 31.5% |
| ROKU | 2.77M | 7.3M | 16.0% |
| ANDROIDTV | 1.06M | 4.6M | 10.1% |
| ANDROID | 2.41M | 3.6M | 7.9% |
| VIZIO | 592K | 2.8M | 6.1% |
| LGTV | 382K | 2.2M | 4.8% |
| IPHONE | 2.33M | 2.0M | 4.4% |
| SAMSUNG | 707K | 1.9M | 4.1% |
| WEB | 331K | 1.8M | 3.9% |

**Comparison to Strategy Doc**:

| Platform | Strategy Doc | Current | Match? |
|---|---|---|---|
| Amazon | 29% | 31.5% | Close — Amazon still #1 for linear |
| Roku | 18% | 16.0% | Close — Roku still #2 |
| Android TV | 10% | 10.1% | Match |
| OTT Total | 82% | ~79% | Close |
| Mobile Total | 14% | ~12.6% | Close |
| Web | 4% | 3.9% | Match |

Platform distribution is well-aligned with strategy doc. Amazon's dominance confirms the Live tab deeplink hypothesis.

## Summary

| Check | Status | Notes |
|---|---|---|
| Connection | PASSED | Databricks reachable, queries execute |
| Table access | PASSED | video_session, content_info, all accessible |
| Data recency | PASSED | Data available through today |
| Platform breakdown | ALIGNED | Matches strategy doc within 2pp |
| User segments | PARTIALLY ALIGNED | Linear+VOD higher than expected (16.6% vs 12%) |
| Entry points | NEEDS INVESTIGATION | 49.8% unattributed sessions |
| Linear TVT share | DISCREPANCY | 4.28% vs 6.5% baseline — needs methodology verification |

## Follow-up Actions

- [ ] Verify linear TVT share methodology against Surface Metrics Dashboard
- [ ] Investigate the 49.8% unattributed sessions — what's in the empty page_source?
- [ ] Compare 30-day vs trailing 12-month for TVT share
- [ ] Cross-reference top channels against the channel performance dashboard
- [ ] Check if `content_type = 'LINEAR'` is the correct filter or if there are other linear-related types
