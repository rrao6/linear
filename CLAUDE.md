# CLAUDE.md — AI Context for Linear Hub

> This file provides context for Claude Code when working in this repository.
> It is the source of truth for what exists, what works, and how to use it.

## What This Repo Is

This is the **Linear Hub** — the single source of truth for Tubi's Linear/FAST TV strategy, competitive intelligence, data analysis, and metadata standards. It is designed to be used through Claude Code skills as the primary work interface.

## Repo Structure

```
linear/
├── CLAUDE.md              ← You are here (AI context)
├── STATUS.md              ← Living capabilities tracker (what works, what doesn't)
├── README.md              ← Human quick start
├── .env                   ← Databricks + API credentials (never commit)
│
├── plugins/               ← Claude Code skills
│   ├── linear-data/       ← /linear-data: Query Databricks for linear metrics
│   ├── linear-research/   ← /linear-research: Competitive intel, market scanning
│   └── linear-strategy/   ← /linear-strategy: PRDs, strategy, decisions
│
├── analysis/              ← Data analysis outputs
│   ├── reports/           ← Completed analyses (markdown, human+AI readable)
│   └── notebooks/         ← Work-in-progress explorations
│
├── intel/                 ← Competitive intelligence pipeline
│   ├── signals/           ← Raw data points (date + source required)
│   ├── findings/          ← Validated patterns (must cite signals)
│   ├── insights/          ← Strategic interpretations (must cite findings)
│   └── opportunities/     ← Actionable items (must define success metric)
│
├── docs/                  ← Knowledge base (structured documentation)
│   ├── 00_start_here/
│   ├── 01_market/
│   ├── 02_competitors/
│   ├── 03_strategy/
│   ├── 04_data/
│   └── 05_metadata_assets/
│
├── tools/                 ← Automation tools
│   └── scanner/           ← Competitive intelligence pipeline
│       ├── orchestrator.py   ← Main 6-phase pipeline (collect→classify→analyze→memory→synthesize→report)
│       ├── aggregator.py     ← Parallel RSS fetcher using feedparser + ThreadPoolExecutor
│       ├── classifier.py     ← AI classification (relevance/impact scoring via gpt-4o-mini)
│       ├── analysts.py       ← 4 specialist agents (threats, opportunities, trends, profiles)
│       ├── memory.py         ← ChromaDB vector store for semantic search + dedup
│       ├── browser.py        ← Playwright headless browser with API interception for SPAs
│       ├── parse_channels.py ← Direct regex channel count extraction from competitor HTML
│       ├── deep_fetch.py     ← AI-assisted deep extraction (uses OpenAI gpt-4o)
│       ├── scan.py           ← Legacy RSS + site scanner
│       ├── config.yaml       ← All competitors, feeds, queries, settings (YAML)
│       ├── models.py         ← Data models (ArticleCandidate, ClassifiedIntel, etc.)
│       └── sources.py        ← Legacy source definitions
│
├── tools/dashboard/       ← Web dashboard
│   ├── server.py          ← Local HTTP server (python3 tools/dashboard/server.py)
│   └── index.html         ← Interactive dashboard UI
│
├── data/chroma/           ← ChromaDB vector store (gitignored, auto-created)
│
├── docs/                  ← Knowledge base
│   └── 03_strategy/
│       └── decision-log.md ← Decision log with context and rationale
│
└── ops/                   ← Operations
    ├── templates/         ← Signal, finding, insight, opportunity templates
    └── agent/             ← Agent playbook and prompts
```

## How to Query Data

The `/linear-data` skill connects to Databricks. The CLI is at `plugins/linear-data/linear_data/cli.py`.

**Direct Python usage** (preferred for complex queries):
```bash
PYTHONPATH=/Users/rrao/linear/plugins/linear-data python3 -c "
from linear_data.connection import get_cursor
with get_cursor() as cur:
    cur.execute('YOUR SQL HERE')
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    # process results
"
```

**Key tables** (see `plugins/linear-data/skills/linear-data/references/tables.md` for full schema):
- `core_prod.session.video_session` — primary viewing data (partition on `date`)
- `core_prod.content.content_info` — content metadata (use for LINEAR content_type)
- `core_prod.tubidw.linear_epg_video_sessions` — program-level linear viewing
- `core_prod.tubidw.epg_schedules` — schedule grid (live_broadcast flag)
- `core_dev.dsa.dsac_viewpres_vidsession_sample` — presentation/click/watch funnel
- `core_prod.analytics.viewable_impression` — container impression tracking
- `core_dev.dsa.dsac_single_title_reporting_bymonth` — pre-aggregated monthly
- `core_prod.events.presentation_event` — full presentation events with container ordering

**Critical query rules**:
- ALWAYS filter on partition key (`date` or `ds`)
- ALWAYS add `tvt_millisec > 0`
- TVT is in milliseconds: `/3600000.0` for hours
- `content_info.duration` is in minutes (not ms)
- For LINEAR, `content_id` = channel, not program. Use `linear_epg_video_sessions` for program-level.
- Only ~30-40% of viewers are registered (`user_id IS NOT NULL`)

## How to Store Analysis

All analysis outputs go in `/analysis/reports/` as markdown with this format:

```markdown
# [Title]

> Date: YYYY-MM-DD
> Query: [brief description of what was analyzed]
> Status: [DRAFT | VERIFIED | SUPERSEDED]

## Key Findings
[Bullet points of main takeaways]

## Data
[Tables, charts, or formatted results]

## Methodology
[SQL queries used, filters, date ranges]

## Comparison to Baseline
[How does this compare to known values from strategy docs or dashboards?]

## Follow-up
[What questions does this raise?]
```

## How to Store Intel

Follow the pipeline: **Signal → Finding → Insight → Opportunity**

- Signals: raw data points in `/intel/signals/YYYY-MM-DD-slug.md`
- Findings: validated patterns in `/intel/findings/YYYY-MM-DD-slug.md`
- Insights: strategic interpretations in `/intel/insights/YYYY-MM-DD-slug.md`
- Opportunities: actionable items in `/intel/opportunities/YYYY-MM-DD-slug.md`

Templates are in `/ops/templates/`. Every level must cite the level below it.

## Current State (as of 2026-02-15)

### What Works
- Databricks connection (tested, queries running)
- 10 canonical queries in CLI
- 6 production-verified complex queries (Channel Performance = EXACT MATCH to dashboard)
- Full table schema documentation
- 3 Claude skills defined and all references verified (data, research, strategy)
- Strategy doc content extracted into references
- Competitive landscape with 4-tier competitor tracking (FAST, pure-app, vMVPD, SVOD)
- **Full 6-phase CI pipeline** — collect (41 feeds) → classify (gpt-4o-mini) → analyze (4 agents) → memory (ChromaDB) → synthesize → report
- **Browser automation** — Playwright + API interception for JS-rendered pages
- **Web dashboard** — interactive UI at `http://localhost:8080`
- **Vector memory** — ChromaDB with OpenAI embeddings for semantic search across scans
- Scan data in `intel/scans/YYYY-MM-DD/`

### How to Run Competitive Scans

```bash
# FULL PIPELINE — 6-phase automated scan (recommended)
python3 tools/scanner/orchestrator.py                          # Full pipeline
python3 tools/scanner/orchestrator.py --skip-memory            # Without vector DB
python3 tools/scanner/orchestrator.py --skip-analysis          # Collect+classify only (fast)
python3 tools/scanner/orchestrator.py --competitor pluto_tv    # One competitor
python3 tools/scanner/orchestrator.py --lookback 168           # 7 days back

# BROWSER AUTOMATION — headless Chrome with API interception
python3 tools/scanner/browser.py                               # All sites
python3 tools/scanner/browser.py --site pluto --screenshot     # One site + screenshot
python3 tools/scanner/browser.py --site tubi --output out.json

# INDIVIDUAL COMPONENTS
python3 tools/scanner/aggregator.py                            # RSS feeds only
python3 tools/scanner/parse_channels.py                        # Static channel counts
python3 tools/scanner/deep_fetch.py "URL" --prompt "..."       # AI deep extraction
python3 tools/scanner/memory.py --search "Roku sports"         # Vector search
python3 tools/scanner/memory.py --stats                        # Memory stats

# DASHBOARD — interactive web UI
python3 tools/dashboard/server.py                              # Start at http://localhost:8080
python3 tools/dashboard/server.py --port 3000                  # Custom port

# LEGACY
python3 tools/scanner/scan.py --mode full                      # Old scanner
```

**Pipeline output**: `intel/scans/YYYY-MM-DD/<run_id>/` containing:
- `articles.json` — raw collected articles
- `classified.json` — AI-scored intel (relevance + impact)
- `analysis.json` — threats, opportunities, trends, profiles
- `channels.json` — competitor channel counts
- `report.md` — executive brief + full analysis

### Verified Competitive Data (2026-02-15)
- **Xumo**: 411 channels (scraped from page JSON, exact)
- **Pluto TV**: 378 channels (Playwright API interception, exact)
- **Samsung TV Plus**: 300+ (marketing claim)
- **Vizio WatchFree+**: 300+ (marketing claim)
- **Plex**: 600+ (Cord Cutters News)
- **Sling Freestream**: 600+ (Cord Cutters News)
- **TCL+**: 350+ (Cord Cutters News)
- **Tubi**: ~340 (user-confirmed; browser scrape found 969 names incl. VOD titles)

### Known Data Discrepancies
- Linear TVT share shows 4.28% (30-day) vs strategy doc's 6.5% — needs methodology verification
- 49.8% of linear sessions have empty `page_source` — likely unattributed deeplinks
- User segments show Linear+VOD at 16.64% vs strategy doc's 12% — may be measurement window

### What Needs Work
- Entry point attribution gap investigation
- Monthly/weekly trend analysis
- Nielsen Gauge data access
- Ad fill rate and CPM data
- Tubi browser scrape needs filtering to separate linear channels from VOD titles
- Scheduled/cron pipeline runs for continuous monitoring

## Key Business Context

- **Tubi has ~340 linear channels** (user-confirmed, not 275 from strategy doc)
- **Linear TVT share**: Currently ~4.28% (last 30 days), target 9.0% by end FY26
- **Critical event**: On Now row unpinned Sep 2024, caused ~70% traffic loss to linear
- **Fox partnership**: Super Bowl, NFL (Thanksgiving), World Cup 2026
- **Top channels**: ION (37M TVT hrs/yr), Dateline 24/7 (37M), ION Mystery (23M)
- **Amazon drives 31.5% of linear TVT** via Live tab deeplinks — biggest platform dependency
- **Linear+VOD users watch 2.4x more** than VOD-only users (35.2 vs 14.5 hrs)
- **YouTube TV is premier indirect competitor** — 8M+ subs, $73/mo, best-in-class linear UX
- **40% of CTV ad dollars ($7.4B) wasted** on bad identity matching (Truthset/Digiday Feb 2026)
- **Roku Channel won "Best Free Streaming 2025"** — beating Tubi and Pluto in consumer preference
