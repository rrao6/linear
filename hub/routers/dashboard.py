"""Dashboard overview: KPIs, goal tracking, system health, AI summary.

Queries live Databricks data for linear KPIs and caches results in SQLite
with a 1-hour TTL so we don't hammer the warehouse on every page load.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime

from fastapi import APIRouter

from ..config import SCANS_DIR, INTEL_DIR, ANALYSIS_DIR, PLUGINS_DIR, OPENAI_API_KEY
from .. import db

# Add linear-data plugin to path
sys.path.insert(0, str(PLUGINS_DIR / "linear-data"))

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL queries for live KPIs
# ---------------------------------------------------------------------------

# (1) Linear TVT share — last 30 days
SQL_LINEAR_TVT_SHARE = """
SELECT
    ROUND(
        SUM(CASE WHEN ci.content_type = 'LINEAR' THEN vs.tvt_millisec ELSE 0 END)
        * 100.0 / SUM(vs.tvt_millisec),
        2
    ) AS linear_tvt_share_pct
FROM core_prod.session.video_session vs
JOIN core_prod.content.content_info ci
    ON vs.content_id = ci.content_id
WHERE vs.date >= DATE_ADD(CURRENT_DATE(), -30)
    AND vs.tvt_millisec > 0
"""

# (2) Daily TVT trend — last 90 days (linear vs total)
SQL_DAILY_TVT_TREND = """
SELECT
    vs.date AS dt,
    ROUND(SUM(vs.tvt_millisec) / 3600000.0, 1) AS total_tvt_hours,
    ROUND(SUM(CASE WHEN ci.content_type = 'LINEAR' THEN vs.tvt_millisec ELSE 0 END) / 3600000.0, 1) AS linear_tvt_hours
FROM core_prod.session.video_session vs
JOIN core_prod.content.content_info ci
    ON vs.content_id = ci.content_id
WHERE vs.date >= DATE_ADD(CURRENT_DATE(), -90)
    AND vs.tvt_millisec > 0
GROUP BY vs.date
ORDER BY vs.date
"""

# (3) Top 10 channels by TVT hours — last 30 days
SQL_TOP_CHANNELS = """
SELECT
    ci.title AS channel_name,
    vs.content_id,
    ROUND(SUM(vs.tvt_millisec) / 3600000.0, 0) AS tvt_hours
FROM core_prod.session.video_session vs
JOIN core_prod.content.content_info ci
    ON vs.content_id = ci.content_id
WHERE vs.date >= DATE_ADD(CURRENT_DATE(), -30)
    AND vs.tvt_millisec > 0
    AND ci.content_type = 'LINEAR'
GROUP BY ci.title, vs.content_id
ORDER BY tvt_hours DESC
LIMIT 10
"""

# (4) Platform breakdown — last 30 days (linear TVT by platform)
SQL_PLATFORM_BREAKDOWN = """
SELECT
    vs.platform AS platform,
    ROUND(SUM(vs.tvt_millisec) / 3600000.0, 0) AS tvt_hours
FROM core_prod.session.video_session vs
JOIN core_prod.content.content_info ci
    ON vs.content_id = ci.content_id
WHERE vs.date >= DATE_ADD(CURRENT_DATE(), -30)
    AND vs.tvt_millisec > 0
    AND ci.content_type = 'LINEAR'
GROUP BY vs.platform
ORDER BY tvt_hours DESC
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HARDCODED_FALLBACK_KPIS = {
    "linear_tvt_share_current": 4.28,
    "linear_tvt_share_target": 9.0,
    "channel_count": 340,
    "source": "hardcoded_fallback",
}


def _run_query(sql: str, cache_key: str):
    """Run a Databricks query, returning rows as dicts. Uses kpi_cache."""
    cached = db.get_cached_kpi(cache_key)
    if cached is not None:
        return cached

    try:
        from linear_data.connection import get_cursor

        t0 = time.time()
        with get_cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        elapsed = time.time() - t0
        db.log_query(sql_text=sql, query_name=cache_key,
                     row_count=len(rows), elapsed_sec=round(elapsed, 2))
        db.set_cached_kpi(cache_key, rows)
        return rows
    except Exception as e:
        log.warning("Databricks query failed (%s): %s", cache_key, e)
        db.log_query(sql_text=sql, query_name=cache_key, error=str(e))
        return None


def _get_qa_status() -> dict:
    """Get QA status indicator (green/yellow/red) from latest checks."""
    try:
        with db.get_db() as conn:
            rows = conn.execute("""
                SELECT qc.metric_name, qc.match, qc.drift_pct, qc.checked_at
                FROM qa_checks qc
                INNER JOIN (
                    SELECT metric_name, MAX(checked_at) AS latest
                    FROM qa_checks GROUP BY metric_name
                ) lc ON qc.metric_name = lc.metric_name AND qc.checked_at = lc.latest
            """).fetchall()

        if not rows:
            return {"indicator": "unknown", "message": "No QA checks run yet"}

        checks = [dict(r) for r in rows]
        fail_count = sum(1 for c in checks if not c["match"])
        last_check = max(c["checked_at"] for c in checks)

        if fail_count == 0:
            return {"indicator": "green", "message": "All checks passing", "last_check": last_check}
        elif fail_count <= 1:
            return {"indicator": "yellow", "message": f"{fail_count} check failing", "last_check": last_check}
        else:
            return {"indicator": "red", "message": f"{fail_count} checks failing", "last_check": last_check}
    except Exception:
        return {"indicator": "unknown", "message": "QA system error"}


def _find_latest_run():
    """Find the most recent scan run with analysis."""
    if not SCANS_DIR.exists():
        return None, None
    for date_dir in sorted(SCANS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for run_dir in sorted(date_dir.iterdir(), reverse=True):
            if not run_dir.is_dir() or not (run_dir / "run.json").exists():
                continue
            return date_dir.name, run_dir.name
    return None, None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/overview")
def get_overview():
    """Main dashboard overview with live KPIs from Databricks."""
    scan_date, run_id = _find_latest_run()

    # Load latest scan summary
    scan_summary = None
    if scan_date and run_id:
        run_file = SCANS_DIR / scan_date / run_id / "run.json"
        if run_file.exists():
            with open(run_file) as f:
                scan_summary = json.load(f)
            scan_summary["scan_date"] = scan_date
            scan_summary["run_id"] = run_id

    # Count intel artifacts
    signal_count = len(list(INTEL_DIR.glob("signals/*.md"))) if INTEL_DIR.exists() else 0
    finding_count = len(list(INTEL_DIR.glob("findings/*.md"))) if INTEL_DIR.exists() else 0
    insight_count = len(list(INTEL_DIR.glob("insights/*.md"))) if INTEL_DIR.exists() else 0
    report_count = len(list(ANALYSIS_DIR.glob("reports/*.md"))) if ANALYSIS_DIR.exists() else 0

    # Work item stats
    work_items = db.get_work_items(limit=500)
    work_stats = {
        "total": len(work_items),
        "open": sum(1 for w in work_items if w["status"] == "open"),
        "in_progress": sum(1 for w in work_items if w["status"] == "in_progress"),
        "blocked": sum(1 for w in work_items if w["status"] == "blocked"),
        "done": sum(1 for w in work_items if w["status"] == "done"),
    }

    # Data verification stats
    verifications = db.get_verifications(limit=500)
    verify_stats = {
        "total": len(verifications),
        "match": sum(1 for v in verifications if v["match_status"] == "match"),
        "mismatch": sum(1 for v in verifications if v["match_status"] == "mismatch"),
        "pending": sum(1 for v in verifications if v["match_status"] == "pending"),
    }

    # Experiment stats
    experiments = db.get_experiments(limit=100)
    exp_stats = {
        "total": len(experiments),
        "running": sum(1 for e in experiments if e["status"] == "running"),
        "planned": sum(1 for e in experiments if e["status"] == "planned"),
    }

    # Learning count
    learnings = db.get_learnings(limit=500)

    # --- Live KPIs from Databricks ---
    tvt_share_rows = _run_query(SQL_LINEAR_TVT_SHARE, "linear_tvt_share_30d")
    daily_trend = _run_query(SQL_DAILY_TVT_TREND, "daily_tvt_trend_90d")
    top_channels = _run_query(SQL_TOP_CHANNELS, "top_channels_30d")
    platform_breakdown = _run_query(SQL_PLATFORM_BREAKDOWN, "platform_breakdown_30d")

    # Build KPIs — fall back to hardcoded values if Databricks is unavailable
    if tvt_share_rows and len(tvt_share_rows) > 0 and tvt_share_rows[0].get("linear_tvt_share_pct") is not None:
        linear_share = float(tvt_share_rows[0]["linear_tvt_share_pct"])
        kpi_source = "databricks"
    else:
        linear_share = HARDCODED_FALLBACK_KPIS["linear_tvt_share_current"]
        kpi_source = "hardcoded_fallback"

    kpis = {
        "linear_tvt_share_current": linear_share,
        "linear_tvt_share_target": 9.0,
        "channel_count": 340,
        "source": kpi_source,
    }

    # Format trend data for charting (list of {date, total_hours, linear_hours})
    # Cast to float to avoid returning Decimal/string types from Databricks
    trend_data = []
    if daily_trend:
        for row in daily_trend:
            total_h = row.get("total_tvt_hours")
            linear_h = row.get("linear_tvt_hours")
            trend_data.append({
                "date": str(row.get("dt", "")),
                "total_tvt_hours": float(total_h) if total_h is not None else 0.0,
                "linear_tvt_hours": float(linear_h) if linear_h is not None else 0.0,
            })

    # Format top channels — cast tvt_hours to float
    channels_data = []
    if top_channels:
        for row in top_channels:
            h = row.get("tvt_hours")
            channels_data.append({
                "channel_name": row.get("channel_name", "Unknown"),
                "content_id": row.get("content_id"),
                "tvt_hours": float(h) if h is not None else 0.0,
            })

    # Format platform breakdown — cast tvt_hours to float
    platform_data = []
    if platform_breakdown:
        for row in platform_breakdown:
            h = row.get("tvt_hours")
            platform_data.append({
                "platform": row.get("platform", "Unknown"),
                "tvt_hours": float(h) if h is not None else 0.0,
            })

    # QA status indicator
    qa_status = _get_qa_status()

    # Monitor summary
    sources = db.get_data_sources()
    sources_healthy = sum(1 for s in sources if s["status"] == "healthy")
    sources_stale = sum(1 for s in sources if s["status"] == "stale")
    sources_error = sum(1 for s in sources if s["status"] == "error")
    alert_items = [w for w in work_items if w["type"] == "alert" and w["status"] == "open"]

    return {
        "monitor": {
            "sources_total": len(sources),
            "sources_healthy": sources_healthy,
            "sources_stale": sources_stale,
            "sources_error": sources_error,
            "open_alerts": len(alert_items),
        },
        "kpis": kpis,
        "daily_trend": trend_data,
        "top_channels": channels_data,
        "platform_breakdown": platform_data,
        "latest_scan": scan_summary,
        "intel": {
            "signals": signal_count,
            "findings": finding_count,
            "insights": insight_count,
            "reports": report_count,
        },
        "work": work_stats,
        "verifications": verify_stats,
        "experiments": exp_stats,
        "learnings": len(learnings),
        "sentiment": db.get_sentiment_summary(),
        "qa_status": qa_status,
    }


@router.get("/goals")
def get_goals():
    """H2 FY26 goal tracking with real progress from work items."""
    # Define initiatives with their associated tag for matching work items
    initiatives_def = [
        {"name": "Sea Tiger (NFL, World Cup)", "tag": "sea_tiger", "tvt_impact": "TBD"},
        {"name": "Registration Gate", "tag": "registration", "tvt_impact": "TBD"},
        {"name": "Metadata Improvements", "tag": "metadata", "tvt_impact": "+0.05%"},
        {"name": "Linear Detail Pages", "tag": "detail_pages", "tvt_impact": "+0.10%"},
        {"name": "Partner Integration", "tag": "partner", "tvt_impact": "TBD"},
        {"name": "Promote Upcoming Programs", "tag": "upcoming_programs", "tvt_impact": "+0.04%"},
        {"name": "Program-level Ranking", "tag": "program_ranking", "tvt_impact": "+0.02%"},
        {"name": "Streamlined Channel Browsing", "tag": "channel_browsing", "tvt_impact": "+0.05%"},
        {"name": "Container Ranking", "tag": "container_ranking", "tvt_impact": "+0.01%"},
    ]

    # Pull all work items to compute progress per initiative
    all_work = db.get_work_items(limit=500)

    initiatives = []
    for init in initiatives_def:
        tag = init["tag"]
        # Match work items whose tags JSON contains this tag, or whose title contains the tag/name
        matched = [w for w in all_work if tag in w.get("tags", "")
                    or tag in w.get("title", "").lower()
                    or init["name"].split("(")[0].strip().lower() in w.get("title", "").lower()]
        total = len(matched)
        done = sum(1 for w in matched if w["status"] == "done")

        # Derive status from work item states
        if total == 0:
            status = "planned"
            progress_pct = 0
        elif done == total:
            status = "completed"
            progress_pct = 100
        elif any(w["status"] == "blocked" for w in matched):
            status = "blocked"
            progress_pct = round((done / total) * 100) if total else 0
        elif any(w["status"] in ("in_progress", "open") for w in matched):
            status = "in_progress"
            progress_pct = round((done / total) * 100) if total else 0
        else:
            status = "planned"
            progress_pct = 0

        initiatives.append({
            "name": init["name"],
            "status": status,
            "tvt_impact": init["tvt_impact"],
            "tag": tag,
            "work_items_total": total,
            "work_items_done": done,
            "progress_pct": progress_pct,
        })

    return {
        "period": "H2 FY26",
        "goals": [
            {"name": "Global TVT", "target": "+0.22%", "metric": "tvt_share_delta"},
            {"name": "Linear TVT", "target": "+5.32%", "metric": "linear_tvt_share_delta"},
        ],
        "initiatives": initiatives,
    }


# ---------------------------------------------------------------------------
# AI Summary endpoint
# ---------------------------------------------------------------------------

# In-memory cache for AI summary
_summary_cache = {"text": None, "generated_at": None}
_SUMMARY_CACHE_TTL = 3600  # 1 hour


@router.get("/summary")
def get_summary():
    """AI-generated summary of current state. Uses OpenAI gpt-4o, cached 1 hour."""
    import time as _time

    # Check cache
    if (_summary_cache["text"] is not None
            and _summary_cache["generated_at"] is not None
            and (_time.time() - _summary_cache["generated_at"]) < _SUMMARY_CACHE_TTL):
        return {"summary": _summary_cache["text"], "cached": True}

    # Gather context for the summary
    try:
        overview = get_overview()
    except Exception:
        overview = {}

    kpis = overview.get("kpis", {})
    work = overview.get("work", {})
    sentiment = overview.get("sentiment", {})
    intel = overview.get("intel", {})
    experiments = overview.get("experiments", {})
    qa = overview.get("qa_status", {})

    context = (
        f"Linear TVT share: {kpis.get('linear_tvt_share_current', 'N/A')}% (target: {kpis.get('linear_tvt_share_target', 9.0)}%). "
        f"Channel count: {kpis.get('channel_count', 'N/A')}. "
        f"Data source: {kpis.get('source', 'unknown')}. "
        f"Work items: {work.get('open', 0)} open, {work.get('in_progress', 0)} in progress, {work.get('blocked', 0)} blocked, {work.get('done', 0)} done. "
        f"Sentiment: {sentiment.get('total', 0)} feedback items, avg score {sentiment.get('avg_score', 0)}. "
        f"Intel: {intel.get('signals', 0)} signals, {intel.get('findings', 0)} findings. "
        f"Experiments: {experiments.get('running', 0)} running of {experiments.get('total', 0)} total. "
        f"QA status: {qa.get('indicator', 'unknown')} — {qa.get('message', '')}. "
        f"Top channels data: {len(overview.get('top_channels', []))} channels loaded. "
        f"Platform breakdown: {len(overview.get('platform_breakdown', []))} platforms loaded."
    )

    # Call OpenAI
    if not OPENAI_API_KEY:
        summary_text = (
            f"Linear TVT share is at {kpis.get('linear_tvt_share_current', 'N/A')}% vs the 9.0% target. "
            f"There are {work.get('open', 0)} open and {work.get('blocked', 0)} blocked work items. "
            f"AI summary requires OPENAI_API_KEY in .env."
        )
        _summary_cache["text"] = summary_text
        _summary_cache["generated_at"] = _time.time()
        return {"summary": summary_text, "cached": False}

    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a concise executive briefer for a streaming TV analytics hub. Write a single paragraph (3-5 sentences) summarizing the current state. Cover: what's going well, what's concerning, and what needs attention. Be specific with numbers. No bullet points, no headers — just a paragraph."},
                {"role": "user", "content": f"Here is the current state of the Linear Hub:\n\n{context}"},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        summary_text = resp.choices[0].message.content.strip()
    except Exception as e:
        log.warning("OpenAI summary generation failed: %s", e)
        summary_text = (
            f"Linear TVT share is at {kpis.get('linear_tvt_share_current', 'N/A')}% vs the 9.0% target. "
            f"There are {work.get('open', 0)} open and {work.get('blocked', 0)} blocked work items requiring attention. "
            f"(AI summary generation failed: {str(e)[:100]})"
        )

    _summary_cache["text"] = summary_text
    _summary_cache["generated_at"] = _time.time()
    return {"summary": summary_text, "cached": False}
