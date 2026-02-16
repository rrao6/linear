# Linear Hub API Reference

> Base URL: `http://localhost:8888`
> Auto-generated docs: `http://localhost:8888/docs`

## Health & Root

### `GET /health`
Health check endpoint.
```bash
curl http://localhost:8888/health
```
Response: `{"status": "ok", "service": "linear-hub"}`

### `GET /`
Serves the SPA frontend (`hub/static/index.html`).

---

## Dashboard (`/api/dashboard`)

### `GET /api/dashboard/overview`
Main dashboard overview with KPIs, scan summary, intel counts, work stats, verifications, experiments, learnings, and sentiment.
```bash
curl http://localhost:8888/api/dashboard/overview
```

### `GET /api/dashboard/goals`
H2 FY26 goal tracking with initiatives and target metrics.
```bash
curl http://localhost:8888/api/dashboard/goals
```

---

## Intel (`/api/intel`)

### `GET /api/intel/runs`
List all competitive scan runs.
```bash
curl http://localhost:8888/api/intel/runs
```

### `GET /api/intel/run/{scan_date}/{run_id}`
Get full data for a specific scan run.
```bash
curl http://localhost:8888/api/intel/run/2026-02-15/20260215_145415
```

### `GET /api/intel/latest`
Get the most recent scan run data.
```bash
curl http://localhost:8888/api/intel/latest
```

### `GET /api/intel/threats`
Get threats from the latest analysis.
```bash
curl http://localhost:8888/api/intel/threats
```

### `GET /api/intel/opportunities`
Get opportunities from the latest analysis.
```bash
curl http://localhost:8888/api/intel/opportunities
```

### `GET /api/intel/trends`
Get trends from the latest analysis.
```bash
curl http://localhost:8888/api/intel/trends
```

### `GET /api/intel/competitors`
Get competitor profiles from the latest analysis.
```bash
curl http://localhost:8888/api/intel/competitors
```

### `POST /api/intel/scan`
Trigger a new competitive intelligence scan (runs in background).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip_memory` | bool | false | Skip ChromaDB vector memory phase |
| `skip_analysis` | bool | false | Skip analysis phase (collect+classify only) |
| `competitor` | string | null | Run for a single competitor |

```bash
curl -X POST "http://localhost:8888/api/intel/scan?skip_memory=true"
curl -X POST "http://localhost:8888/api/intel/scan?competitor=pluto_tv"
```

---

## Data (`/api/data`)

### `POST /api/data/query`
Execute raw SQL against Databricks.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sql` | string | yes | SQL query to execute |
| `limit` | int | no (100) | Max rows to return |

```bash
curl -X POST http://localhost:8888/api/data/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT COUNT(*) FROM core_prod.session.video_session WHERE date = \"2026-02-14\"", "limit": 10}'
```

### `POST /api/data/named`
Run a canonical named query.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Query name (e.g. `linear_tvt_share`) |
| `days` | int | no (30) | Lookback period in days |
| `limit` | int | no (50) | Max rows to return |

```bash
curl -X POST http://localhost:8888/api/data/named \
  -H "Content-Type: application/json" \
  -d '{"name": "top_linear_channels", "days": 30, "limit": 10}'
```

### `GET /api/data/queries`
List all available canonical queries.
```bash
curl http://localhost:8888/api/data/queries
```

### `GET /api/data/history`
Get query execution history.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Max entries |

```bash
curl "http://localhost:8888/api/data/history?limit=20"
```

### `GET /api/data/tables`
Return key Databricks table reference info and query gotchas.
```bash
curl http://localhost:8888/api/data/tables
```

---

## Sentiment (`/api/sentiment`)

### `GET /api/sentiment/summary`
Get overall sentiment summary (counts by sentiment, by source, avg score).
```bash
curl http://localhost:8888/api/sentiment/summary
```

### `GET /api/sentiment/feed`
Get sentiment feed with optional filters.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | null | Filter by source (reddit, appstore, sprout, manual) |
| `sentiment` | string | null | Filter by sentiment (positive, negative, neutral, mixed) |
| `limit` | int | 50 | Max items |

```bash
curl "http://localhost:8888/api/sentiment/feed?source=reddit&limit=10"
```

### `POST /api/sentiment/feedback`
Add a single feedback item.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | yes | Source identifier |
| `text` | string | yes | Feedback text |
| `sentiment` | string | no ("neutral") | positive/negative/neutral/mixed |
| `sentiment_score` | float | no (0.0) | Score from -1.0 to 1.0 |
| `topics` | list | no ([]) | Topic tags |
| `author` | string | no ("") | Author name |
| `url` | string | no ("") | Source URL |
| `metadata` | dict | no ({}) | Additional metadata |

```bash
curl -X POST http://localhost:8888/api/sentiment/feedback \
  -H "Content-Type: application/json" \
  -d '{"source": "manual", "text": "EPG navigation is confusing", "sentiment": "negative", "topics": ["epg", "navigation"]}'
```

### `POST /api/sentiment/feedback/batch`
Add multiple feedback items at once.
```bash
curl -X POST http://localhost:8888/api/sentiment/feedback/batch \
  -H "Content-Type: application/json" \
  -d '{"items": [{"source": "manual", "text": "Great content", "sentiment": "positive"}]}'
```

### `POST /api/sentiment/collect/sprout`
Ingest social listening data from Sprout Social. Accepts `SproutCollectPayload` with a list of `SproutMessage` objects.
```bash
curl -X POST http://localhost:8888/api/sentiment/collect/sprout \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"network": "twitter", "text": "Love Tubi!", "sentiment": "positive"}], "topic": "brand_mentions"}'
```

### `GET /api/sentiment/topics`
Get topic frequency from all feedback.
```bash
curl http://localhost:8888/api/sentiment/topics
```

---

## Features (`/api/features`)

### `GET /api/features/experiments`
List experiments with optional status filter.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | null | Filter by status (planned, running, analyzing, completed, killed) |
| `limit` | int | 100 | Max items |

```bash
curl "http://localhost:8888/api/features/experiments?status=running"
```

### `POST /api/features/experiments`
Create a new experiment.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Experiment name |
| `phase` | string | no | Phase (phase_1, phase_2, etc.) |
| `hypothesis` | string | no | What we expect |
| `status` | string | no ("planned") | Current status |
| `platforms` | list | no ([]) | Target platforms |
| `statsig_id` | string | no | Statsig experiment ID |
| `notes` | string | no | Additional notes |

```bash
curl -X POST http://localhost:8888/api/features/experiments \
  -H "Content-Type: application/json" \
  -d '{"name": "EPG Redesign v2", "phase": "phase_1", "hypothesis": "New EPG increases linear TVT by 5%"}'
```

### `PUT /api/features/experiments/{exp_id}`
Update an experiment. All fields optional.
```bash
curl -X PUT http://localhost:8888/api/features/experiments/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "running", "start_date": "2026-02-15"}'
```

### `GET /api/features/roadmap`
Get the EPG roadmap with phases and experiment statuses.
```bash
curl http://localhost:8888/api/features/roadmap
```

---

## OEM (`/api/oem`)

### `GET /api/oem/snapshots`
List OEM placement snapshots.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `platform` | string | null | Filter by platform |
| `limit` | int | 100 | Max items |

```bash
curl "http://localhost:8888/api/oem/snapshots?platform=amazon_fire"
```

### `POST /api/oem/snapshots`
Record an OEM placement snapshot.
```bash
curl -X POST http://localhost:8888/api/oem/snapshots \
  -H "Content-Type: application/json" \
  -d '{"platform": "roku", "date": "2026-02-15", "tubi_placement": {"position": 3, "section": "Live TV"}}'
```

### `GET /api/oem/platforms`
Get platform overview with known dependencies and competitor presence.
```bash
curl http://localhost:8888/api/oem/platforms
```

### `GET /api/oem/gracenote`
List Gracenote ID mappings.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | null | Filter by match_status (mapped, unmapped, ambiguous, manual) |
| `limit` | int | 100 | Max items |

```bash
curl "http://localhost:8888/api/oem/gracenote?status=unmapped"
```

### `POST /api/oem/gracenote`
Create a Gracenote ID mapping.
```bash
curl -X POST http://localhost:8888/api/oem/gracenote \
  -H "Content-Type: application/json" \
  -d '{"tubi_content_id": "100234", "gracenote_id": "SH012345", "content_name": "ION", "content_type": "channel", "match_status": "mapped"}'
```

---

## Strategy (`/api/strategy`)

### `GET /api/strategy/work`
List work items.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | null | Filter by status (open, in_progress, blocked, done, cancelled) |
| `type` | string | null | Filter by type (task, prd, change, plan, investigation) |
| `limit` | int | 100 | Max items |

```bash
curl "http://localhost:8888/api/strategy/work?status=open&type=task"
```

### `POST /api/strategy/work`
Create a work item.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | yes | Work item title |
| `type` | string | no ("task") | Item type |
| `description` | string | no | Detailed description |
| `priority` | string | no ("medium") | critical/high/medium/low |
| `owner` | string | no | Assignee |
| `tags` | list | no ([]) | Tags |
| `parent_id` | int | no | Parent work item ID |
| `metadata` | dict | no ({}) | Additional metadata |

```bash
curl -X POST http://localhost:8888/api/strategy/work \
  -H "Content-Type: application/json" \
  -d '{"title": "Investigate TVT share discrepancy", "type": "investigation", "priority": "high"}'
```

### `PUT /api/strategy/work/{item_id}`
Update a work item. All fields optional.
```bash
curl -X PUT http://localhost:8888/api/strategy/work/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "done"}'
```

### `GET /api/strategy/learnings`
List learnings.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `category` | string | null | Filter by category |
| `limit` | int | 100 | Max items |

```bash
curl "http://localhost:8888/api/strategy/learnings?category=data_issue"
```

### `POST /api/strategy/learnings`
Record a learning.
```bash
curl -X POST http://localhost:8888/api/strategy/learnings \
  -H "Content-Type: application/json" \
  -d '{"category": "query_gotcha", "title": "TVT is in milliseconds", "description": "Always divide by 3600000 for hours"}'
```

### `GET /api/strategy/verifications`
List data verifications.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | null | Filter by match_status |
| `limit` | int | 100 | Max items |

```bash
curl http://localhost:8888/api/strategy/verifications
```

### `POST /api/strategy/verifications`
Create a data verification record.
```bash
curl -X POST http://localhost:8888/api/strategy/verifications \
  -H "Content-Type: application/json" \
  -d '{"metric_name": "Linear TVT Share", "query_sql": "SELECT ...", "expected_value": "6.5%", "actual_value": "4.28%", "match_status": "mismatch"}'
```

### `GET /api/strategy/changelog`
List change log entries.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | string | null | Filter by type (decision, change, rollback, launch, finding) |
| `limit` | int | 100 | Max items |

```bash
curl http://localhost:8888/api/strategy/changelog
```

### `POST /api/strategy/changelog`
Record a change.
```bash
curl -X POST http://localhost:8888/api/strategy/changelog \
  -H "Content-Type: application/json" \
  -d '{"type": "decision", "title": "Use ChromaDB for vector memory", "description": "Lightweight, local, no infra needed"}'
```

### `POST /api/strategy/generate-prd`
Generate a PRD template populated with hub data.

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | PRD title |
| `problem` | string | Problem statement |
| `hypothesis` | string | What we expect |

```bash
curl -X POST http://localhost:8888/api/strategy/generate-prd \
  -H "Content-Type: application/json" \
  -d '{"title": "EPG Redesign", "problem": "Low linear engagement", "hypothesis": "Better EPG increases TVT by 5%"}'
```

---

## Search (`/api/search`)

### `GET /api/search/`
Unified search across ChromaDB vectors, work items, learnings, feedback, and changelog.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | yes | Search query |
| `limit` | int | no (20) | Max results per source |

```bash
curl "http://localhost:8888/api/search/?q=epg+navigation&limit=10"
```

### `GET /api/search/memory/stats`
Get ChromaDB vector memory statistics.
```bash
curl http://localhost:8888/api/search/memory/stats
```

---

## Endpoint Summary

| Router | Endpoints | Methods |
|--------|-----------|---------|
| Root | 2 | GET |
| Dashboard | 2 | GET |
| Intel | 8 | 7 GET, 1 POST |
| Data | 5 | 3 GET, 2 POST |
| Sentiment | 6 | 3 GET, 3 POST |
| Features | 4 | 2 GET, 1 POST, 1 PUT |
| OEM | 5 | 3 GET, 2 POST |
| Strategy | 9 | 4 GET, 4 POST, 1 PUT |
| Search | 2 | GET |
| **Total** | **43** | **27 GET, 12 POST, 2 PUT** |
