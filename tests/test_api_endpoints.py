#!/usr/bin/env python3
"""Comprehensive API endpoint test suite for Linear Hub at localhost:8888.

Tests all endpoints, creates test data, and verifies dashboard aggregation.
"""

import json
import sys
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


def test_get(name, path, expect_key=None, expect_type=None):
    """Test a GET endpoint."""
    try:
        r = requests.get(f"{BASE}{path}", timeout=10)
        ok = r.status_code == 200
        data = r.json()
        if expect_key and ok:
            ok = expect_key in data if isinstance(data, dict) else True
        if expect_type and ok:
            ok = isinstance(data, expect_type)
        report(name, ok, f"status={r.status_code}")
        return data
    except Exception as e:
        report(name, False, str(e))
        return None


def test_post(name, path, payload, expect_key=None):
    """Test a POST endpoint."""
    try:
        r = requests.post(f"{BASE}{path}", json=payload, timeout=10)
        ok = r.status_code == 200
        data = r.json()
        if expect_key and ok:
            ok = expect_key in data
        report(name, ok, f"status={r.status_code}, body={json.dumps(data)[:200]}")
        return data
    except Exception as e:
        report(name, False, str(e))
        return None


def test_put(name, path, payload):
    """Test a PUT endpoint."""
    try:
        r = requests.put(f"{BASE}{path}", json=payload, timeout=10)
        ok = r.status_code == 200
        data = r.json()
        report(name, ok, f"status={r.status_code}")
        return data
    except Exception as e:
        report(name, False, str(e))
        return None


# ============================================================
# PHASE 1: Test all GET endpoints (read-only, no data needed)
# ============================================================
print("\n" + "=" * 60)
print("PHASE 1: Testing all GET endpoints")
print("=" * 60)

# Core
test_get("GET /health", "/health", expect_key="status")

# Dashboard
test_get("GET /api/dashboard/overview", "/api/dashboard/overview", expect_key="kpis")
test_get("GET /api/dashboard/goals", "/api/dashboard/goals", expect_key="goals")

# Intel
test_get("GET /api/intel/runs", "/api/intel/runs", expect_type=list)
test_get("GET /api/intel/latest", "/api/intel/latest")
test_get("GET /api/intel/threats", "/api/intel/threats")
test_get("GET /api/intel/opportunities", "/api/intel/opportunities")
test_get("GET /api/intel/trends", "/api/intel/trends")
test_get("GET /api/intel/competitors", "/api/intel/competitors")

# Data
test_get("GET /api/data/queries", "/api/data/queries")
test_get("GET /api/data/history", "/api/data/history", expect_type=list)
test_get("GET /api/data/tables", "/api/data/tables", expect_key="primary")

# Sentiment
test_get("GET /api/sentiment/summary", "/api/sentiment/summary")
test_get("GET /api/sentiment/feed", "/api/sentiment/feed", expect_type=list)
test_get("GET /api/sentiment/topics", "/api/sentiment/topics", expect_type=list)
test_get("GET /api/sentiment/trends", "/api/sentiment/trends")

# Features
test_get("GET /api/features/experiments", "/api/features/experiments", expect_type=list)
test_get("GET /api/features/roadmap", "/api/features/roadmap", expect_key="phases")

# OEM
test_get("GET /api/oem/snapshots", "/api/oem/snapshots", expect_type=list)
test_get("GET /api/oem/platforms", "/api/oem/platforms", expect_key="platforms")
test_get("GET /api/oem/gracenote", "/api/oem/gracenote", expect_type=list)

# Strategy
test_get("GET /api/strategy/work", "/api/strategy/work", expect_type=list)
test_get("GET /api/strategy/learnings", "/api/strategy/learnings", expect_type=list)
test_get("GET /api/strategy/verifications", "/api/strategy/verifications", expect_type=list)
test_get("GET /api/strategy/changelog", "/api/strategy/changelog", expect_type=list)

# Search
test_get("GET /api/search/?q=linear", "/api/search/?q=linear", expect_key="sources")
test_get("GET /api/search/memory/stats", "/api/search/memory/stats")

# QA
test_get("GET /api/qa/status", "/api/qa/status", expect_key="overall")
test_get("GET /api/qa/history", "/api/qa/history", expect_key="checks")
test_get("GET /api/qa/drift", "/api/qa/drift", expect_key="drifting_metrics")

# Monitor
test_get("GET /api/monitor/health", "/api/monitor/health", expect_key="status")
test_get("GET /api/monitor/sources", "/api/monitor/sources", expect_type=list)
test_get("GET /api/monitor/log", "/api/monitor/log", expect_type=list)

# Knowledge
test_get("GET /api/knowledge/reviews", "/api/knowledge/reviews", expect_type=list)
test_get("GET /api/knowledge/ideas", "/api/knowledge/ideas", expect_type=list)
test_get("GET /api/knowledge/insights", "/api/knowledge/insights", expect_type=list)


# ============================================================
# PHASE 2: Create test data
# ============================================================
print("\n" + "=" * 60)
print("PHASE 2: Creating test data")
print("=" * 60)

# --- 3 Work Items ---
print("\n--- Creating 3 Work Items ---")
work_ids = []

w1 = test_post("POST work item 1: EPG Navigation Redesign",
    "/api/strategy/work",
    {"type": "epic", "title": "EPG Navigation Redesign",
     "description": "Redesign the EPG grid for faster channel switching and improved accessibility",
     "priority": "high", "owner": "linear-team",
     "tags": ["epg", "ux", "linear"]})
if w1: work_ids.append(w1["id"])

w2 = test_post("POST work item 2: Live Sports Integration",
    "/api/strategy/work",
    {"type": "task", "title": "Live Sports Deep-link Integration",
     "description": "Enable deep-linking from sports scores widgets to live linear sports channels",
     "priority": "high", "owner": "platform-team",
     "tags": ["sports", "deeplink", "linear"]})
if w2: work_ids.append(w2["id"])

w3 = test_post("POST work item 3: Channel Discovery ML",
    "/api/strategy/work",
    {"type": "task", "title": "ML-based Channel Recommendations",
     "description": "Train collaborative filtering model on linear viewing patterns for personalized channel recs",
     "priority": "medium", "owner": "ml-team",
     "tags": ["ml", "discovery", "linear"]})
if w3: work_ids.append(w3["id"])

# Update one work item
if work_ids:
    test_put("PUT update work item 1 to in_progress",
        f"/api/strategy/work/{work_ids[0]}",
        {"status": "in_progress"})

# --- 2 Experiments ---
print("\n--- Creating 2 Experiments ---")
exp_ids = []

e1 = test_post("POST experiment 1: EPG Grid A/B Test",
    "/api/features/experiments",
    {"name": "EPG Grid Layout A/B Test",
     "phase": "phase_1",
     "hypothesis": "Horizontal-scroll EPG with channel logos increases linear TVT by 5%",
     "status": "running",
     "platforms": ["fire_tv", "roku", "samsung"],
     "statsig_id": "epg_grid_v2",
     "notes": "Control: current vertical grid. Treatment: horizontal scroll with previews."})
if e1: exp_ids.append(e1["id"])

e2 = test_post("POST experiment 2: On Now Personalization",
    "/api/features/experiments",
    {"name": "On Now Container Personalization",
     "phase": "phase_2",
     "hypothesis": "Personalized On Now row ordering increases linear session starts by 8%",
     "status": "planned",
     "platforms": ["fire_tv", "roku"],
     "statsig_id": "on_now_personalized",
     "notes": "Uses collaborative filtering from ML-based channel recs."})
if e2: exp_ids.append(e2["id"])

# Update one experiment
if exp_ids:
    test_put("PUT update experiment 1 metrics",
        f"/api/features/experiments/{exp_ids[0]}",
        {"metrics": {"linear_tvt_delta": "+3.2%", "epg_ctr": "+12%", "p_value": 0.02}})

# --- 5 Feedback Items about Tubi Linear ---
print("\n--- Creating 5 Feedback Items (Tubi Linear) ---")

feedback_items = [
    {"source": "reddit", "text": "Tubi's EPG is clunky compared to YouTube TV. Takes too many clicks to switch channels and the grid scrolls too slowly on my Roku.",
     "sentiment": "negative", "sentiment_score": -0.7,
     "topics": ["epg", "navigation", "roku", "ux"],
     "author": "u/cord_cutter_2024", "url": "https://reddit.com/r/cordcutters/example1"},
    {"source": "appstore", "text": "Love the free live channels! Ad breaks are a bit long during movies but way better than paying for cable. The NFL games on Fox were great quality.",
     "sentiment": "positive", "sentiment_score": 0.6,
     "topics": ["ads", "live_sports", "nfl", "content_quality"],
     "author": "StarWatcher99", "url": ""},
    {"source": "twitter", "text": "Only 340 channels on Tubi? Pluto has 378 and Xumo has 411. Need more variety, especially international channels and music.",
     "sentiment": "negative", "sentiment_score": -0.4,
     "topics": ["channel_count", "competition", "content_variety"],
     "author": "@streaming_fan", "url": "https://twitter.com/example2"},
    {"source": "reddit", "text": "Content discovery on Tubi linear is broken. There's no way to see what's coming up next on a channel without clicking into it. Need an EPG preview or mini-guide.",
     "sentiment": "negative", "sentiment_score": -0.6,
     "topics": ["content_discovery", "epg", "program_guide", "ux"],
     "author": "u/free_tv_watcher", "url": "https://reddit.com/r/tubi/example3"},
    {"source": "manual", "text": "World Cup 2026 on Tubi linear will be a game-changer. If the live sports experience is smooth and the EPG surfaces matches easily, it could drive massive linear TVT growth.",
     "sentiment": "positive", "sentiment_score": 0.8,
     "topics": ["live_sports", "world_cup", "linear_growth", "epg"],
     "author": "internal-analyst", "url": ""},
]

fb_result = test_post("POST feedback batch (5 items)",
    "/api/sentiment/feedback/batch",
    {"items": feedback_items},
    expect_key="count")
if fb_result:
    report("Feedback batch count check", fb_result.get("count") == 5,
           f"expected 5, got {fb_result.get('count')}")

# --- 2 OEM Snapshots ---
print("\n--- Creating 2 OEM Snapshots ---")

test_post("POST OEM snapshot 1: Amazon Fire TV",
    "/api/oem/snapshots",
    {"platform": "amazon_fire",
     "date": "2026-02-15",
     "tubi_placement": {"live_tab_position": 3, "home_row": 5, "featured": False,
                        "deeplink_enabled": True, "channels_indexed": 340},
     "competitor_placements": {"freevee": {"position": 1, "featured": True},
                                "pluto_tv": {"position": 2, "featured": True},
                                "xumo": {"position": 4, "featured": False}},
     "notes": "Amazon continues to favor Freevee in Live tab. Tubi at position 3."})

test_post("POST OEM snapshot 2: Roku",
    "/api/oem/snapshots",
    {"platform": "roku",
     "date": "2026-02-15",
     "tubi_placement": {"live_guide_position": 4, "home_row": 3, "featured": True,
                        "channels_indexed": 285},
     "competitor_placements": {"roku_channel": {"position": 1, "featured": True},
                                "pluto_tv": {"position": 2, "featured": True},
                                "xumo": {"position": 3, "featured": False}},
     "notes": "Roku Channel dominant. Tubi featured on home but lower in live guide."})


# ============================================================
# PHASE 3: Verify data was persisted correctly
# ============================================================
print("\n" + "=" * 60)
print("PHASE 3: Verifying persisted data")
print("=" * 60)

# Verify work items
work_data = test_get("GET /api/strategy/work (verify 3 items)", "/api/strategy/work", expect_type=list)
if work_data:
    # Count items we created (filter by our tags)
    our_items = [w for w in work_data if "linear" in (w.get("tags") or [])]
    report("Work items count >= 3", len(our_items) >= 3, f"found {len(our_items)} with 'linear' tag")

# Verify experiments
exp_data = test_get("GET /api/features/experiments (verify 2 experiments)", "/api/features/experiments", expect_type=list)
if exp_data:
    our_exps = [e for e in exp_data if "EPG" in e.get("name", "") or "On Now" in e.get("name", "")]
    report("Experiments count >= 2", len(our_exps) >= 2, f"found {len(our_exps)}")

# Verify feedback
feed_data = test_get("GET /api/sentiment/feed (verify 5 feedback)", "/api/sentiment/feed", expect_type=list)
if feed_data:
    report("Feedback items >= 5", len(feed_data) >= 5, f"found {len(feed_data)} total feedback items")

# Verify sentiment summary updated
summary = test_get("GET /api/sentiment/summary (after feedback)", "/api/sentiment/summary")
if summary:
    report("Sentiment total >= 5", summary.get("total", 0) >= 5,
           f"total={summary.get('total')}, avg_score={summary.get('avg_score')}")

# Verify topics extracted
topics = test_get("GET /api/sentiment/topics (verify topic extraction)", "/api/sentiment/topics", expect_type=list)
if topics:
    topic_names = [t["topic"] for t in topics]
    has_epg = "epg" in topic_names
    report("Topics include 'epg'", has_epg, f"topics: {topic_names[:10]}")

# Verify OEM snapshots
snaps = test_get("GET /api/oem/snapshots (verify 2 snapshots)", "/api/oem/snapshots", expect_type=list)
if snaps:
    our_snaps = [s for s in snaps if s.get("date") == "2026-02-15"]
    report("OEM snapshots >= 2", len(our_snaps) >= 2, f"found {len(our_snaps)} for 2026-02-15")

# Verify search finds our data
search = test_get("GET /api/search/?q=epg", "/api/search/?q=epg", expect_key="sources")
if search:
    sources = search.get("sources", {})
    has_results = any(len(v) > 0 for v in sources.values() if isinstance(v, list))
    report("Search finds 'epg' across sources", has_results,
           f"work={len(sources.get('work_items', []))}, feedback={len(sources.get('feedback', []))}")


# ============================================================
# PHASE 4: Verify dashboard overview aggregation
# ============================================================
print("\n" + "=" * 60)
print("PHASE 4: Verifying dashboard overview aggregation")
print("=" * 60)

overview = test_get("GET /api/dashboard/overview (final)", "/api/dashboard/overview", expect_key="kpis")
if overview:
    # KPIs
    kpis = overview.get("kpis", {})
    report("KPIs: linear_tvt_share_current present", "linear_tvt_share_current" in kpis,
           f"value={kpis.get('linear_tvt_share_current')}")
    report("KPIs: channel_count = 340", kpis.get("channel_count") == 340,
           f"value={kpis.get('channel_count')}")

    # Work stats
    work = overview.get("work", {})
    report("Dashboard work.total >= 3", work.get("total", 0) >= 3,
           f"total={work.get('total')}, open={work.get('open')}, in_progress={work.get('in_progress')}")
    report("Dashboard work.in_progress >= 1", work.get("in_progress", 0) >= 1,
           f"in_progress={work.get('in_progress')}")

    # Experiment stats
    exps = overview.get("experiments", {})
    report("Dashboard experiments.total >= 2", exps.get("total", 0) >= 2,
           f"total={exps.get('total')}, running={exps.get('running')}, planned={exps.get('planned')}")
    report("Dashboard experiments.running >= 1", exps.get("running", 0) >= 1,
           f"running={exps.get('running')}")

    # Sentiment
    sent = overview.get("sentiment", {})
    report("Dashboard sentiment.total >= 5", sent.get("total", 0) >= 5,
           f"total={sent.get('total')}, avg_score={sent.get('avg_score')}")

    # Learnings (may be 0 if none created)
    report("Dashboard learnings present", "learnings" in overview,
           f"count={overview.get('learnings')}")

    # Verifications
    verif = overview.get("verifications", {})
    report("Dashboard verifications present", "verifications" in overview,
           f"total={verif.get('total')}")

    # Intel
    intel = overview.get("intel", {})
    report("Dashboard intel section present", "intel" in overview,
           f"signals={intel.get('signals')}, findings={intel.get('findings')}")


# ============================================================
# PHASE 5: Test additional POST endpoints
# ============================================================
print("\n" + "=" * 60)
print("PHASE 5: Testing remaining POST endpoints")
print("=" * 60)

# Strategy: learnings
test_post("POST /api/strategy/learnings",
    "/api/strategy/learnings",
    {"category": "data", "title": "Linear TVT measurement gap",
     "description": "49.8% of linear sessions have empty page_source, likely unattributed deeplinks from OEM integrations",
     "source": "data-verification", "verified": True,
     "tags": ["attribution", "linear", "data-quality"]})

# Strategy: verifications
test_post("POST /api/strategy/verifications",
    "/api/strategy/verifications",
    {"metric_name": "Linear TVT Share", "query_sql": "SELECT ... FROM video_session ...",
     "expected_value": "6.5%", "actual_value": "4.28%",
     "dashboard_source": "internal-dashboard", "match_status": "mismatch",
     "notes": "Strategy doc says 6.5%, actual query returns 4.28% — methodology difference"})

# Strategy: changelog
test_post("POST /api/strategy/changelog",
    "/api/strategy/changelog",
    {"type": "data_update", "title": "Verified channel count at 340",
     "description": "User confirmed Tubi has ~340 linear channels, not 275 from strategy doc",
     "impact": "Updates competitive positioning analysis",
     "evidence": "Manual count + browser scrape", "tags": ["channels", "competitive"]})

# Strategy: generate-prd (requires OPENAI_API_KEY — 200 with key, 500 without)
try:
    r = requests.post(f"{BASE}/api/strategy/generate-prd",
        json={"topic": "EPG Navigation Redesign", "context": "Focus on reducing clicks to switch channels"},
        timeout=60)
    if r.status_code == 200:
        prd_result = r.json()
        report("POST /api/strategy/generate-prd", True, f"status=200")
        report("PRD has markdown content", len(prd_result.get("prd_markdown", "")) > 50,
               f"length={len(prd_result.get('prd_markdown', ''))}")
        report("PRD has id", "id" in prd_result, f"id={prd_result.get('id')}")
    elif r.status_code == 500:
        report("POST /api/strategy/generate-prd (no OpenAI key)", True,
               "500 expected without OPENAI_API_KEY")
    else:
        report("POST /api/strategy/generate-prd", False, f"unexpected status={r.status_code}")
except Exception as e:
    report("POST /api/strategy/generate-prd", False, str(e))

# Strategy: PRD CRUD endpoints
test_get("GET /api/strategy/prds", "/api/strategy/prds", expect_type=list)
# Test GET single PRD (404 for non-existent)
try:
    r = requests.get(f"{BASE}/api/strategy/prds/99999", timeout=10)
    report("GET /api/strategy/prds/99999 returns 404", r.status_code == 404,
           f"status={r.status_code}")
except Exception as e:
    report("GET /api/strategy/prds/99999", False, str(e))
# Test PUT PRD (404 for non-existent)
try:
    r = requests.put(f"{BASE}/api/strategy/prds/99999", json={"status": "approved"}, timeout=10)
    report("PUT /api/strategy/prds/99999 returns 404", r.status_code == 404,
           f"status={r.status_code}")
except Exception as e:
    report("PUT /api/strategy/prds/99999", False, str(e))

# OEM: gracenote
test_post("POST /api/oem/gracenote",
    "/api/oem/gracenote",
    {"tubi_content_id": "ch_ion_mystery", "gracenote_id": "GN12345",
     "content_name": "ION Mystery", "content_type": "linear_channel",
     "match_status": "matched", "notes": "Top 3 channel by TVT"})

# Individual feedback (non-batch)
test_post("POST /api/sentiment/feedback (single)",
    "/api/sentiment/feedback",
    {"source": "slack", "text": "Users love the NFL experience on linear but want better halftime content",
     "sentiment": "mixed", "sentiment_score": 0.2,
     "topics": ["nfl", "live_sports", "content"], "author": "pm-jane"})


# ============================================================
# PHASE 6: Test Sprout Social ingest + trigger endpoints
# ============================================================
print("\n" + "=" * 60)
print("PHASE 6: Testing Sprout Social endpoints")
print("=" * 60)

# POST /api/sentiment/collect/sprout/ingest — data ingestion (no API key needed)
sprout_payload = {
    "messages": [
        {"network": "twitter", "text": "Tubi's live channels are surprisingly good for free TV!",
         "sentiment": "positive", "author": "@streaming_watcher",
         "url": "https://twitter.com/example/status/1",
         "profile_name": "Streaming Watcher", "created_time": "2026-02-14T10:30:00Z",
         "tags": ["tubi", "live_tv", "free"],
         "metrics": {"likes": 42, "retweets": 8, "impressions": 1200}},
        {"network": "instagram", "text": "Why does Tubi buffer so much on the live channels? Fix this please.",
         "sentiment": "negative", "author": "cord_cutter_ig",
         "url": "", "profile_name": "Cord Cutter",
         "created_time": "2026-02-14T14:00:00Z",
         "tags": ["tubi", "buffering", "quality"],
         "metrics": {"likes": 15, "comments": 3}},
        {"network": "facebook", "text": "Just discovered Tubi has a linear TV guide. Reminds me of the old cable days but free.",
         "sentiment": "positive", "author": "fb_user_123",
         "url": "https://facebook.com/post/example",
         "profile_name": "Free TV Fan", "created_time": "2026-02-14T18:45:00Z",
         "tags": ["tubi", "epg", "nostalgia", "free"],
         "metrics": {"likes": 87, "shares": 12, "comments": 5}},
    ],
    "topic": "Tubi Linear TV Mentions",
    "date_range": "2026-02-01 to 2026-02-15",
}

sprout_result = test_post("POST /api/sentiment/collect/sprout/ingest (3 messages)",
    "/api/sentiment/collect/sprout/ingest",
    sprout_payload,
    expect_key="count")
if sprout_result:
    report("Sprout ingest count = 3", sprout_result.get("count") == 3,
           f"expected 3, got {sprout_result.get('count')}")
    report("Sprout ingest returns ids", len(sprout_result.get("ids", [])) == 3,
           f"ids={sprout_result.get('ids')}")
    report("Sprout ingest returns topic", sprout_result.get("topic") == "Tubi Linear TV Mentions",
           f"topic={sprout_result.get('topic')}")

# POST /api/sentiment/collect/sprout/ingest — empty batch
empty_sprout = test_post("POST /api/sentiment/collect/sprout/ingest (empty batch)",
    "/api/sentiment/collect/sprout/ingest",
    {"messages": []},
    expect_key="count")
if empty_sprout:
    report("Sprout empty batch count = 0", empty_sprout.get("count") == 0,
           f"count={empty_sprout.get('count')}")

# POST /api/sentiment/collect/sprout/ingest — single message, minimal fields
minimal_sprout = test_post("POST /api/sentiment/collect/sprout/ingest (minimal fields)",
    "/api/sentiment/collect/sprout/ingest",
    {"messages": [{"text": "Tubi linear is neat"}]},
    expect_key="count")
if minimal_sprout:
    report("Sprout minimal msg count = 1", minimal_sprout.get("count") == 1,
           f"count={minimal_sprout.get('count')}")

# POST /api/sentiment/collect/sprout — API trigger (requires API key, expect graceful error)
trigger_result = test_post("POST /api/sentiment/collect/sprout (trigger, no API key)",
    "/api/sentiment/collect/sprout",
    {})
if trigger_result:
    report("Sprout trigger returns status", "status" in trigger_result,
           f"keys={list(trigger_result.keys())}")

# Verify sprout data appears in sentiment feed
sprout_feed = test_get("GET /api/sentiment/feed?source=sprout:twitter",
    "/api/sentiment/feed?source=sprout:twitter", expect_type=list)
if sprout_feed:
    report("Sprout twitter items in feed", len(sprout_feed) >= 1,
           f"found {len(sprout_feed)} sprout:twitter items")

# Verify sprout data in summary breakdown
sprout_summary = test_get("GET /api/sentiment/summary (after sprout)",
    "/api/sentiment/summary")
if sprout_summary:
    by_source = sprout_summary.get("by_source", {})
    has_sprout = any(k.startswith("sprout:") for k in by_source) or "sprout" in by_source
    report("Sprout source in summary breakdown", has_sprout,
           f"sources={list(by_source.keys())}")


# ============================================================
# PHASE 7: Test previously untested endpoints
# ============================================================
print("\n" + "=" * 60)
print("PHASE 7: Testing previously untested endpoints")
print("=" * 60)

# POST /api/intel/scan — trigger a scan (background, won't actually run pipeline)
scan_result = test_post("POST /api/intel/scan (trigger scan)",
    "/api/intel/scan",
    {},
    expect_key="status")
if scan_result:
    report("Scan returns status=scan_started",
           scan_result.get("status") == "scan_started",
           f"status={scan_result.get('status')}")

# POST /api/intel/scan with options
scan_opts = test_post("POST /api/intel/scan?skip_analysis=true&competitor=pluto_tv",
    "/api/intel/scan?skip_analysis=true&competitor=pluto_tv",
    {},
    expect_key="status")
if scan_opts:
    args = scan_opts.get("args", [])
    report("Scan passes skip_analysis arg", "--skip-analysis" in args,
           f"args={args}")
    report("Scan passes competitor arg", "pluto_tv" in args,
           f"args={args}")

# GET /api/intel/run/{scan_date}/{run_id} — test with known run if available
runs = test_get("GET /api/intel/runs (for run lookup)", "/api/intel/runs", expect_type=list)
if runs and len(runs) > 0:
    run_date = runs[0]["date"]
    run_id = runs[0]["run_id"]
    run_data = test_get(f"GET /api/intel/run/{run_date}/{run_id}",
        f"/api/intel/run/{run_date}/{run_id}")
    if run_data:
        report("Run data has scan_date", run_data.get("scan_date") == run_date,
               f"scan_date={run_data.get('scan_date')}")
        report("Run data has run_id", run_data.get("run_id") == run_id,
               f"run_id={run_data.get('run_id')}")
else:
    # No runs available — test with a fake date/id, expect empty result
    run_data = test_get("GET /api/intel/run (no data)", "/api/intel/run/1970-01-01/fake_run")
    report("Run with invalid id returns data dict", isinstance(run_data, dict),
           f"type={type(run_data).__name__}")

# POST /api/data/query — SQL query (will fail without Databricks, but endpoint should respond)
query_result = test_post("POST /api/data/query (Databricks SQL)",
    "/api/data/query",
    {"sql": "SELECT 1 AS test_col", "limit": 10})
if query_result:
    # May return rows or error — either is a valid response from the endpoint
    has_response = "rows" in query_result or "error" in query_result
    report("Data query returns rows or error", has_response,
           f"keys={list(query_result.keys())}")

# POST /api/data/named — named query
named_result = test_post("POST /api/data/named (named query)",
    "/api/data/named",
    {"name": "nonexistent_query", "days": 7})
if named_result:
    # Should return error for unknown query with available list
    has_response = "error" in named_result or "rows" in named_result
    report("Named query returns error or rows", has_response,
           f"keys={list(named_result.keys())}")

# POST /api/data/named — test with bad query name returns available list
if named_result and "available" in named_result:
    report("Named query error lists available queries",
           len(named_result.get("available", [])) > 0,
           f"available={named_result.get('available', [])[:5]}")


# ============================================================
# PHASE 8: Test new intel endpoints (history, diff, ingest)
# ============================================================
print("\n" + "=" * 60)
print("PHASE 8: Testing intel history, diff, and ingest endpoints")
print("=" * 60)

# GET /api/intel/history — list all past scans with counts
history = test_get("GET /api/intel/history", "/api/intel/history", expect_type=list)
if history:
    report("Intel history has entries", len(history) > 0, f"found {len(history)} scan runs")
    first = history[0]
    report("History entry has date", "date" in first, f"keys={list(first.keys())}")
    report("History entry has article_count", "article_count" in first,
           f"article_count={first.get('article_count')}")
    report("History entry has threat_count", "threat_count" in first,
           f"threat_count={first.get('threat_count')}")
    report("History entry has opportunity_count", "opportunity_count" in first,
           f"opportunity_count={first.get('opportunity_count')}")

# GET /api/intel/diff — compare latest two scans
diff = test_get("GET /api/intel/diff", "/api/intel/diff")
if diff:
    if "error" not in diff:
        report("Diff has latest/previous refs", "latest" in diff and "previous" in diff,
               f"latest={diff.get('latest', {}).get('run_id')}, prev={diff.get('previous', {}).get('run_id')}")
        report("Diff has summary", "summary" in diff, f"summary={diff.get('summary')}")
        report("Diff has new_intel list", isinstance(diff.get("new_intel"), list),
               f"new_intel_count={len(diff.get('new_intel', []))}")
        report("Diff has new_threats list", isinstance(diff.get("new_threats"), list),
               f"new_threats_count={len(diff.get('new_threats', []))}")
    else:
        report("Diff returns error (need 2+ runs)", "runs_available" in diff,
               f"error={diff.get('error')}")

# POST /api/intel/ingest — manually ingest a scan run
if history and len(history) > 0:
    ingest_date = history[0]["date"]
    ingest_run_id = history[0]["run_id"]
    ingest_result = test_post("POST /api/intel/ingest (manual)",
        f"/api/intel/ingest/{ingest_date}/{ingest_run_id}", {})
    if ingest_result:
        report("Ingest returned status", ingest_result.get("status") == "ingested",
               f"threats={ingest_result.get('threats')}, opps={ingest_result.get('opportunities')}")
        report("Ingest created work items", isinstance(ingest_result.get("work_item_ids"), list),
               f"count={len(ingest_result.get('work_item_ids', []))}")

    # Verify work items were created
    work_items = test_get("GET /api/strategy/work?type=threat", "/api/strategy/work?type=threat", expect_type=list)
    if work_items:
        ci_threats = [w for w in work_items if "ci_scan" in (w.get("tags") or "")]
        report("Threat work items created from scan", len(ci_threats) > 0,
               f"found {len(ci_threats)} threat work items with ci_scan tag")

    work_items_opp = test_get("GET /api/strategy/work?type=opportunity", "/api/strategy/work?type=opportunity", expect_type=list)
    if work_items_opp:
        ci_opps = [w for w in work_items_opp if "ci_scan" in (w.get("tags") or "")]
        report("Opportunity work items created from scan", len(ci_opps) > 0,
               f"found {len(ci_opps)} opportunity work items with ci_scan tag")


# ============================================================
# PHASE 9: Knowledge engine endpoints
# ============================================================
print("\n" + "=" * 60)
print("PHASE 9: Testing knowledge engine endpoints")
print("=" * 60)

# GET endpoints (should work without OpenAI)
test_get("GET /api/knowledge/reviews", "/api/knowledge/reviews", expect_type=list)
test_get("GET /api/knowledge/ideas", "/api/knowledge/ideas", expect_type=list)
test_get("GET /api/knowledge/insights", "/api/knowledge/insights", expect_type=list)

# POST /api/knowledge/review-prd — requires OpenAI, expect 200 or 503
print("\n--- Knowledge: PRD Review (requires OpenAI) ---")
try:
    r = requests.post(f"{BASE}/api/knowledge/review-prd",
        json={"prd_content": "# EPG Redesign\n\nRedesign the EPG for better navigation.\n\n## Success Metrics\n- Increase linear TVT by 5%"},
        timeout=60)
    if r.status_code == 200:
        data = r.json()
        report("POST review-prd returns score", "score" in data.get("feedback", {}),
               f"score={data.get('score')}, id={data.get('id')}")
    elif r.status_code == 503:
        report("POST review-prd returns 503 (no OpenAI key)", True, "expected without API key")
    else:
        report("POST review-prd unexpected status", False, f"status={r.status_code}")
except Exception as e:
    report("POST review-prd", False, str(e))

# POST /api/knowledge/review-prd — missing content
try:
    r = requests.post(f"{BASE}/api/knowledge/review-prd", json={}, timeout=10)
    report("POST review-prd empty returns 400", r.status_code == 400,
           f"status={r.status_code}")
except Exception as e:
    report("POST review-prd empty", False, str(e))

# POST /api/knowledge/generate-ideas — requires OpenAI
print("\n--- Knowledge: Idea Generator (requires OpenAI) ---")
try:
    r = requests.post(f"{BASE}/api/knowledge/generate-ideas",
        json={"area": "epg"}, timeout=60)
    if r.status_code == 200:
        data = r.json()
        report("POST generate-ideas returns ideas", data.get("count", 0) > 0,
               f"count={data.get('count')}, gen_id={data.get('generation_id')}")
    elif r.status_code == 503:
        report("POST generate-ideas returns 503 (no OpenAI key)", True, "expected without API key")
    else:
        report("POST generate-ideas unexpected status", False, f"status={r.status_code}")
except Exception as e:
    report("POST generate-ideas", False, str(e))

# GET /api/knowledge/ideas — verify ideas stored
ideas_data = test_get("GET /api/knowledge/ideas (after generate)", "/api/knowledge/ideas", expect_type=list)

# GET /api/knowledge/ideas?area=epg — filter by area
test_get("GET /api/knowledge/ideas?area=epg", "/api/knowledge/ideas?area=epg", expect_type=list)

# PUT /api/knowledge/ideas/{id}/vote — vote on an idea
if ideas_data and len(ideas_data) > 0:
    idea_id = ideas_data[0]["id"]
    vote_result = test_put(f"PUT /api/knowledge/ideas/{idea_id}/vote (upvote)",
        f"/api/knowledge/ideas/{idea_id}/vote?direction=1", {})
    if vote_result:
        report("Vote returns new votes count", "votes" in vote_result,
               f"votes={vote_result.get('votes')}")

# POST /api/knowledge/synthesize — requires OpenAI
print("\n--- Knowledge: Insight Synthesizer (requires OpenAI) ---")
try:
    r = requests.post(f"{BASE}/api/knowledge/synthesize",
        json={"question": "Why is linear TVT declining?"}, timeout=60)
    if r.status_code == 200:
        data = r.json()
        report("POST synthesize returns answer", bool(data.get("answer_md")),
               f"id={data.get('id')}, answer_length={len(data.get('answer_md', ''))}")
    elif r.status_code == 503:
        report("POST synthesize returns 503 (no OpenAI key)", True, "expected without API key")
    else:
        report("POST synthesize unexpected status", False, f"status={r.status_code}")
except Exception as e:
    report("POST synthesize", False, str(e))

# GET /api/knowledge/insights — list insights
test_get("GET /api/knowledge/insights (after synthesize)", "/api/knowledge/insights", expect_type=list)

# GET /api/knowledge/digest — requires OpenAI
print("\n--- Knowledge: Weekly Digest (requires OpenAI) ---")
try:
    r = requests.get(f"{BASE}/api/knowledge/digest", timeout=60)
    if r.status_code == 200:
        data = r.json()
        report("GET digest returns markdown", bool(data.get("digest_md")),
               f"period={data.get('period')}, stats={data.get('stats')}")
    elif r.status_code == 503:
        report("GET digest returns 503 (no OpenAI key)", True, "expected without API key")
    else:
        report("GET digest unexpected status", False, f"status={r.status_code}")
except Exception as e:
    report("GET digest", False, str(e))


# ============================================================
# PHASE 10: Test query parameter filters and edge cases
# ============================================================
print("\n" + "=" * 60)
print("PHASE 10: Testing query parameter filters and edge cases")
print("=" * 60)

# Sentiment feed with source filter
test_get("GET /api/sentiment/feed?source=reddit",
    "/api/sentiment/feed?source=reddit", expect_type=list)

# Sentiment feed with sentiment filter
test_get("GET /api/sentiment/feed?sentiment=negative",
    "/api/sentiment/feed?sentiment=negative", expect_type=list)

# Sentiment feed with limit
limited = test_get("GET /api/sentiment/feed?limit=2",
    "/api/sentiment/feed?limit=2", expect_type=list)
if limited:
    report("Feed limit=2 returns <=2", len(limited) <= 2, f"got {len(limited)}")

# Work items with status filter
test_get("GET /api/strategy/work?status=open",
    "/api/strategy/work?status=open", expect_type=list)

# Work items with type filter
test_get("GET /api/strategy/work?type=task",
    "/api/strategy/work?type=task", expect_type=list)

# Experiments with status filter
test_get("GET /api/features/experiments?status=running",
    "/api/features/experiments?status=running", expect_type=list)

# OEM snapshots with platform filter
test_get("GET /api/oem/snapshots?platform=roku",
    "/api/oem/snapshots?platform=roku", expect_type=list)

# Learnings with category filter
test_get("GET /api/strategy/learnings?category=data_issue",
    "/api/strategy/learnings?category=data_issue", expect_type=list)

# Verifications with status filter
test_get("GET /api/strategy/verifications?status=mismatch",
    "/api/strategy/verifications?status=mismatch", expect_type=list)

# Changelog with type filter
test_get("GET /api/strategy/changelog?type=decision",
    "/api/strategy/changelog?type=decision", expect_type=list)

# Search with limit
test_get("GET /api/search/?q=linear&limit=3",
    "/api/search/?q=linear&limit=3", expect_key="sources")

# Gracenote with status filter
test_get("GET /api/oem/gracenote?status=mapped",
    "/api/oem/gracenote?status=mapped", expect_type=list)


# ============================================================
# PHASE 11: Verify non-existent endpoints return 404
# ============================================================
print("\n" + "=" * 60)
print("PHASE 11: Verifying non-existent endpoint handling")
print("=" * 60)

def test_404(name, path):
    """Test that a path returns 404."""
    try:
        r = requests.get(f"{BASE}{path}", timeout=10)
        report(name, r.status_code == 404, f"status={r.status_code}")
    except Exception as e:
        report(name, False, str(e))

test_404("GET /api/ask returns 404", "/api/ask")
test_404("GET /api/insights returns 404", "/api/insights")
test_404("GET /api/nonexistent returns 404", "/api/nonexistent")


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print(f"FINAL RESULTS: {PASS} PASS / {FAIL} FAIL / {PASS + FAIL} TOTAL")
print("=" * 60)

if FAIL > 0:
    print("\nFailed tests:")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  ✗ {name}: {detail}")

sys.exit(0 if FAIL == 0 else 1)
