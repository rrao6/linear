# Hub Integration Test Report

> Date: 2026-02-15
> Server: localhost:8888 (running from swift-deer worktree)
> Tester: Automated integration test

## Critical Finding: Database Instability

The server's SQLite database (`data/hub.db`) became empty (no tables) during testing.
This caused a cascade where 27/35 endpoints returned HTTP 500.

**Root cause hypothesis**: The `init_db()` function in `hub/db.py` runs `CREATE TABLE IF NOT EXISTS`
at module import, but the server's DB file (4KB, no tables) suggests either:
1. The DB was wiped by another process
2. A schema migration failed silently
3. The WAL journal became corrupted

**Recommendation**: Add DB health check to `/health` endpoint that verifies tables exist.

## Initial Test Results (before DB degradation)

These results were captured when the server was freshly started and all tables existed.

### PASS - Working with real data (18 endpoints)

| Endpoint | HTTP | Detail |
|----------|------|--------|
| GET /health | 200 | `{"status":"ok","service":"linear-hub"}` |
| GET /api/dashboard/overview | 200 | 979 bytes, real KPI data (linear_tvt_share: 4.28) |
| GET /api/dashboard/goals | 200 | 864 bytes, H2 FY26 goals |
| GET /api/intel/latest | 200 | 249KB scan data (run_id: 20260215_175003) |
| GET /api/intel/threats | 200 | Threats from YouTube TV, etc. |
| GET /api/intel/opportunities | 200 | Sports streaming opportunities |
| GET /api/intel/history | 200 | Scan history |
| GET /api/strategy/work | 200 | 8+ work items, 6558 bytes |
| GET /api/features/roadmap | 200 | Phase data (EPG browse & player) |
| GET /api/oem/platforms | 200 | Platform data (Amazon Fire TV, etc.) |
| GET /api/ask/history | 200 | 5639 bytes, previous queries |
| GET /api/monitor/health | 200 | Uptime, source counts |
| GET /api/monitor/sources | 200 | 5 sources (appstore, etc.) |
| GET /api/sentiment/trends | 200 | Empty array (endpoint exists) |
| POST /api/sentiment/feedback | 200 | Created id=2 |
| POST /api/strategy/work | 200 | Created id=9 |
| POST /api/strategy/learnings | 200 | Created id=1 |
| POST /api/strategy/verifications | 200 | Created id=1 |

### PASS - Working but empty data (10 endpoints)

| Endpoint | HTTP | Detail |
|----------|------|--------|
| GET /api/sentiment/summary | 200 | `{"total":0,"by_sentiment":{},"by_source":{},"avg_score":0}` |
| GET /api/sentiment/feed | 200 | `[]` |
| GET /api/sentiment/topics | 200 | `[]` |
| GET /api/features/experiments | 200 | `[]` |
| GET /api/problems | 200 | `[]` |
| GET /api/problems/by-area | 200 | `[]` |
| GET /api/knowledge/ideas | 200 | `[]` |
| GET /api/knowledge/insights | 200 | `[]` |
| GET /api/strategy/learnings | 200 | `[]` (before creation) |
| GET /api/strategy/verifications | 200 | `[]` (before creation) |

### DEGRADED - Working but no meaningful data (4 endpoints)

| Endpoint | HTTP | Detail |
|----------|------|--------|
| GET /api/insights/latest | 200 | `{"status":"no_data","message":"No insights generated yet"}` |
| GET /api/insights/brief | 200 | `{"status":"no_data","message":"No weekly brief generated yet"}` |
| GET /api/qa/status | 200 | `{"overall":"unknown","all_pass":false,"total_checks":0}` |
| GET /api/qa/drift | 200 | `{"drifting_metrics":0,"checks":[]}` |

### FAIL - Broken (3 endpoints)

| Endpoint | HTTP | Detail |
|----------|------|--------|
| POST /api/strategy/generate-prd | 500 | `OPENAI_API_KEY not configured` |
| POST /api/ask | 500 | `OPENAI_API_KEY not configured` |
| GET /api/search?q=linear | 307→200 | Partial: `intel_memory` errors due to missing OPENAI_API_KEY |

### Write Operations

| Operation | Result |
|-----------|--------|
| Create work item | PASS (id=9, verified in GET list) |
| Create learning | PASS (id=1, verified in GET list) |
| Create verification | PASS (id=1, verified in GET list) |

## Post-Degradation Results

After the DB tables disappeared, a re-run of all tests showed:

- **PASS**: 5 (health, goals, roadmap, oem/platforms, intel/latest)
- **EMPTY**: 3 (intel/threats, intel/opportunities, intel/history)
- **FAIL (500)**: 27 endpoints

The 5 endpoints that survived are those serving static/file-based data, not SQLite.

## Summary

| Category | Count | % |
|----------|-------|---|
| Fully working (real data) | 18 | 51% |
| Working (empty data) | 10 | 29% |
| Degraded (no meaningful data) | 4 | 11% |
| Broken (500 errors) | 3 | 9% |
| **Total endpoints tested** | **35** | |

## Issues to Fix (Priority Order)

1. **DB stability**: SQLite tables disappear during operation. Add table existence check to health endpoint.
2. **OPENAI_API_KEY**: generate-prd and ask endpoints hard-fail without it. Should return 503 with clear message.
3. **Empty pipelines**: Sentiment, problems, knowledge, experiments have no data flowing.
4. **Search redirect**: `/api/search?q=linear` returns 307 before 200 — should be direct 200.
5. **QA system**: No checks configured, always returns "unknown" status.

## Rerun Instructions

```bash
./tests/integration_test_hub.sh              # Default localhost:8888
./tests/integration_test_hub.sh http://host:port  # Custom URL
```
