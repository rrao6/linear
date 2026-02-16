"""QA endpoints — check data accuracy, view history, trigger runs."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter

from ..db import get_db
from ..qa.runner import trigger_immediate_run

router = APIRouter(prefix="/api/qa", tags=["qa"])


@router.get("/status")
def qa_status():
    """Latest check results for all metrics, overall pass/fail."""
    with get_db() as conn:
        # Get the most recent check for each metric
        rows = conn.execute("""
            SELECT qc.*
            FROM qa_checks qc
            INNER JOIN (
                SELECT metric_name, MAX(checked_at) AS latest
                FROM qa_checks
                GROUP BY metric_name
            ) latest_checks
            ON qc.metric_name = latest_checks.metric_name
               AND qc.checked_at = latest_checks.latest
            ORDER BY qc.metric_name
        """).fetchall()

    checks = [dict(r) for r in rows]
    all_pass = all(c.get("match") for c in checks) if checks else False
    fail_count = sum(1 for c in checks if not c.get("match"))

    # Determine overall status color
    if not checks:
        overall = "unknown"
    elif all_pass:
        overall = "green"
    elif fail_count <= 1:
        overall = "yellow"
    else:
        overall = "red"

    return {
        "overall": overall,
        "all_pass": all_pass,
        "total_checks": len(checks),
        "passing": len(checks) - fail_count,
        "failing": fail_count,
        "checks": checks,
    }


@router.get("/history")
def qa_history(metric: Optional[str] = None, limit: int = 100):
    """Historical check results with trend analysis."""
    with get_db() as conn:
        if metric:
            rows = conn.execute(
                "SELECT * FROM qa_checks WHERE metric_name = ? ORDER BY checked_at DESC LIMIT ?",
                (metric, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM qa_checks ORDER BY checked_at DESC LIMIT ?",
                (limit,)
            ).fetchall()

    checks = [dict(r) for r in rows]

    # Compute trend per metric: compare latest pass rate to older pass rate
    trend = {}
    metrics_seen = {}
    for c in checks:
        name = c["metric_name"]
        if name not in metrics_seen:
            metrics_seen[name] = []
        metrics_seen[name].append(c)

    for name, metric_checks in metrics_seen.items():
        if len(metric_checks) < 2:
            trend[name] = "insufficient_data"
            continue
        # Recent half vs older half
        mid = len(metric_checks) // 2
        recent = metric_checks[:mid]
        older = metric_checks[mid:]
        recent_pass_rate = sum(1 for c in recent if c["match"]) / max(len(recent), 1)
        older_pass_rate = sum(1 for c in older if c["match"]) / max(len(older), 1)
        if recent_pass_rate > older_pass_rate:
            trend[name] = "improving"
        elif recent_pass_rate < older_pass_rate:
            trend[name] = "degrading"
        else:
            trend[name] = "stable"

    return {
        "checks": checks,
        "trend": trend,
        "total_records": len(checks),
    }


@router.post("/run")
def qa_run():
    """Trigger an immediate full QA check."""
    results = trigger_immediate_run()
    all_pass = all(r.get("match") for r in results) if results else False

    return {
        "status": "completed",
        "all_pass": all_pass,
        "total_checks": len(results),
        "passing": sum(1 for r in results if r.get("match")),
        "failing": sum(1 for r in results if not r.get("match")),
        "results": results,
    }


@router.get("/drift")
def qa_drift():
    """Show only metrics with drift > 0, sorted by severity."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT qc.*
            FROM qa_checks qc
            INNER JOIN (
                SELECT metric_name, MAX(checked_at) AS latest
                FROM qa_checks
                GROUP BY metric_name
            ) latest_checks
            ON qc.metric_name = latest_checks.metric_name
               AND qc.checked_at = latest_checks.latest
            WHERE qc.drift_pct > 0
            ORDER BY qc.drift_pct DESC
        """).fetchall()

    checks = [dict(r) for r in rows]
    return {
        "drifting_metrics": len(checks),
        "checks": checks,
    }
