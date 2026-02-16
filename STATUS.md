# Linear Hub — Capabilities & Status Tracker

> Living document. Updated after every significant change.
> Last updated: 2026-02-15

## System Health

| Component | Status | Last Tested | Notes |
|---|---|---|---|
| Databricks Connection | **WORKING** | 2026-02-15 | tubi-dev warehouse, core_prod catalog |
| linear-data skill | **WORKING** | 2026-02-15 | 10 canonical queries, 6 production queries |
| linear-research skill | **WORKING** | 2026-02-15 | Full 6-phase CI pipeline operational |
| Scanner Pipeline | **WORKING** | 2026-02-15 | 198 articles/41 feeds, 34 classified, 3 threats, 4 opportunities |
| Browser Automation | **WORKING** | 2026-02-15 | Playwright + API interception; Pluto=378ch, Tubi=969 names |
| Vector Memory (ChromaDB) | **WORKING** | 2026-02-15 | 51 intel, 5 profiles, 4 trends indexed; search working |
| Web Dashboard | **WORKING** | 2026-02-15 | http://localhost:8080 — all 4 API endpoints verified |
| linear-strategy skill | **WORKING** | 2026-02-15 | Skill + references + decision-log created |
| Claude Skills marketplace | **COMPATIBLE** | 2026-02-15 | Format verified against adRise/claude-skills; marketplace.json updated with owner/metadata |
| Analysis storage | **WORKING** | 2026-02-15 | First report saved to /analysis/reports/ |
| Intel pipeline | **WORKING** | 2026-02-15 | First finding saved: FAST market competitive scan |

## Data Verification Log

Track every data point we verify against dashboards or other sources.

| Date | Metric | Our Value | Dashboard Value | Match? | Notes |
|---|---|---|---|---|---|
| 2026-02-15 | Linear TVT Share (30d, US) | 4.28% | 6.5% (strategy doc) | **MISMATCH** | Strategy doc may be trailing 12mo or different window |
| 2026-02-15 | Amazon % of Linear TVT | 31.5% | 29% (strategy doc) | ~Match | Within 2.5pp, strategy doc was older data |
| 2026-02-15 | Roku % of Linear TVT | 16.0% | 18% (strategy doc) | ~Match | Within 2pp |
| 2026-02-15 | Android TV % of Linear TVT | 10.1% | 10% (strategy doc) | **Match** | |
| 2026-02-15 | Linear-only users % | 5.59% | 4% (strategy doc) | Close | Strategy doc may be post-Super Bowl average |
| 2026-02-15 | Linear+VOD users % | 16.64% | 12% (strategy doc) | **MISMATCH** | Needs investigation — possibly different user counting |
| 2026-02-15 | Top channel #1 | ION | ION (dashboard) | **EXACT MATCH** | 36,993,135 TVT hours matches exactly |
| 2026-02-15 | Unattributed sessions | 49.8% | — | — | Known gap per Entry Points doc |
| 2026-02-15 | Entertainment % of Linear TVT | 69.1% | 70% (strategy doc) | **Match** | Within 1pp |
| 2026-02-15 | News % of Linear TVT | 24.8% | 25% (strategy doc) | **Match** | Within 0.2pp |
| 2026-02-15 | Sports % of Linear TVT | 5.9% | 5% (strategy doc) | **Match** | Within 1pp |
| 2026-02-15 | Revenue tables accessible | YES | — | — | content_earnings_daily + linear_epg_earnings_hourly |
| 2026-02-15 | viewable_impression accessible | YES (1.1B rows/day) | — | — | Container impression tracking |
| 2026-02-15 | DSA presentation sample accessible | YES (218M rows/7d) | — | — | Funnel analysis ready |
| 2026-02-15 | Monthly reporting table accessible | YES (5.5K rows 2025+) | — | — | Historical trend analysis ready |
| 2026-02-15 | ION TVT Hours (365d) | 36,993,135 | 36,993,135 (dashboard) | **EXACT MATCH** | Production Query 1 verified |
| 2026-02-15 | ION Viewers (365d) | 7,059,199 | 7,059,199 (dashboard) | **EXACT MATCH** | |
| 2026-02-15 | ION AVT (365d) | 5.24 | 5.24 (dashboard) | **EXACT MATCH** | |
| 2026-02-15 | ION 5min Conv (365d) | 12.30% | 12.30% (dashboard) | **EXACT MATCH** | |
| 2026-02-15 | ION Revenue (365d) | $3,587,410 | $3,587,267 (dashboard) | ~Match | $143 diff, rounding |
| 2026-02-15 | OTT TVT Feb 2025 | 16,233,963 | 16,231,970 (dashboard) | ~Match | ~2K diff, APPROX_COUNT variance |
| 2026-02-15 | Dateline TVT (365d) | 36,720,612 | — | **Verified via query** | #2 channel by TVT |

### Verification TODO

- [ ] Compare linear TVT share against Surface Metrics Dashboard (exact same date range)
- [x] Verify top 10 channels against channel performance dashboard — **EXACT MATCH on all metrics**
- [ ] Verify user segment %s against the registered users analysis (strategy doc notes "registered viewers only")
- [ ] Check if our query includes ALL devices or only registered — strategy doc says registered only for demographics
- [ ] Run same 30-day query for Sep 2024 to see if we can reproduce the 7-8% share
- [x] Verify revenue tables accessible (`content_earnings_daily`, `linear_epg_earnings_hourly`) — **VERIFIED, revenue within $143**

## Completed Analyses

| Date | Report | Key Finding |
|---|---|---|
| 2026-02-15 | [Data Verification](analysis/reports/2026-02-15-data-verification.md) | Connection working. Linear share at 4.28% (30d). 49.8% sessions unattributed. |
| 2026-02-15 | [FAST Market Competitive Scan](intel/findings/2026-02-15-fast-market-competitive-scan.md) | Samsung 300+ ch (web), Xumo 200+ (web). Platform integration = moat. Sports = next battleground. |

## Available Canonical Queries

| Query Name | Description | Verified? |
|---|---|---|
| `linear_tvt_by_platform` | Linear TVT by platform | **YES** (2026-02-15) |
| `linear_tvt_share` | Linear as % of total TVT | **YES** (2026-02-15) |
| `linear_entry_points` | Session attribution by entry point | **YES** (2026-02-15) |
| `top_linear_channels` | Top channels by TVT | **YES** (2026-02-15) |
| `linear_user_segments` | Linear-only vs Linear+VOD vs VOD-only | **YES** (2026-02-15) |
| `linear_tvt_trend` | Daily TVT trend | Not yet |
| `linear_homepage_funnel` | Homepage presentation → watch funnel | Not yet |
| `linear_channel_genre_breakdown` | TVT by genre | Not yet |
| `linear_first_view_retention` | Retention by first view type | Not yet |
| `linear_deeplink_attribution` | Deeplink sessions by platform | Not yet |

## Production Queries (from DSA dashboards)

| Query | Description | Verified? |
|---|---|---|
| Channel Performance Dashboard | Full channel perf w/ TVT, conversion, D1, revenue, position | **YES** (2026-02-15) — exact match |
| Monthly Channel Trend | Historical monthly trends w/ positioning | Not yet |
| EPG Program-Level | Schedule-aware program performance | Not yet |
| Container Row Position | Linear container positioning on homepage | Not yet |
| Container Impression History | Per-device impression history | Not yet |
| Presentation Event Ordering | Container ordering from presentation events | Not yet |

## Known Issues

| Issue | Severity | Status | Notes |
|---|---|---|---|
| Linear TVT share discrepancy (4.28% vs 6.5%) | **HIGH** | Investigating | May be methodology difference |
| 49.8% sessions unattributed | **HIGH** | Known | Aligns with Entry Points doc gap |
| Linear+VOD segment mismatch (16.64% vs 12%) | **MEDIUM** | Investigating | May be user counting methodology |
| Python 3.9 on macOS (no pyarrow) | LOW | Acceptable | Cloud fetch disabled, queries still work |
| urllib3 SSL warning | LOW | Cosmetic | LibreSSL vs OpenSSL mismatch |

## Skill Reference Completeness

| Reference File | Content Quality | Needs Update? |
|---|---|---|
| tables.md | Comprehensive — all key tables documented | Add new tables as discovered |
| production-queries.md | 6 verified production queries | Good |
| metrics-definitions.md | Canonical metrics + baselines | Update baselines after verification |
| query-patterns.md | Reusable SQL patterns | Good |
| linear-baseline.md | Strategy doc metrics extracted | **Update after TVT share verification** |
| competitors.md | 4-tier framework, 20+ competitors, verified data | **Updated** — Xumo 411, Pluto 378, Samsung 300+ |
| market-landscape.md | Market structure documented | Needs current data |
| oem-placements.md | OEM surfaces documented | Needs platform-specific research |
| h1-fy26-plan.md | Full approved strategy | Good |
| entry-points.md | Initiative context | Good |
| open-questions.md | 6 strategic questions tracked | Good |

## Changelog

### 2026-02-15 (update 4)
- Built full 6-phase competitive intelligence pipeline (`tools/scanner/orchestrator.py`)
  - Phase 1: Parallel RSS aggregation (feedparser + ThreadPoolExecutor) — 41 feeds, 198 articles
  - Phase 2: AI classification via gpt-4o-mini — relevance + impact scoring, 34 actionable items
  - Phase 3: 4 specialist agents (threats, opportunities, trends, profiles) via gpt-4o
  - Phase 4: ChromaDB vector memory for dedup + historical context
  - Phase 5: Executive brief synthesis via gpt-4o
  - Phase 6: Full report generation (MD + JSON)
- Built Playwright browser automation (`tools/scanner/browser.py`) with API interception
  - Pluto TV: 378 channels (exact, from intercepted API)
  - Tubi: 969 content names (includes VOD), 4,040 content IDs
  - Samsung, Roku also supported
- YAML config (`tools/scanner/config.yaml`) with 17 competitors across 4 tiers
- Pipeline produces: `intel/scans/YYYY-MM-DD/<run_id>/report.md`
- First full pipeline run: 3 threats, 4 opportunities, 4 trends, 5 profiles identified

### 2026-02-15 (update 3)
- First competitive market scan completed
- Web-verified: Samsung TV Plus (300+ channels), Xumo (411 channels, 26 categories), Pluto TV (378 channels)
- Restructured competitors.md to 4-tier framework (Platform FAST → Pure-App FAST → vMVPD → SVOD)
- Added YouTube TV as premier indirect competitor (deep profile)
- Built automated scanner tools: scan.py, deep_fetch.py, parse_channels.py
- Key findings: Platform integration = competitive moat, Sports = next battleground, Amazon dependency = risk

### 2026-02-15 (update 2)
- **Dashboard verification PASSED** — Channel Performance query produces EXACT match on TVT, viewers, AVT, 5min_conversion
- Revenue within $143 (rounding). Platform performance within ~2K (APPROX_COUNT variance)
- Production Query 1 (Channel Performance Dashboard) fully verified
- Data pipeline confirmed: our queries = dashboard queries

### 2026-02-15
- Initial repo setup
- Created 3 skills: linear-data, linear-research, linear-strategy
- Established Databricks connection
- Ran 5 verification queries
- Saved first analysis report
- Created CLAUDE.md (AI context) and STATUS.md (this file)
- Identified key data discrepancies to investigate
