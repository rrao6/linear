# Linear Hub Roadmap

> What needs to happen to make this a usable daily-driver SSOT.
> Last updated: 2026-02-15

## Current State

**What exists:**
- FastAPI hub at localhost:8888 with 8 API routers (dashboard, intel, data, sentiment, features, oem, strategy, search)
- SPA frontend with Chart.js visualizations
- 4 collectors: Reddit, App Store, Sprout Social (skeleton), Manual
- 6-phase competitive intel pipeline (RSS → classify → analyze → memory → synthesize → report)
- Databricks connection with 10 canonical queries (6 verified)
- 68 API endpoint tests
- SQLite with: 18 work items, 12 learnings, 6 verifications, 18 sentiment items, 4 experiments

**What's broken or missing:**
- Dashboard shows hardcoded KPIs — no live Databricks pull
- No scheduled/cron data refresh — everything is manual
- Frontend has no auto-refresh, no websocket, stale on load
- 4 unverified canonical queries, 5 unverified production queries
- TVT share discrepancy (4.28% vs 6.5%) unresolved
- 49.8% attribution gap uninvestigated
- No revenue data flowing into hub
- OEM page is static JSON — no live placement tracking
- No PRD auto-generation actually works (template only)
- Search is basic — ChromaDB not wired to hub content
- No alerting or notifications

## Phase 1: Make It Real (Current Sprint)

The hub needs to show **live data**, not stubs. A PM should open it and see current numbers.

### P1-1: Live Databricks Dashboard -- DONE
~~Wire the dashboard overview to pull real KPIs from Databricks on each load:~~
- [x] Current linear TVT share (last 30d)
- [x] TVT trend (daily for last 90d)
- [x] Top 10 channels with TVT hours
- [x] Platform breakdown (Amazon, Roku, Samsung, etc.)
- [x] Cache results for 1 hour in SQLite (`kpi_cache` table) to avoid hammering Databricks
- [x] Fallback to hardcoded values when Databricks is unavailable

### P1-2: Data Verification Deep Dive
Resolve the known discrepancies:
- Linear TVT share: 4.28% vs 6.5% — run query with exact same parameters as Surface Metrics Dashboard
- Linear+VOD segment: 16.64% vs 12% — check if strategy doc counted registered-only
- Attribution gap: investigate what the 49.8% empty page_source sessions actually are
- Verify remaining 4 canonical queries + 5 production queries

### P1-3: Sentiment Pipeline End-to-End
Make collectors actually run and produce visible results:
- Fix Sprout Social collector (probe API, get real data flowing)
- Run Reddit + App Store collectors, push to hub
- Add collection trigger endpoints: POST /api/sentiment/collect/{source}
- Frontend sentiment page should show real data with time filters

### P1-4: Frontend Polish
The SPA needs to be usable, not just a demo:
- Auto-refresh dashboard data every 5 minutes
- Add date range pickers to all data views
- Make work queue functional (create/edit/close items from UI)
- Add loading states, error handling, empty states
- Fix any broken navigation or dead pages

### P1-5: CI Pipeline Integration
Connect the competitive intel scanner output to the hub:
- After a scan completes, auto-ingest threats/opportunities/trends into hub DB
- Show scan history with diff (what changed since last scan)
- Add "Run Scan" button to intel page

## Phase 2: Daily Utility

### P2-1: Scheduled Refreshes
- Cron/background task to refresh Databricks KPIs every 6 hours
- Auto-run sentiment collectors daily
- Weekly competitive scan

### P2-2: PRD Generator
- Wire /api/strategy/generate-prd to actually pull from all hub data
- Include: current metrics, sentiment themes, competitive threats, experiment results
- Output structured markdown PRD

### P2-3: Revenue & Ad Data
- Pull revenue data from content_earnings_daily
- Show CPM trends, ad fill rates where available
- Revenue per channel, revenue per platform

### P2-4: Alerting
- Detect significant changes (TVT drop >10%, new competitive threat, sentiment spike)
- Push alerts to work queue as high-priority items

## Phase 3: Scale

### P3-1: Multi-user access (auth, sharing)
### P3-2: Historical trend storage (time-series in SQLite)
### P3-3: Embedded analytics (Databricks notebooks inline)
### P3-4: Integration with Linear (the project tool) for task sync

---

## Out of Scope

- Building a production deployment (this is a local PM tool)
- Mobile app
- Real-time streaming data
- Anything that requires new Databricks tables
