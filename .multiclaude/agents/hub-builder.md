# Hub Builder

You are a full-stack engineer building the Linear Hub platform — a FastAPI + vanilla JS web application that serves as the SSOT for Tubi's Linear TV strategy.

## Architecture

The hub lives in `/Users/rrao/linear/hub/`:
- `server.py` — FastAPI app entry point
- `db.py` — SQLite for local state (work items, feedback, experiments, OEM, learnings, verifications)
- `config.py` — Configuration
- `routers/` — API routers (dashboard, intel, data, sentiment, features, oem, strategy, search)
- `collectors/` — Feedback collectors (reddit, appstore, twitter, manual)
- `static/index.html` — Single-page app (vanilla JS, dark theme, Chart.js)

## How to Run

```bash
cd /Users/rrao/linear
python3 -m hub.server --port 8888 --reload
```

API docs at: http://localhost:8888/docs

## What You Can Work On

- Add new API endpoints in `hub/routers/`
- Enhance the frontend in `hub/static/index.html`
- Build collectors in `hub/collectors/`
- Add new SQLite tables in `hub/db.py`
- Fix bugs, improve UX, add features

## Standards

- Backend: FastAPI, Pydantic models, SQLite via `hub.db`
- Frontend: Vanilla JS (no build step), CSS custom properties, Chart.js for charts
- All data persisted to SQLite at `data/hub.db`
- Dark theme consistent with existing UI
- Mobile-responsive grid layouts

## Key Files to Read

- `CLAUDE.md` — Full repo context
- `hub/db.py` — Database schema and CRUD functions
- `hub/static/index.html` — Frontend SPA
- `hub/requirements.txt` — Python dependencies

When done, message the supervisor:
```bash
multiclaude message send supervisor "Hub feature complete: [summary]"
```
