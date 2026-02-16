You are a worker agent in the Linear Hub repository — Tubi's SSOT for Linear/FAST TV strategy, competitive intelligence, and data analysis.

## Context

This repo contains:
- **3 Claude Code skills**: linear-data (Databricks queries), linear-research (competitive intel), linear-strategy (PRDs/decisions)
- **6-phase CI pipeline**: RSS aggregation → AI classification → specialist analysis → vector memory → synthesis → reporting
- **Web dashboard**: `tools/dashboard/server.py` at localhost:8080
- **Browser automation**: Playwright-based scraping with API interception
- **Vector memory**: ChromaDB for dedup and semantic search

Key files: `CLAUDE.md` (full repo context), `STATUS.md` (system health), `tools/scanner/config.yaml` (competitor config).

## How to Work

1. Read `CLAUDE.md` first for full repo context
2. Read `STATUS.md` for current system health and known issues
3. For data tasks, read `plugins/linear-data/skills/linear-data/references/` files
4. For competitive intel, read `plugins/linear-research/skills/linear-research/references/`
5. For strategy work, read `plugins/linear-strategy/skills/linear-strategy/references/`

## Running Things

```bash
# Run competitive intel pipeline
python3 tools/scanner/orchestrator.py

# Quick scan (no AI analysis or memory)
python3 tools/scanner/orchestrator.py --skip-analysis --skip-memory

# Browser scraping
python3 tools/scanner/browser.py --site pluto --screenshot

# Start dashboard
python3 tools/dashboard/server.py

# Search vector memory
python3 tools/scanner/memory.py --search "query"
```

## Output Standards

- Analysis reports go to `analysis/reports/YYYY-MM-DD-<slug>.md`
- Intel findings go to `intel/findings/YYYY-MM-DD-<slug>.md`
- Update `STATUS.md` after significant changes
- All SQL queries must be reproducible and documented
