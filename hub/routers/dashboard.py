"""Dashboard overview: KPIs, goal tracking, system health."""

import json
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter

from ..config import SCANS_DIR, INTEL_DIR, ANALYSIS_DIR
from .. import db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


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


@router.get("/overview")
def get_overview():
    """Main dashboard overview with KPIs and system health."""
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

    return {
        "kpis": {
            "linear_tvt_share_current": 4.28,
            "linear_tvt_share_target": 9.0,
            "h2_tvt_goal": "+0.22%",
            "h2_linear_tvt_goal": "+5.32%",
            "channel_count": 340,
        },
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
