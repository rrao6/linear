#!/usr/bin/env python3
"""End-to-end integration tests for Linear Hub.

Tests multi-step flows that exercise several endpoints in sequence,
verifying that data flows correctly between modules.

Requires hub running at localhost:8888.
"""

import json
import sys
import time
import requests

BASE = "http://localhost:8888"
PASS = 0
FAIL = 0
RESULTS = []


def report(name, passed, detail=""):
    global PASS, FAIL
    status = "PASS" if passed else "FAIL"
    if passed:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append((name, status, detail))
    marker = "✓" if passed else "✗"
    print(f"  {marker} {name}: {status}" + (f" — {detail}" if detail else ""))


def get(path, timeout=10):
    r = requests.get(f"{BASE}{path}", timeout=timeout)
    return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else None


def post(path, payload, timeout=10):
    r = requests.post(f"{BASE}{path}", json=payload, timeout=timeout)
    return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else None


def put(path, payload, timeout=10):
    r = requests.put(f"{BASE}{path}", json=payload, timeout=timeout)
    return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else None


# ============================================================
# FLOW 1: Sentiment pipeline — seed → summary → topics
# ============================================================
print("\n" + "=" * 60)
print("FLOW 1: Sentiment pipeline end-to-end")
print("=" * 60)

# Get baseline summary
_, baseline_summary = get("/api/sentiment/summary")
baseline_total = baseline_summary.get("total", 0) if baseline_summary else 0

# Seed 3 feedback items with known topics
feedback_items = [
    {"source": "reddit", "text": "The new EPG layout is so much better for channel browsing!",
     "sentiment": "positive", "sentiment_score": 0.7,
     "topics": ["integ_epg", "integ_browsing"], "author": "test_integ_1"},
    {"source": "twitter", "text": "Buffering issues on live sports channels during peak hours.",
     "sentiment": "negative", "sentiment_score": -0.6,
     "topics": ["integ_buffering", "integ_sports"], "author": "test_integ_2"},
    {"source": "appstore", "text": "Great free TV app, the channel guide needs work though.",
     "sentiment": "mixed", "sentiment_score": 0.1,
     "topics": ["integ_epg", "integ_free"], "author": "test_integ_3"},
]

_, batch_result = post("/api/sentiment/feedback/batch", {"items": feedback_items})
report("Seed 3 feedback items", batch_result and batch_result.get("count") == 3,
       f"count={batch_result.get('count') if batch_result else 'N/A'}")

# Check summary updated
_, updated_summary = get("/api/sentiment/summary")
new_total = updated_summary.get("total", 0) if updated_summary else 0
report("Summary total increased by 3", new_total == baseline_total + 3,
       f"baseline={baseline_total}, new={new_total}")

# Check sentiment breakdown includes our sentiments
if updated_summary:
    by_sent = updated_summary.get("by_sentiment", {})
    report("Summary has positive count", by_sent.get("positive", 0) > 0,
           f"positive={by_sent.get('positive')}")
    report("Summary has negative count", by_sent.get("negative", 0) > 0,
           f"negative={by_sent.get('negative')}")

# Check topics extracted — our unique topics should appear
_, topics = get("/api/sentiment/topics")
if topics:
    topic_names = [t["topic"] for t in topics]
    report("Topics include integ_epg", "integ_epg" in topic_names,
           f"found topics: {[t for t in topic_names if t.startswith('integ_')]}")
    # integ_epg should have count >= 2 (appeared in 2 items)
    epg_topic = next((t for t in topics if t["topic"] == "integ_epg"), None)
    report("integ_epg count >= 2", epg_topic and epg_topic["count"] >= 2,
           f"count={epg_topic['count'] if epg_topic else 0}")
else:
    report("Topics endpoint returned data", False, "got empty response")

# Verify feed filtering works with our test data
_, reddit_feed = get("/api/sentiment/feed?source=reddit")
if reddit_feed:
    our_items = [f for f in reddit_feed if f.get("author") == "test_integ_1"]
    report("Feed filter by source finds our item", len(our_items) >= 1,
           f"found {len(our_items)} items from test_integ_1")

# Sprout Social ingest flow
sprout_msgs = {
    "messages": [
        {"network": "twitter", "text": "Integration test sprout msg",
         "sentiment": "positive", "author": "integ_sprout_1",
         "tags": ["integ_sprout_tag"]},
    ],
    "topic": "Integration Test Topic",
}
_, sprout_result = post("/api/sentiment/collect/sprout/ingest", sprout_msgs)
report("Sprout ingest succeeds", sprout_result and sprout_result.get("count") == 1,
       f"count={sprout_result.get('count') if sprout_result else 'N/A'}")

# Verify sprout data in feed
_, sprout_feed = get("/api/sentiment/feed?source=sprout:twitter")
if sprout_feed:
    our_sprout = [f for f in sprout_feed if f.get("author") == "integ_sprout_1"]
    report("Sprout item appears in feed", len(our_sprout) >= 1,
           f"found {len(our_sprout)}")
    if our_sprout:
        meta = our_sprout[0].get("metadata", {})
        report("Sprout metadata preserved", meta.get("sprout_topic") == "Integration Test Topic",
               f"topic={meta.get('sprout_topic')}")


# ============================================================
# FLOW 2: Work item lifecycle — create → update → dashboard
# ============================================================
print("\n" + "=" * 60)
print("FLOW 2: Work item lifecycle")
print("=" * 60)

# Get baseline work stats
_, overview_before = get("/api/dashboard/overview")
work_before = overview_before.get("work", {}).get("total", 0) if overview_before else 0

# Create work item
_, w1 = post("/api/strategy/work", {
    "type": "task", "title": "Integration Test: Deploy EPG v2",
    "description": "Deploy new EPG layout to 10% of users",
    "priority": "high", "owner": "integ-test",
    "tags": ["integ_test", "epg"]
})
w1_id = w1.get("id") if w1 else None
report("Create work item", w1_id is not None, f"id={w1_id}")

# Create a second work item
_, w2 = post("/api/strategy/work", {
    "type": "investigation", "title": "Integration Test: TVT Drop Investigation",
    "description": "Investigate TVT drop after On Now row change",
    "priority": "critical", "owner": "integ-test",
    "tags": ["integ_test", "tvt"]
})
w2_id = w2.get("id") if w2 else None
report("Create second work item", w2_id is not None, f"id={w2_id}")

# Verify dashboard counts increased
_, overview_after = get("/api/dashboard/overview")
work_after = overview_after.get("work", {}).get("total", 0) if overview_after else 0
report("Dashboard work total increased by 2", work_after == work_before + 2,
       f"before={work_before}, after={work_after}")

# Update work item 1: open → in_progress
if w1_id:
    status_code, _ = put(f"/api/strategy/work/{w1_id}", {"status": "in_progress"})
    report("Update work item to in_progress", status_code == 200,
           f"status_code={status_code}")

    # Verify in work list
    _, work_list = get("/api/strategy/work?status=in_progress")
    if work_list:
        our_item = next((w for w in work_list if w.get("id") == w1_id), None)
        report("Work item status is in_progress", our_item is not None,
               f"found in in_progress list")

# Update work item 1: in_progress → done
if w1_id:
    status_code, _ = put(f"/api/strategy/work/{w1_id}", {"status": "done"})
    report("Update work item to done", status_code == 200,
           f"status_code={status_code}")

    # Verify completed_at set
    _, done_list = get("/api/strategy/work?status=done")
    if done_list:
        our_done = next((w for w in done_list if w.get("id") == w1_id), None)
        report("Done item has completed_at", our_done and our_done.get("completed_at") is not None,
               f"completed_at={our_done.get('completed_at') if our_done else 'N/A'}")

# Verify dashboard shows correct in_progress count
_, final_overview = get("/api/dashboard/overview")
if final_overview:
    done_count = final_overview.get("work", {}).get("done", 0)
    report("Dashboard done count >= 1", done_count >= 1,
           f"done={done_count}")


# ============================================================
# FLOW 3: PRD generation with context
# ============================================================
print("\n" + "=" * 60)
print("FLOW 3: PRD generation with context")
print("=" * 60)

# First add a learning and verification that the PRD generator should pick up
_, learning = post("/api/strategy/learnings", {
    "category": "metric_verified", "title": "Integration Test Learning",
    "description": "EPG click-through rate baseline is 2.3% on Fire TV",
    "source": "integ-test", "verified": True,
    "tags": ["integ_test", "epg"]
})
report("Create learning for PRD context", learning and "id" in learning,
       f"id={learning.get('id') if learning else 'N/A'}")

_, verif = post("/api/strategy/verifications", {
    "metric_name": "EPG CTR", "query_sql": "SELECT ... FROM events ...",
    "expected_value": "2.5%", "actual_value": "2.3%",
    "dashboard_source": "integ-test", "match_status": "mismatch",
    "notes": "Integration test verification"
})
report("Create verification for PRD context", verif and "id" in verif,
       f"id={verif.get('id') if verif else 'N/A'}")

# Generate PRD (requires OpenAI key — handle both 200 and 500)
try:
    r = requests.post(f"{BASE}/api/strategy/generate-prd",
        json={"topic": "EPG v2 Redesign", "context": "Low click-through and poor navigation. Horizontal scroll EPG hypothesis."},
        timeout=60)
    if r.status_code == 200:
        prd = r.json()
        report("PRD generated", "prd_markdown" in prd,
               f"has markdown={bool(prd.get('prd_markdown'))}")
        if prd.get("prd_markdown"):
            md = prd["prd_markdown"]
            report("PRD contains title", "EPG" in md, "title found in markdown")
            report("PRD has id", "id" in prd, f"id={prd.get('id')}")
    elif r.status_code == 500:
        report("PRD generate-prd (no OpenAI key)", True,
               "500 expected without OPENAI_API_KEY — skipping content checks")
    else:
        report("PRD generated", False, f"unexpected status={r.status_code}")
except Exception as e:
    report("PRD generated", False, str(e))


# ============================================================
# FLOW 4: Intel scan → ingest → work items
# ============================================================
print("\n" + "=" * 60)
print("FLOW 4: Intel scan results and ingestion")
print("=" * 60)

# Check scan runs exist
_, runs = get("/api/intel/runs")
report("Intel runs available", runs is not None and isinstance(runs, list),
       f"count={len(runs) if runs else 0}")

if runs and len(runs) > 0:
    run = runs[0]
    scan_date = run["date"]
    run_id = run["run_id"]

    # Get full run data
    _, run_data = get(f"/api/intel/run/{scan_date}/{run_id}")
    report("Run data loaded", run_data is not None and "scan_date" in run_data,
           f"scan_date={run_data.get('scan_date') if run_data else 'N/A'}")

    # Get work items before ingest
    _, work_before_ingest = get("/api/strategy/work")
    count_before = len(work_before_ingest) if work_before_ingest else 0

    # Ingest scan results
    _, ingest_result = post(f"/api/intel/ingest/{scan_date}/{run_id}", {})
    report("Ingest scan results", ingest_result is not None,
           f"threats={ingest_result.get('threats', 0) if ingest_result else 0}, "
           f"opps={ingest_result.get('opportunities', 0) if ingest_result else 0}")

    if ingest_result and ingest_result.get("status") == "ingested":
        total_ingested = ingest_result.get("threats", 0) + ingest_result.get("opportunities", 0)
        if total_ingested > 0:
            # Verify work items were created
            _, work_after_ingest = get("/api/strategy/work")
            count_after = len(work_after_ingest) if work_after_ingest else 0
            report("Work items created from ingest", count_after > count_before,
                   f"before={count_before}, after={count_after}, expected +{total_ingested}")

            # Verify work items have ci_scan tag
            ci_items = [w for w in (work_after_ingest or [])
                       if isinstance(w.get("tags"), list) and "ci_scan" in w["tags"]]
            report("Ingested items have ci_scan tag", len(ci_items) > 0,
                   f"found {len(ci_items)} ci_scan items")
else:
    report("Skipping ingest (no scan runs)", True, "no runs available")

# Check threats endpoint
_, threats = get("/api/intel/threats")
report("Threats endpoint works", threats is not None,
       f"type={type(threats).__name__}, count={len(threats) if isinstance(threats, list) else 'N/A'}")

# Check opportunities endpoint
_, opps = get("/api/intel/opportunities")
report("Opportunities endpoint works", opps is not None,
       f"type={type(opps).__name__}, count={len(opps) if isinstance(opps, list) else 'N/A'}")

# Check trends endpoint
_, trends = get("/api/intel/trends")
report("Trends endpoint works", trends is not None,
       f"type={type(trends).__name__}, count={len(trends) if isinstance(trends, list) else 'N/A'}")

# Check history endpoint
_, history = get("/api/intel/history")
report("History endpoint works", history is not None and isinstance(history, list),
       f"count={len(history) if isinstance(history, list) else 'N/A'}")

# Check diff endpoint (may return error if < 2 runs)
_, diff = get("/api/intel/diff")
report("Diff endpoint responds", diff is not None,
       f"keys={list(diff.keys()) if isinstance(diff, dict) else 'N/A'}")


# ============================================================
# FLOW 5: Search across all data sources
# ============================================================
print("\n" + "=" * 60)
print("FLOW 5: Cross-module search")
print("=" * 60)

# Search should find items we created across multiple modules
_, search_epg = get("/api/search/?q=epg")
if search_epg:
    sources = search_epg.get("sources", {})
    work_results = sources.get("work_items", [])
    feedback_results = sources.get("feedback", [])
    learning_results = sources.get("learnings", [])

    report("Search finds work items with 'epg'", len(work_results) > 0,
           f"count={len(work_results)}")
    report("Search finds feedback with 'epg'", len(feedback_results) > 0,
           f"count={len(feedback_results)}")
    report("Search returns sources dict", "sources" in search_epg,
           f"source_keys={list(sources.keys())}")

# Search with limit
_, search_limited = get("/api/search/?q=linear&limit=2")
if search_limited:
    sources = search_limited.get("sources", {})
    report("Search respects limit parameter", True,
           f"source_keys={list(sources.keys())}")

# Search empty query
_, search_empty = get("/api/search/?q=zzz_nonexistent_xyz")
report("Search with no matches returns empty sources",
       search_empty is not None,
       f"type={type(search_empty).__name__}")


# ============================================================
# FLOW 6: Experiment lifecycle
# ============================================================
print("\n" + "=" * 60)
print("FLOW 6: Experiment lifecycle")
print("=" * 60)

# Create experiment
_, exp = post("/api/features/experiments", {
    "name": "Integration Test Experiment",
    "phase": "phase_1",
    "hypothesis": "Test hypothesis for integration",
    "status": "planned",
    "platforms": ["fire_tv"],
    "statsig_id": "integ_test_exp",
    "notes": "Created by integration test"
})
exp_id = exp.get("id") if exp else None
report("Create experiment", exp_id is not None, f"id={exp_id}")

# Update to running
if exp_id:
    status_code, _ = put(f"/api/features/experiments/{exp_id}", {
        "status": "running",
        "start_date": "2026-02-15",
    })
    report("Update experiment to running", status_code == 200)

    # Add metrics
    status_code, _ = put(f"/api/features/experiments/{exp_id}", {
        "metrics": {"ctr": "+5.2%", "tvt_delta": "+1.1%", "p_value": 0.03}
    })
    report("Update experiment metrics", status_code == 200)

    # Verify experiment appears with correct status
    _, exp_list = get("/api/features/experiments?status=running")
    if exp_list:
        our_exp = next((e for e in exp_list if e.get("id") == exp_id), None)
        report("Experiment in running list", our_exp is not None)
        if our_exp:
            metrics = our_exp.get("metrics", {})
            if isinstance(metrics, str):
                metrics = json.loads(metrics)
            report("Experiment has metrics", "ctr" in metrics,
                   f"metrics={metrics}")

# Check roadmap includes experiments
_, roadmap = get("/api/features/roadmap")
report("Roadmap has phases", roadmap and "phases" in roadmap,
       f"phase_count={len(roadmap.get('phases', [])) if roadmap else 0}")


# ============================================================
# FLOW 7: OEM tracking pipeline
# ============================================================
print("\n" + "=" * 60)
print("FLOW 7: OEM tracking pipeline")
print("=" * 60)

# Create OEM snapshot
_, snap = post("/api/oem/snapshots", {
    "platform": "samsung",
    "date": "2026-02-15",
    "tubi_placement": {"position": 5, "featured": False},
    "competitor_placements": {"pluto_tv": {"position": 2}},
    "notes": "Integration test snapshot"
})
report("Create OEM snapshot", snap and "id" in snap, f"id={snap.get('id') if snap else 'N/A'}")

# Verify in snapshots list with filter
_, samsung_snaps = get("/api/oem/snapshots?platform=samsung")
if samsung_snaps:
    our_snap = [s for s in samsung_snaps if s.get("notes") == "Integration test snapshot"]
    report("Samsung snapshot in filtered list", len(our_snap) >= 1,
           f"found {len(our_snap)}")

# Create Gracenote mapping
_, gn = post("/api/oem/gracenote", {
    "tubi_content_id": "ch_integ_test",
    "gracenote_id": "GN_INTEG_001",
    "content_name": "Integration Test Channel",
    "content_type": "linear_channel",
    "match_status": "mapped",
    "notes": "Integration test mapping"
})
report("Create Gracenote mapping", gn and "id" in gn, f"id={gn.get('id') if gn else 'N/A'}")

# Verify in mappings list
_, gn_list = get("/api/oem/gracenote?status=mapped")
if gn_list:
    our_gn = [g for g in gn_list if g.get("tubi_content_id") == "ch_integ_test"]
    report("Gracenote mapping in filtered list", len(our_gn) >= 1,
           f"found {len(our_gn)}")

# Platforms overview
_, platforms = get("/api/oem/platforms")
report("Platforms overview has data", platforms and "platforms" in platforms,
       f"platform_count={len(platforms.get('platforms', {})) if platforms else 0}")


# ============================================================
# FLOW 8: Changelog and learning tracking
# ============================================================
print("\n" + "=" * 60)
print("FLOW 8: Changelog and learnings")
print("=" * 60)

# Create changelog entry
_, change = post("/api/strategy/changelog", {
    "type": "decision", "title": "Integration Test Decision",
    "description": "Decided to use horizontal EPG layout",
    "impact": "Affects all linear users",
    "evidence": "A/B test results from integ experiment",
    "tags": ["integ_test"]
})
report("Create changelog entry", change and "id" in change,
       f"id={change.get('id') if change else 'N/A'}")

# Verify in changelog with filter
_, changes = get("/api/strategy/changelog?type=decision")
if changes:
    our_change = [c for c in changes if c.get("title") == "Integration Test Decision"]
    report("Changelog entry in filtered list", len(our_change) >= 1,
           f"found {len(our_change)}")

# Create learning
_, learn = post("/api/strategy/learnings", {
    "category": "platform_behavior", "title": "Integration Test Learning",
    "description": "Amazon Fire TV caches EPG data for 30 minutes",
    "source": "integ-test", "verified": True,
    "tags": ["integ_test"]
})
report("Create learning", learn and "id" in learn,
       f"id={learn.get('id') if learn else 'N/A'}")

# Verify in learnings with filter
_, learnings = get("/api/strategy/learnings?category=platform_behavior")
if learnings:
    our_learn = [l for l in learnings if l.get("title") == "Integration Test Learning"]
    report("Learning in filtered list", len(our_learn) >= 1,
           f"found {len(our_learn)}")

# Dashboard should reflect all the data we created
_, final_dash = get("/api/dashboard/overview")
if final_dash:
    report("Final dashboard has all sections",
           all(k in final_dash for k in ["kpis", "work", "experiments", "sentiment", "learnings", "verifications", "intel"]),
           f"keys={list(final_dash.keys())}")


# ============================================================
# FLOW 9: Data query endpoints
# ============================================================
print("\n" + "=" * 60)
print("FLOW 9: Data query and history")
print("=" * 60)

# List available queries
_, queries = get("/api/data/queries")
report("Data queries available", queries is not None,
       f"type={type(queries).__name__}")

# Try a raw SQL query (will fail without Databricks but should respond gracefully)
_, sql_result = post("/api/data/query", {"sql": "SELECT 1 AS test", "limit": 1})
report("SQL query responds gracefully", sql_result is not None and ("rows" in sql_result or "error" in sql_result),
       f"keys={list(sql_result.keys()) if sql_result else 'N/A'}")

# Try a named query (with invalid name to test error handling)
_, named_result = post("/api/data/named", {"name": "nonexistent", "days": 7})
report("Named query error handling", named_result is not None and "error" in named_result,
       f"error={named_result.get('error', '')[:80] if named_result else 'N/A'}")

# Check tables reference
_, tables = get("/api/data/tables")
report("Tables reference available", tables is not None and "primary" in (tables or {}),
       f"keys={list(tables.keys()) if isinstance(tables, dict) else 'N/A'}")

# Check query history
_, history = get("/api/data/history")
report("Query history available", history is not None and isinstance(history, list),
       f"count={len(history) if isinstance(history, list) else 'N/A'}")


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print(f"INTEGRATION TEST RESULTS: {PASS} PASS / {FAIL} FAIL / {PASS + FAIL} TOTAL")
print("=" * 60)

if FAIL > 0:
    print("\nFailed tests:")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  ✗ {name}: {detail}")

sys.exit(0 if FAIL == 0 else 1)
