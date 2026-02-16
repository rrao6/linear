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

# Strategy: generate-prd
test_post("POST /api/strategy/generate-prd",
    "/api/strategy/generate-prd",
    {"title": "EPG Redesign PRD", "problem": "Current EPG is slow and hard to navigate",
     "hypothesis": "A modern horizontal-scroll EPG will increase linear TVT by 5%"},
    expect_key="prd_markdown")

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
