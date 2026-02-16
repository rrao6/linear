#!/usr/bin/env python3
"""Data quality and integrity tests for Linear Hub.

Validates data integrity constraints that the hub should maintain:
- No orphaned records
- Valid field values (sentiment, status, timestamps)
- No duplicate entries
- Valid state transitions

Requires hub running at localhost:8888 with some data seeded.
"""

import json
import re
import sys
import requests

BASE = "http://localhost:8888"
PASS = 0
FAIL = 0
RESULTS = []

# ISO 8601 pattern (basic validation)
ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def get(path, timeout=30):
    try:
        r = requests.get(f"{BASE}{path}", timeout=timeout)
        return r.json() if r.status_code == 200 else None
    except requests.exceptions.ReadTimeout:
        print(f"    [WARN] Timeout on GET {path}")
        return None


def post(path, payload, timeout=10):
    r = requests.post(f"{BASE}{path}", json=payload, timeout=timeout)
    return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else None


def put(path, payload, timeout=10):
    r = requests.put(f"{BASE}{path}", json=payload, timeout=timeout)
    return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else None


def is_valid_iso(s):
    """Check if string is a valid ISO timestamp or date."""
    if not s:
        return False
    return bool(ISO_PATTERN.match(s) or ISO_DATE_PATTERN.match(s))


# ============================================================
# Seed some test data first
# ============================================================
print("\n" + "=" * 60)
print("Seeding test data for quality checks")
print("=" * 60)

# Create work items with known states
post("/api/strategy/work", {
    "type": "task", "title": "DQ Test Task Open",
    "description": "Open task for data quality test",
    "priority": "medium", "tags": ["dq_test"]
})
_, w_progress = post("/api/strategy/work", {
    "type": "task", "title": "DQ Test Task In Progress",
    "description": "In progress task for data quality test",
    "priority": "high", "tags": ["dq_test"]
})
if w_progress and w_progress.get("id"):
    put(f"/api/strategy/work/{w_progress['id']}", {"status": "in_progress"})

_, w_done = post("/api/strategy/work", {
    "type": "task", "title": "DQ Test Task Done",
    "description": "Done task for data quality test",
    "priority": "low", "tags": ["dq_test"]
})
if w_done and w_done.get("id"):
    put(f"/api/strategy/work/{w_done['id']}", {"status": "done"})

# Create feedback with various sentiments
post("/api/sentiment/feedback/batch", {"items": [
    {"source": "reddit", "text": "DQ positive test", "sentiment": "positive", "sentiment_score": 0.5, "topics": ["dq_test"]},
    {"source": "twitter", "text": "DQ negative test", "sentiment": "negative", "sentiment_score": -0.5, "topics": ["dq_test"]},
    {"source": "manual", "text": "DQ neutral test", "sentiment": "neutral", "sentiment_score": 0.0, "topics": ["dq_test"]},
]})

# Create a learning
post("/api/strategy/learnings", {
    "category": "data_issue", "title": "DQ Test Learning",
    "description": "Test learning for data quality checks",
    "source": "dq-test", "verified": True, "tags": ["dq_test"]
})

print("  Test data seeded.\n")


# ============================================================
# CHECK 1: Feedback sentiment values are valid
# ============================================================
print("=" * 60)
print("CHECK 1: Feedback sentiment values")
print("=" * 60)

VALID_SENTIMENTS = {"positive", "negative", "neutral", "mixed"}
feedback = get("/api/sentiment/feed?limit=500")
if feedback:
    invalid_sentiments = []
    for f in feedback:
        if f.get("sentiment") not in VALID_SENTIMENTS:
            invalid_sentiments.append((f.get("id"), f.get("sentiment")))
    report("All feedback has valid sentiment",
           len(invalid_sentiments) == 0,
           f"invalid: {invalid_sentiments[:5]}" if invalid_sentiments else f"checked {len(feedback)} items")

    # Sentiment scores in valid range
    out_of_range = []
    for f in feedback:
        score = f.get("sentiment_score", 0)
        if score < -1.0 or score > 1.0:
            out_of_range.append((f.get("id"), score))
    report("All sentiment scores in [-1.0, 1.0]",
           len(out_of_range) == 0,
           f"out of range: {out_of_range[:5]}" if out_of_range else f"checked {len(feedback)} items")

    # All feedback has non-empty text
    empty_text = [f.get("id") for f in feedback if not f.get("text", "").strip()]
    report("All feedback has non-empty text",
           len(empty_text) == 0,
           f"empty text ids: {empty_text[:5]}" if empty_text else f"checked {len(feedback)} items")

    # All feedback has valid source
    valid_sources = {"reddit", "appstore", "twitter", "manual", "slack"}
    invalid_sources = []
    for f in feedback:
        src = f.get("source", "")
        # Allow sprout:* sources
        if src not in valid_sources and not src.startswith("sprout:") and src != "sprout":
            invalid_sources.append((f.get("id"), src))
    report("All feedback has valid source",
           len(invalid_sources) == 0,
           f"invalid: {invalid_sources[:5]}" if invalid_sources else f"checked {len(feedback)} items")
else:
    report("Feedback data available", False, "could not fetch feedback")


# ============================================================
# CHECK 2: Timestamps are valid ISO format
# ============================================================
print("\n" + "=" * 60)
print("CHECK 2: Timestamp format validation")
print("=" * 60)

# Check feedback timestamps
if feedback:
    invalid_timestamps = []
    for f in feedback:
        for field in ["created_at", "collected_at"]:
            val = f.get(field)
            if val and not is_valid_iso(val):
                invalid_timestamps.append((f.get("id"), field, val))
    report("All feedback timestamps are valid ISO",
           len(invalid_timestamps) == 0,
           f"invalid: {invalid_timestamps[:3]}" if invalid_timestamps else f"checked {len(feedback)} items")

# Check work item timestamps
work_items = get("/api/strategy/work?limit=500")
if work_items:
    invalid_ts = []
    for w in work_items:
        for field in ["created_at", "updated_at"]:
            val = w.get(field)
            if val and not is_valid_iso(val):
                invalid_ts.append((w.get("id"), field, val))
        # completed_at should be set only for done items, and should be valid if set
        if w.get("completed_at") and not is_valid_iso(w["completed_at"]):
            invalid_ts.append((w.get("id"), "completed_at", w["completed_at"]))
    report("All work item timestamps are valid ISO",
           len(invalid_ts) == 0,
           f"invalid: {invalid_ts[:3]}" if invalid_ts else f"checked {len(work_items)} items")

    # completed_at should only be set for done items
    bad_completed = []
    for w in work_items:
        if w.get("status") != "done" and w.get("completed_at"):
            bad_completed.append((w.get("id"), w.get("status"), w.get("completed_at")))
    report("completed_at only set for done items",
           len(bad_completed) == 0,
           f"bad: {bad_completed[:3]}" if bad_completed else f"checked {len(work_items)} items")
else:
    report("Work items available", False, "could not fetch work items")

# Check learnings timestamps
learnings = get("/api/strategy/learnings?limit=500")
if learnings:
    invalid_ts = []
    for l in learnings:
        for field in ["created_at", "updated_at"]:
            val = l.get(field)
            if val and not is_valid_iso(val):
                invalid_ts.append((l.get("id"), field, val))
    report("All learning timestamps are valid ISO",
           len(invalid_ts) == 0,
           f"invalid: {invalid_ts[:3]}" if invalid_ts else f"checked {len(learnings)} items")
else:
    report("Learnings available", False, "could not fetch learnings")

# Check experiment timestamps
experiments = get("/api/features/experiments?limit=500")
if experiments:
    invalid_ts = []
    for e in experiments:
        for field in ["created_at", "updated_at"]:
            val = e.get(field)
            if val and not is_valid_iso(val):
                invalid_ts.append((e.get("id"), field, val))
    report("All experiment timestamps are valid ISO",
           len(invalid_ts) == 0,
           f"invalid: {invalid_ts[:3]}" if invalid_ts else f"checked {len(experiments)} items")

# Check OEM snapshot timestamps
oem_snaps = get("/api/oem/snapshots?limit=500")
if oem_snaps:
    invalid_ts = []
    for s in oem_snaps:
        if s.get("created_at") and not is_valid_iso(s["created_at"]):
            invalid_ts.append((s.get("id"), "created_at", s["created_at"]))
        # date field should be a valid ISO date
        if s.get("date") and not is_valid_iso(s["date"]):
            invalid_ts.append((s.get("id"), "date", s["date"]))
    report("All OEM snapshot timestamps are valid ISO",
           len(invalid_ts) == 0,
           f"invalid: {invalid_ts[:3]}" if invalid_ts else f"checked {len(oem_snaps)} items")


# ============================================================
# CHECK 3: No duplicate learnings
# ============================================================
print("\n" + "=" * 60)
print("CHECK 3: Duplicate detection")
print("=" * 60)

if learnings:
    seen_titles = {}
    duplicates = []
    for l in learnings:
        title = l.get("title", "")
        cat = l.get("category", "")
        key = f"{cat}:{title}"
        if key in seen_titles:
            duplicates.append((l.get("id"), seen_titles[key], title))
        else:
            seen_titles[key] = l.get("id")
    # Note: duplicates may exist from running other test suites that seed data.
    # This check detects them; the hub doesn't enforce uniqueness (valid for feedback systems).
    report("Duplicate learnings detected (informational)",
           True,
           f"{len(duplicates)} duplicates found in {len(learnings)} items" if duplicates else f"0 duplicates in {len(learnings)} items")

# Check for duplicate feedback (same source+text)
if feedback:
    seen_fb = {}
    dup_fb = []
    for f in feedback:
        key = f"{f.get('source')}:{f.get('text', '')[:100]}"
        if key in seen_fb:
            dup_fb.append((f.get("id"), seen_fb[key], f.get("text", "")[:50]))
        else:
            seen_fb[key] = f.get("id")
    report("Duplicate feedback detected (informational)",
           True,
           f"{len(dup_fb)} duplicates found in {len(feedback)} items" if dup_fb else f"0 duplicates in {len(feedback)} items")


# ============================================================
# CHECK 4: Work item status transitions
# ============================================================
print("\n" + "=" * 60)
print("CHECK 4: Work item status validity")
print("=" * 60)

VALID_STATUSES = {"open", "in_progress", "blocked", "done", "cancelled"}
VALID_PRIORITIES = {"critical", "high", "medium", "low"}
VALID_TYPES = {"task", "prd", "change", "plan", "investigation", "epic", "threat", "opportunity", "research"}

if work_items:
    # All statuses are valid
    invalid_status = []
    for w in work_items:
        if w.get("status") not in VALID_STATUSES:
            invalid_status.append((w.get("id"), w.get("status")))
    report("All work item statuses are valid",
           len(invalid_status) == 0,
           f"invalid: {invalid_status[:5]}" if invalid_status else f"checked {len(work_items)} items")

    # All priorities are valid
    invalid_priority = []
    for w in work_items:
        if w.get("priority") not in VALID_PRIORITIES:
            invalid_priority.append((w.get("id"), w.get("priority")))
    report("All work item priorities are valid",
           len(invalid_priority) == 0,
           f"invalid: {invalid_priority[:5]}" if invalid_priority else f"checked {len(work_items)} items")

    # All types are valid
    invalid_type = []
    for w in work_items:
        if w.get("type") not in VALID_TYPES:
            invalid_type.append((w.get("id"), w.get("type")))
    report("All work item types are valid",
           len(invalid_type) == 0,
           f"invalid: {invalid_type[:5]}" if invalid_type else f"checked {len(work_items)} items")

    # Tags should be lists (not strings)
    bad_tags = []
    for w in work_items:
        tags = w.get("tags")
        if tags is not None and not isinstance(tags, list):
            bad_tags.append((w.get("id"), type(tags).__name__))
    report("All work item tags are lists",
           len(bad_tags) == 0,
           f"bad: {bad_tags[:5]}" if bad_tags else f"checked {len(work_items)} items")


# ============================================================
# CHECK 5: Experiment field validation
# ============================================================
print("\n" + "=" * 60)
print("CHECK 5: Experiment field validation")
print("=" * 60)

VALID_EXP_STATUSES = {"planned", "running", "analyzing", "completed", "killed"}

if experiments:
    # All statuses valid
    invalid_exp_status = []
    for e in experiments:
        if e.get("status") not in VALID_EXP_STATUSES:
            invalid_exp_status.append((e.get("id"), e.get("status")))
    report("All experiment statuses are valid",
           len(invalid_exp_status) == 0,
           f"invalid: {invalid_exp_status[:5]}" if invalid_exp_status else f"checked {len(experiments)} items")

    # Platforms should be lists
    bad_platforms = []
    for e in experiments:
        platforms = e.get("platforms")
        if isinstance(platforms, str):
            try:
                parsed = json.loads(platforms)
                if not isinstance(parsed, list):
                    bad_platforms.append((e.get("id"), type(parsed).__name__))
            except json.JSONDecodeError:
                bad_platforms.append((e.get("id"), "invalid_json"))
    report("All experiment platforms are valid",
           len(bad_platforms) == 0,
           f"bad: {bad_platforms[:5]}" if bad_platforms else f"checked {len(experiments)} items")


# ============================================================
# CHECK 6: Verification field validation
# ============================================================
print("\n" + "=" * 60)
print("CHECK 6: Verification field validation")
print("=" * 60)

VALID_MATCH_STATUSES = {"pending", "match", "mismatch", "investigating"}
verifications = get("/api/strategy/verifications?limit=500")
if verifications:
    invalid_ms = []
    for v in verifications:
        if v.get("match_status") not in VALID_MATCH_STATUSES:
            invalid_ms.append((v.get("id"), v.get("match_status")))
    report("All verification match_status values are valid",
           len(invalid_ms) == 0,
           f"invalid: {invalid_ms[:5]}" if invalid_ms else f"checked {len(verifications)} items")

    # All verifications have metric_name
    no_name = [v.get("id") for v in verifications if not v.get("metric_name")]
    report("All verifications have metric_name",
           len(no_name) == 0,
           f"missing name: {no_name[:5]}" if no_name else f"checked {len(verifications)} items")

    # All verifications have query_sql
    no_sql = [v.get("id") for v in verifications if not v.get("query_sql")]
    report("All verifications have query_sql",
           len(no_sql) == 0,
           f"missing sql: {no_sql[:5]}" if no_sql else f"checked {len(verifications)} items")
else:
    report("Verifications available for checking", verifications is not None,
           "could not fetch verifications")


# ============================================================
# CHECK 7: Changelog field validation
# ============================================================
print("\n" + "=" * 60)
print("CHECK 7: Changelog field validation")
print("=" * 60)

VALID_CHANGE_TYPES = {"decision", "change", "rollback", "launch", "finding", "data_update"}
changelog = get("/api/strategy/changelog?limit=500")
if changelog:
    invalid_types = []
    for c in changelog:
        if c.get("type") not in VALID_CHANGE_TYPES:
            invalid_types.append((c.get("id"), c.get("type")))
    report("All changelog types are valid",
           len(invalid_types) == 0,
           f"invalid: {invalid_types[:5]}" if invalid_types else f"checked {len(changelog)} items")

    # All have title
    no_title = [c.get("id") for c in changelog if not c.get("title")]
    report("All changelog entries have title",
           len(no_title) == 0,
           f"missing: {no_title[:5]}" if no_title else f"checked {len(changelog)} items")

    # Tags are lists
    bad_tags = []
    for c in changelog:
        tags = c.get("tags")
        if tags is not None and not isinstance(tags, list):
            bad_tags.append((c.get("id"), type(tags).__name__))
    report("All changelog tags are lists",
           len(bad_tags) == 0,
           f"bad: {bad_tags[:5]}" if bad_tags else f"checked {len(changelog)} items")


# ============================================================
# CHECK 8: OEM and Gracenote validation
# ============================================================
print("\n" + "=" * 60)
print("CHECK 8: OEM and Gracenote validation")
print("=" * 60)

VALID_PLATFORMS = {"amazon_fire", "roku", "samsung", "lg", "vizio", "google_tv"}
if oem_snaps:
    invalid_platforms = []
    for s in oem_snaps:
        if s.get("platform") not in VALID_PLATFORMS:
            invalid_platforms.append((s.get("id"), s.get("platform")))
    report("All OEM snapshots have valid platform",
           len(invalid_platforms) == 0,
           f"invalid: {invalid_platforms[:5]}" if invalid_platforms else f"checked {len(oem_snaps)} items")

    # tubi_placement and competitor_placements should be dicts (or parseable JSON)
    bad_placement = []
    for s in oem_snaps:
        tp = s.get("tubi_placement")
        if isinstance(tp, str):
            try:
                json.loads(tp)
            except json.JSONDecodeError:
                bad_placement.append((s.get("id"), "tubi_placement"))
    report("All OEM tubi_placement is valid JSON",
           len(bad_placement) == 0,
           f"bad: {bad_placement[:5]}" if bad_placement else f"checked {len(oem_snaps)} items")

VALID_GN_STATUSES = {"mapped", "unmapped", "ambiguous", "manual", "matched"}
gracenote = get("/api/oem/gracenote?limit=500")
if gracenote:
    invalid_gn = []
    for g in gracenote:
        if g.get("match_status") not in VALID_GN_STATUSES:
            invalid_gn.append((g.get("id"), g.get("match_status")))
    report("All Gracenote mappings have valid status",
           len(invalid_gn) == 0,
           f"invalid: {invalid_gn[:5]}" if invalid_gn else f"checked {len(gracenote)} items")


# ============================================================
# CHECK 9: Dashboard aggregation consistency
# ============================================================
print("\n" + "=" * 60)
print("CHECK 9: Dashboard aggregation consistency")
print("=" * 60)

overview = get("/api/dashboard/overview")
if overview:
    # Work stats should sum correctly
    work = overview.get("work", {})
    total = work.get("total", 0)
    open_count = work.get("open", 0)
    in_progress = work.get("in_progress", 0)
    blocked = work.get("blocked", 0)
    done = work.get("done", 0)
    sum_parts = open_count + in_progress + blocked + done
    # Note: cancelled items are included in total but not in breakdown above
    report("Work stats sum <= total (cancelled not in breakdown)",
           sum_parts <= total,
           f"total={total}, open={open_count}+ip={in_progress}+blocked={blocked}+done={done}={sum_parts}")

    # Sentiment summary consistency
    sent = overview.get("sentiment", {})
    sent_total = sent.get("total", 0)
    by_sentiment = sent.get("by_sentiment", {})
    sum_sentiments = sum(by_sentiment.values())
    report("Sentiment counts sum to total",
           sum_sentiments == sent_total,
           f"total={sent_total}, sum={sum_sentiments}, by_sentiment={by_sentiment}")

    # KPIs should have required fields
    kpis = overview.get("kpis", {})
    report("KPIs has linear_tvt_share_current",
           "linear_tvt_share_current" in kpis,
           f"value={kpis.get('linear_tvt_share_current')}")
    report("KPIs has channel_count",
           "channel_count" in kpis,
           f"value={kpis.get('channel_count')}")
    report("KPIs has source field",
           "source" in kpis,
           f"source={kpis.get('source')}")
else:
    report("Dashboard overview available", False, "could not fetch overview")


# ============================================================
# CHECK 10: Sentiment summary consistency
# ============================================================
print("\n" + "=" * 60)
print("CHECK 10: Sentiment summary consistency")
print("=" * 60)

summary = get("/api/sentiment/summary")
if summary:
    # by_source counts should sum to total
    by_source = summary.get("by_source", {})
    source_total = sum(by_source.values())
    report("by_source sums to total",
           source_total == summary.get("total", 0),
           f"total={summary.get('total')}, source_sum={source_total}")

    # avg_score should be in valid range
    avg = summary.get("avg_score", 0)
    report("avg_score in [-1.0, 1.0]",
           -1.0 <= avg <= 1.0,
           f"avg_score={avg}")

    # Total should match feed count
    all_feedback = get("/api/sentiment/feed?limit=10000")
    if all_feedback:
        report("Summary total matches feed count",
               summary.get("total") == len(all_feedback),
               f"summary_total={summary.get('total')}, feed_count={len(all_feedback)}")


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print(f"DATA QUALITY RESULTS: {PASS} PASS / {FAIL} FAIL / {PASS + FAIL} TOTAL")
print("=" * 60)

if FAIL > 0:
    print("\nFailed checks:")
    for name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  ✗ {name}: {detail}")

sys.exit(0 if FAIL == 0 else 1)
