"""Dashboard overview: KPIs, goal tracking, system health.

Queries live Databricks data for linear KPIs and caches results in SQLite
with a 1-hour TTL so we don't hammer the warehouse on every page load.
"""

import json
import logging
import sys
import time
from datetime import datetime

from fastapi import APIRouter

from ..config import SCANS_DIR, INTEL_DIR, ANALYSIS_DIR, PLUGINS_DIR
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
    trend_data = []
    if daily_trend:
        for row in daily_trend:
            trend_data.append({
                "date": str(row.get("dt", "")),
                "total_tvt_hours": row.get("total_tvt_hours"),
                "linear_tvt_hours": row.get("linear_tvt_hours"),
            })

    # Format top channels
    channels_data = []
    if top_channels:
        for row in top_channels:
            channels_data.append({
                "channel_name": row.get("channel_name", "Unknown"),
                "content_id": row.get("content_id"),
                "tvt_hours": row.get("tvt_hours"),
            })

    # Format platform breakdown
    platform_data = []
    if platform_breakdown:
        for row in platform_breakdown:
            platform_data.append({
                "platform": row.get("platform", "Unknown"),
                "tvt_hours": row.get("tvt_hours"),
            })

    # QA status indicator
    qa_status = _get_qa_status()

    return {
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
    """H2 FY26 goal tracking."""
    return {
        "period": "H2 FY26",
        "goals": [
            {"name": "Global TVT", "target": "+0.22%", "metric": "tvt_share_delta"},
            {"name": "Linear TVT", "target": "+5.32%", "metric": "linear_tvt_share_delta"},
        ],
        "initiatives": [
            {"name": "Sea Tiger (NFL, World Cup)", "status": "in_progress", "tvt_impact": "TBD"},
            {"name": "Registration Gate", "status": "planned", "tvt_impact": "TBD"},
            {"name": "Metadata Improvements", "status": "in_progress", "tvt_impact": "+0.05%"},
            {"name": "Linear Detail Pages", "status": "planned", "tvt_impact": "+0.10%"},
            {"name": "Partner Integration", "status": "in_progress", "tvt_impact": "TBD"},
            {"name": "Promote Upcoming Programs", "status": "planned", "tvt_impact": "+0.04%"},
            {"name": "Program-level Ranking", "status": "planned", "tvt_impact": "+0.02%"},
            {"name": "Streamlined Channel Browsing", "status": "in_progress", "tvt_impact": "+0.05%"},
            {"name": "Container Ranking", "status": "planned", "tvt_impact": "+0.01%"},
        ],
    }
