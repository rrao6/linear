# Linear Hub Platform — Build Plan

## Vision

Transform the current collection of scripts and flat files into an integrated platform that serves as the **operational center** for Tubi's Linear TV strategy. The hub combines real-time competitive monitoring, Databricks analytics, user sentiment tracking, and automated insight-to-PRD workflows — all accessible through a single web interface.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LINEAR HUB UI                         │
│  (React SPA served by FastAPI)                          │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │Dashboard │ │Intel     │ │Data      │ │Strategy    │ │
│  │Overview  │ │Monitor   │ │Explorer  │ │Workspace   │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │Sentiment │ │Feature   │ │OEM       │ │PRD         │ │
│  │Tracker   │ │Adoption  │ │Tracker   │ │Generator   │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                  FastAPI Backend                          │
│                                                          │
│  /api/dashboard   — KPI overview, goal tracking          │
│  /api/intel       — CI pipeline results, threats, opps   │
│  /api/data        — Databricks query proxy               │
│  /api/sentiment   — Feedback aggregation & trends        │
│  /api/features    — Feature adoption metrics             │
│  /api/oem         — OEM placement tracking               │
│  /api/strategy    — PRD generation, decision log         │
│  /api/search      — Unified semantic search (ChromaDB)   │
│  /api/ws          — WebSocket for live updates           │
└──────────┬───────────┬───────────┬──────────────────────┘
           │           │           │
    ┌──────▼──┐  ┌─────▼────┐  ┌──▼──────────┐
    │Databricks│  │ChromaDB  │  │SQLite       │
    │(queries) │  │(vectors) │  │(local state)│
    └─────────┘  └──────────┘  └─────────────┘
```

---

## What We're Building (8 Modules)

### Module 1: FastAPI Backend (replaces SimpleHTTPRequestHandler)
**Why**: Current server.py is a toy. FastAPI gives us async, WebSockets, auto-docs, and proper routing.

**Files**:
- `hub/server.py` — FastAPI app, CORS, static file serving
- `hub/routers/dashboard.py` — KPI endpoints
- `hub/routers/intel.py` — CI pipeline endpoints (wraps existing scanner)
- `hub/routers/data.py` — Databricks query proxy
- `hub/routers/sentiment.py` — Sentiment aggregation
- `hub/routers/features.py` — Feature adoption tracking
- `hub/routers/oem.py` — OEM placement data
- `hub/routers/strategy.py` — PRD generation, decisions
- `hub/routers/search.py` — Unified ChromaDB search
- `hub/db.py` — SQLite for local state (feedback, feature tracking, OEM snapshots)
- `hub/models.py` — Pydantic models for all entities

### Module 2: Dashboard Overview (Home)
**What it shows**:
- Linear TVT share (current vs target 9.0%) with sparkline trend
- Top 5 channels by TVT (live from Databricks)
- Goal progress bars (H2 FY26: +0.22% TVT, +5.32% Linear TVT)
- Latest threats/opportunities from CI pipeline
- Recent scan freshness indicator
- Platform attribution breakdown (Amazon 31.5%, Roku, etc.)

**Data sources**: Databricks (cached 15min), latest scan JSON, SQLite

### Module 3: Intel Monitor (Competitive Intelligence)
**What it shows**:
- Live feed of classified intel (threats, opportunities, trends)
- Competitor profiles with channel counts (auto-updated by scanner)
- Threat severity timeline
- One-click "Run Scan" button (triggers orchestrator.py)
- Scan history with diff view (what changed since last scan)
- Signal → Finding → Insight → Opportunity pipeline visualization

**Data sources**: Existing scanner pipeline output, ChromaDB

### Module 4: Data Explorer (Databricks Query Interface)
**What it shows**:
- Pre-built query library (10 canonical + 6 production-verified)
- Custom SQL editor with autocomplete for table/column names
- Results rendered as tables + auto-generated charts
- Query history (saved to SQLite)
- "Save as Report" button → generates markdown in analysis/reports/
- Key tables reference sidebar

**Data sources**: Databricks via existing connection.py

### Module 5: Sentiment Tracker (NEW — User Feedback Integration)
**What it shows**:
- Aggregated sentiment from configured sources (Reddit, Twitter/X, app reviews, support tickets)
- Sentiment trend over time (positive/negative/neutral)
- Topic clustering (EPG complaints, channel requests, ad experience, etc.)
- Verbatim quotes tagged by theme
- Alert rules: notify when negative sentiment spikes on a topic

**Implementation**:
- `hub/collectors/reddit.py` — Reddit API (PRAW) for r/Tubi, r/cordcutters, r/FAST
- `hub/collectors/appstore.py` — App Store/Google Play review scraper
- `hub/collectors/twitter.py` — Twitter/X API search for Tubi Linear mentions
- `hub/collectors/manual.py` — Manual feedback entry form (for Slack/email/meetings)
- All feedback stored in ChromaDB with sentiment scores (OpenAI classification)

### Module 6: Feature Adoption Tracker (NEW)
**What it shows**:
- Active experiments and their status (from Statsig or manual entry)
- Feature rollout metrics (TVT impact, conversion lift, engagement delta)
- Before/after comparison dashboards for each experiment
- EPG Phase 1/2/3 progress tracking tied to the roadmap
- Feature flag status across platforms

**Implementation**:
- `hub/routers/features.py` — CRUD for experiments + metrics
- SQLite table: `experiments (id, name, phase, status, hypothesis, start_date, metrics_json)`
- Databricks queries parameterized by experiment date ranges
- Manual metric entry for non-automated sources

### Module 7: OEM Placement Tracker (NEW)
**What it shows**:
- Where Tubi Linear appears on each OEM platform (position, prominence)
- Competitor placement comparison (who has Live tab default, etc.)
- Historical placement changes (tracked over time)
- Impact correlation: placement changes → TVT impact
- Amazon dependency tracker (31.5% of linear TVT)

**Implementation**:
- `hub/routers/oem.py` — OEM snapshot CRUD
- SQLite table: `oem_snapshots (id, platform, date, placement_json, notes)`
- Browser automation snapshots (extend existing browser.py)
- Manual entry for placements that can't be scraped

### Module 8: Strategy Workspace (PRD Generator)
**What it shows**:
- PRD template with auto-populated context (metrics, competitive data, user feedback)
- Decision log viewer/editor
- Open questions tracker
- Strategy doc reference (H1 FY26 plan, product strategy)
- "Generate PRD" button: pulls relevant data from all modules into PRD template

**Implementation**:
- `hub/routers/strategy.py` — PRD CRUD, decision log, questions
- Template engine pulling from Databricks + ChromaDB + SQLite
- Markdown rendering with export

---

## Frontend Approach

**Single HTML file with modern vanilla JS** (consistent with existing dashboard pattern, no build step needed).

Why not React/Next.js:
- This is a local tool, not a production web app
- No build step = instant iteration
- Current dashboard already works this way
- FastAPI serves static files directly

**UI Framework**: Vanilla JS + CSS custom properties (dark theme, consistent with existing)
**Charts**: Chart.js (lightweight, no build needed, CDN)
**Icons**: Lucide (CDN)
**Layout**: CSS Grid dashboard with collapsible sidebar navigation

---

## Implementation Sequence

### Phase 1: Foundation (Backend + Dashboard + Data Explorer)
1. Create `hub/` directory with FastAPI app structure
2. Migrate existing dashboard server.py → FastAPI
3. Wire up Databricks query proxy (wrap existing connection.py)
4. Build dashboard overview page with live KPI cards
5. Build data explorer with query library + custom SQL
6. Add SQLite for local state

### Phase 2: Intel + Search
7. Migrate intel endpoints from old server.py
8. Add unified ChromaDB search endpoint
9. Build intel monitor page with threat/opportunity feed
10. Add "Run Scan" trigger from UI
11. Build scan diff view

### Phase 3: Sentiment + Feedback
12. Build Reddit collector (PRAW)
13. Build App Store review collector
14. Build manual feedback entry
15. Build sentiment classification pipeline (OpenAI)
16. Build sentiment tracker page with trends + topics

### Phase 4: Features + OEM + Strategy
17. Build experiment tracker (SQLite CRUD)
18. Build OEM snapshot tracker
19. Build strategy workspace with PRD generator
20. Wire everything together with cross-references

---

## File Structure (New)

```
hub/
├── server.py              ← FastAPI app entry point
├── config.py              ← Hub configuration
├── db.py                  ← SQLite connection + schema
├── models.py              ← Pydantic models
├── routers/
│   ├── dashboard.py       ← KPI overview
│   ├── intel.py           ← CI pipeline
│   ├── data.py            ← Databricks proxy
│   ├── sentiment.py       ← Feedback aggregation
│   ├── features.py        ← Feature adoption
│   ├── oem.py             ← OEM placement
│   ├── strategy.py        ← PRDs + decisions
│   └── search.py          ← Unified search
├── collectors/
│   ├── reddit.py          ← Reddit API
│   ├── appstore.py        ← App review scraper
│   ├── twitter.py         ← Twitter/X search
│   └── manual.py          ← Manual entry
├── static/
│   ├── index.html         ← Main SPA
│   ├── styles.css         ← Dark theme styles
│   └── app.js             ← Frontend logic
└── requirements.txt       ← Python deps
```

---

## Dependencies (New)

```
fastapi>=0.109.0
uvicorn>=0.27.0
python-dotenv>=1.0.0       # already have
pydantic>=2.0.0             # already have
chromadb                    # already have
databricks-sql-connector    # already have
openai                      # already have
praw                        # Reddit API
aiohttp                     # async HTTP for collectors
```

---

## What This Unlocks

Once built, the hub becomes:
- **SSOT for Linear metrics** — no more switching between Databricks, dashboards, docs
- **Automated competitive monitoring** — pipeline runs on schedule, surfaces threats
- **User voice integration** — sentiment from Reddit/reviews feeds into PRD decisions
- **Feature tracking** — see if EPG Phase 1 is actually moving the needle
- **OEM dependency awareness** — track Amazon's 31.5% contribution actively
- **PRD generation** — pull data + intel + feedback into structured PRDs automatically
- **Queryable knowledge base** — semantic search across all intel, reports, and strategy docs
