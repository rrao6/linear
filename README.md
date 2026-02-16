# Linear Hub

Single source of truth for Tubi's Linear/FAST TV strategy, competitive intelligence, data analysis, and metadata standards.

## Quick Start

```bash
# 1. Set up credentials
cp .env.example .env  # Add Databricks + OpenAI keys

# 2. Install Python dependencies
pip3 install feedparser beautifulsoup4 pyyaml chromadb python-dotenv playwright
python3 -m playwright install chromium

# 3. Install Claude Code skills
/plugin marketplace add .

# 4. Run competitive intelligence pipeline
python3 tools/scanner/orchestrator.py

# 5. Launch dashboard
python3 tools/dashboard/server.py
# Open http://localhost:8080
```

## Claude Code Skills

| Skill | Command | Description |
|---|---|---|
| **linear-data** | `/linear-data` | Query Databricks for linear metrics, user behavior, funnel analysis |
| **linear-research** | `/linear-research` | Competitive intel, market scanning, OEM placement tracking |
| **linear-strategy** | `/linear-strategy` | PRD generation, strategy synthesis, decision logging |

## Structure

```
linear/
├── plugins/           # Claude Code skills (3 skills)
├── tools/
│   ├── scanner/       # 6-phase CI pipeline (orchestrator, classifier, analysts, memory, browser)
│   └── dashboard/     # Web dashboard (server.py + index.html)
├── intel/             # Signals → Findings → Insights → Opportunities
├── analysis/          # Data analysis reports
├── docs/              # Knowledge base
├── data/              # ChromaDB vector store (auto-created)
└── ops/               # Templates and playbooks
```

## Competitive Intelligence Pipeline

Automated 6-phase pipeline adapted from multi-agent architecture:

1. **COLLECT** — Parallel RSS aggregation (41 feeds, 17 competitors) + channel count scraping
2. **CLASSIFY** — AI classification via gpt-4o-mini (relevance + impact scoring)
3. **ANALYZE** — 4 specialist agents: Threat Analyst, Opportunity Finder, Trend Tracker, Profiler
4. **MEMORY** — ChromaDB vector store with OpenAI embeddings for dedup + historical context
5. **SYNTHESIZE** — Executive brief generation via gpt-4o
6. **REPORT** — Markdown + JSON output to `intel/scans/`

```bash
# Full pipeline
python3 tools/scanner/orchestrator.py

# Quick scan (collect + classify only)
python3 tools/scanner/orchestrator.py --skip-analysis --skip-memory

# Browser automation for JS-rendered sites
python3 tools/scanner/browser.py --site pluto --screenshot

# Semantic search across all intel
python3 tools/scanner/memory.py --search "YouTube TV sports"
```

## Dashboard

Interactive web dashboard for viewing pipeline output:

```bash
python3 tools/dashboard/server.py
# http://localhost:8080
```

Features: overview stats, threat/opportunity/trend analysis, competitor profiles, channel count comparison chart, classified article feed, executive brief, vector memory search.

## Setup

### Required credentials (`.env`):
```
DATABRICKS_HOST=...
DATABRICKS_TOKEN=...
DATABRICKS_HTTP_PATH=...
OPENAI_API_KEY=...
```

### Python dependencies:
```bash
pip3 install feedparser beautifulsoup4 pyyaml chromadb python-dotenv playwright
pip3 install databricks-sql-connector  # For Databricks queries
python3 -m playwright install chromium  # For browser automation
```

## Operating Model

- **On demand**: Run `python3 tools/scanner/orchestrator.py` for fresh competitive scan
- **Daily**: Check dashboard for new signals, triage into findings
- **Weekly**: Publish pulse (top findings, insights, recommended actions)
- **Monthly**: Convert insights to opportunities, log decisions, update competitor profiles
- **Always**: Tie launches to opportunity, evidence, KPI, readout

## Verified Data

Pipeline tested and verified on 2026-02-15:
- 195 articles collected from 41 RSS feeds (0 errors)
- 51 actionable items classified
- 3 threats, 5 opportunities, 4 trends, 5 competitor profiles
- ChromaDB memory: 51 intel items, 5 profiles, 4 trends indexed
- Dashboard: all API endpoints operational
- Browser automation: Pluto TV 378 channels, Xumo 411 channels (exact)
