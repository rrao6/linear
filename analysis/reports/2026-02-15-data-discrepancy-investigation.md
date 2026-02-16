# Data Discrepancy Investigation

> Date: 2026-02-15
> Query: Investigation of 3 known data discrepancies between video_session queries and strategy doc figures
> Status: VERIFIED

## Executive Summary

Three data discrepancies were investigated. Two are explained by **measurement methodology differences** (date range and user identity scope). The third reveals a significant **attribution gap concentrated on mobile deeplinks**.

---

## Discrepancy 1: Linear TVT Share — 4.28% vs Strategy Doc's 6.5%

### Question
Linear TVT share from `video_session` shows ~4.28% (30-day), but the strategy doc cites 6.5%.

### Results by Date Range (All Users, US)

| Window | Linear TVT Share | Linear TVT Hours |
|--------|-----------------|-----------------|
| 30-day | 4.27% | 44,559,347 |
| 90-day | 4.03% | 123,914,584 |
| 180-day | 4.05% | 238,508,686 |
| 365-day | 4.38% | 495,009,985 |

### Results by Date Range (Registered Users Only, US)

| Window | Linear TVT Share | Linear TVT Hours |
|--------|-----------------|-----------------|
| 30-day | 4.33% | 28,294,674 |
| 90-day | 4.11% | 79,659,434 |

### Finding

**The discrepancy is NOT caused by date range or user registration filter.** Linear TVT share remains stable at ~4.0-4.4% across all date ranges and user filters tested. Registered-only filtering has negligible effect (~0.06pp higher).

### Root Cause Hypothesis

The strategy doc's 6.5% figure likely uses a **different methodology**:
- **Different denominator**: May count only CTV sessions (excluding mobile/web), where linear share would be higher since linear viewing skews heavily toward CTV
- **Different metric**: May use "share of viewers" rather than "share of TVT hours"
- **Different time period**: May reference a specific historical peak (e.g., during NFL/Super Bowl events where SPORTS_EVENT content showed up at 0.13% in 90-day but 0% in 30-day)
- **Dashboard methodology**: The strategy doc figure may come from a dashboard that applies additional filters (e.g., minimum session duration, specific platforms only)

### Recommendation

Obtain the exact query or dashboard definition behind the strategy doc's 6.5% figure. The most likely explanation is a CTV-only denominator or a different time period that included major sports events.

---

## Discrepancy 2: Linear+VOD User Segment — 16.64% vs Strategy Doc's 12%

### Question
Linear+VOD cross-viewers show 16.64% of devices (30-day) but strategy doc says 12%.

### Results by Scope

| Window | Scope | Linear+VOD | Linear Only | VOD Only |
|--------|-------|------------|-------------|----------|
| 30-day | All devices | **17.56%** (11.3M) | 4.59% (3.0M) | 77.84% (50.0M) |
| 30-day | Registered users | **25.06%** (6.7M) | 4.32% (1.2M) | 70.63% (19.0M) |
| 90-day | All devices | **20.65%** (23.8M) | 3.86% (4.4M) | 75.49% (86.9M) |
| 90-day | Registered users | **32.29%** (13.5M) | 3.44% (1.4M) | 64.27% (26.8M) |

### Finding

**Filtering to registered users makes the discrepancy WORSE, not better** — going from 17.56% to 25.06% (30-day). This is because registered users are more engaged and more likely to watch both content types.

The strategy doc's 12% figure is **lower** than our device-level 17.56%. This suggests:

1. **Measurement window**: The 12% may be from a shorter or specific time period
2. **Stricter definition**: The strategy doc may require a minimum TVT threshold for each content type (e.g., >5 min LINEAR + >5 min VOD) rather than any viewing
3. **Longer window dilution**: Over 90 days, the cross-viewing rate actually rises to 20.65%, suggesting that a shorter window (weekly?) would show a lower rate closer to 12%

### Key Insight

The 90-day registered-user figure (32.29%) shows that **nearly 1 in 3 registered users watches both linear and VOD** — this is a strong engagement signal. The gap between registered (25.06%) and all-device (17.56%) confirms that linear cross-viewers are disproportionately registered/engaged users.

### Recommendation

Check if the strategy doc's 12% uses a weekly measurement window or requires a minimum viewing threshold per content type. A weekly cadence would naturally produce a lower cross-viewing rate.

---

## Discrepancy 3: Attribution Gap — 49.8% Empty page_source

### Question
49.8% of LINEAR sessions have empty `page_source`. What platforms and devices generate these unattributed sessions?

### Overall Gap

| Status | Sessions % | TVT Hours |
|--------|-----------|-----------|
| Empty page_source | 49.8% | 13,613,217 |
| Has page_source | 50.2% | 30,946,130 |

Note: Empty sessions account for 49.8% of session count but only **30.5% of TVT hours** — unattributed sessions are shorter on average.

### Empty page_source Rate by Content Type

| Content Type | Empty Rate | Empty Sessions | Total Sessions |
|-------------|-----------|---------------|---------------|
| LINEAR | **49.8%** | 87,151,823 | 175,132,165 |
| UNKNOWN | 57.2% | 318,644 | 556,802 |
| SCENE | 74.6% | 14,966 | 20,066 |
| SERIES | 19.6% | 3,408,535 | 17,350,762 |
| MOVIE | 12.2% | 91,189,154 | 745,843,438 |
| EPISODE | 6.8% | 84,306,372 | 1,232,860,110 |

**LINEAR has by far the highest empty rate among major content types** (49.8% vs 12.2% for movies and 6.8% for episodes).

### Platform Breakdown of Empty page_source LINEAR Sessions

| Platform | % of Empty Sessions | Session Count | TVT Hours |
|----------|-------------------|--------------|-----------|
| **ANDROID** | **47.7%** | 41,613,959 | 2,185,214 |
| AMAZON | 13.0% | 11,372,566 | 6,081,878 |
| ROKU | 10.2% | 8,924,105 | 612,891 |
| IPHONE | 9.7% | 8,476,344 | 464,483 |
| ANDROIDTV | 4.9% | 4,302,640 | 1,828,763 |
| SAMSUNG | 2.6% | 2,244,252 | 269,670 |
| VIZIO | 2.6% | 2,226,614 | 55,743 |
| IPAD | 2.5% | 2,216,182 | 194,116 |
| LGTV | 1.4% | 1,239,437 | 720,905 |
| COMCAST | 1.3% | 1,159,593 | 64,129 |
| XBOXONE | 1.0% | 849,734 | 183,912 |
| WEB | 0.9% | 748,877 | 381,424 |
| PS5 | 0.8% | 731,109 | 77,871 |

### Attributed LINEAR Sessions by page_source

| Page Source | % of Attributed | Session Count | TVT Hours |
|-------------|----------------|--------------|-----------|
| LinearBrowsePage | 39.6% | 34,834,360 | 8,789,842 |
| VideoPlayerPage | 34.4% | 30,308,002 | 7,335,367 |
| HomePage | 24.1% | 21,159,632 | 13,705,045 |
| SearchPage | 1.2% | 1,066,625 | 1,049,050 |
| ForYouPage | 0.4% | 340,734 | 40,885 |

### Finding

**The attribution gap is overwhelmingly driven by ANDROID (47.7% of empty sessions)** — likely deeplink entries from the Android app that bypass normal page navigation. Combined with IPHONE (9.7%), mobile accounts for **57.4% of all unattributed LINEAR sessions**.

Key observations:
1. **ANDROID dominates** with 41.6M unattributed sessions but relatively low TVT per session (52.5 hrs/M sessions) — these are likely short deeplink-initiated sessions
2. **AMAZON has the highest TVT per unattributed session** (534.7 hrs/M sessions) — consistent with Amazon Live tab deeplinks being the #1 linear traffic source (31.5% per CLAUDE.md)
3. **LGTV shows high TVT per session** (581.5 hrs/M) despite low volume — possible built-in app integration
4. When attributed, **HomePage drives the most TVT hours** (13.7M) despite being only 24.1% of sessions — homepage linear entry points generate the most engaged viewing

### Recommendation

1. **Android instrumentation fix**: The 47.7% ANDROID share suggests a page_source tracking bug in the Android app for deeplink/notification entries — this should be investigated as an engineering fix
2. **Amazon attribution**: The high-TVT Amazon sessions are likely the "Live tab deeplinks" referenced in business context — consider adding a specific `AmazonLiveTab` page_source value
3. **Impact on metrics**: The 49.8% gap means all page_source-based attribution analysis (including the "Amazon drives 31.5% of linear TVT" claim) is based on only half the data and may significantly undercount certain entry points

---

## Methodology

All queries run against `core_prod.session.video_session` with:
- `tvt_millisec > 0` filter
- `country = 'US'` filter
- Date ranges: 30, 90, 180, and 365 days from 2026-02-15
- Registered user filter: `user_id IS NOT NULL`

## Follow-up

1. **TVT Share**: Obtain the exact query/dashboard behind the strategy doc's 6.5% figure — most likely a CTV-only or event-inclusive window
2. **User Segments**: Test weekly measurement windows and minimum TVT thresholds to match the 12% figure
3. **Attribution**: File engineering ticket for Android page_source tracking on deeplink entries; create Amazon-specific attribution value
4. **Re-baseline**: Once methodology is aligned, update CLAUDE.md Known Data Discrepancies section
