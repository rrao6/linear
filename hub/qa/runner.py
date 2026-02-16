"""Scheduled QA runner — runs accuracy checks on a configurable interval."""

from __future__ import annotations

import logging
import threading
from typing import List, Optional

from .accuracy import run_all_checks
from ..db import create_work_item, get_db

logger = logging.getLogger(__name__)

# Default interval: 2 hours (in seconds)
DEFAULT_INTERVAL_SEC = 2 * 60 * 60
DRIFT_THRESHOLD_PCT = 5.0

_timer: Optional[threading.Timer] = None
_interval_sec: int = DEFAULT_INTERVAL_SEC
_running = False


def _execute_run():
    """Execute a full QA run and handle mismatches."""
    global _timer, _running
    logger.info("QA runner: starting scheduled check")

    try:
        results = run_all_checks()

        # Check for mismatches above threshold
        for r in results:
            if not r.get("match") and r.get("drift_pct", 0) > DRIFT_THRESHOLD_PCT:
                _create_bug_work_item(r)

        passed = sum(1 for r in results if r.get("match"))
        total = len(results)
        logger.info("QA runner: completed — %d/%d checks passed", passed, total)

    except Exception as e:
        logger.error("QA runner: error during run — %s", e)

    # Schedule next run
    if _running:
        _timer = threading.Timer(_interval_sec, _execute_run)
        _timer.daemon = True
        _timer.start()


def _create_bug_work_item(result: dict):
    """Auto-create a critical bug work item for a drifting metric."""
    metric = result.get("metric_name", "unknown")
    drift = result.get("drift_pct", 0)
    expected = result.get("expected_value", "?")
    actual = result.get("actual_value", "?")
    error = result.get("error", "")

    title = f"[QA] Data drift detected: {metric} ({drift:.1f}% off)"
    description = (
        f"Automated QA check found drift exceeding {DRIFT_THRESHOLD_PCT}% threshold.\n\n"
        f"**Metric:** {metric}\n"
        f"**Expected:** {expected}\n"
        f"**Actual:** {actual}\n"
        f"**Drift:** {drift:.2f}%\n"
    )
    if error:
        description += f"**Error:** {error}\n"

    # Check if a similar open bug already exists to avoid duplicates
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM work_items WHERE type = 'bug' AND status IN ('open', 'in_progress') "
            "AND title LIKE ?",
            (f"%[QA]%{metric}%",)
        ).fetchone()
        if existing:
            logger.info("QA runner: bug already exists for %s (id=%d), skipping", metric, existing[0])
            return

    try:
        item_id = create_work_item(
            type="bug",
            title=title,
            description=description,
            priority="critical",
            tags=["qa", "data-drift", metric],
        )
        logger.info("QA runner: created bug work item #%d for %s", item_id, metric)
    except Exception as e:
        logger.error("QA runner: failed to create bug for %s — %s", metric, e)


def start_scheduler(interval_sec: int = DEFAULT_INTERVAL_SEC):
    """Start the background QA scheduler."""
    global _timer, _interval_sec, _running
    if _running:
        logger.warning("QA scheduler already running")
        return

    _interval_sec = interval_sec
    _running = True
    _timer = threading.Timer(_interval_sec, _execute_run)
    _timer.daemon = True
    _timer.start()
    logger.info("QA scheduler started (interval=%ds)", _interval_sec)


def stop_scheduler():
    """Stop the background QA scheduler."""
    global _timer, _running
    _running = False
    if _timer is not None:
        _timer.cancel()
        _timer = None
    logger.info("QA scheduler stopped")


def trigger_immediate_run() -> List[dict]:
    """Trigger an immediate QA run (not on the scheduler timer).

    Returns the check results.
    """
    logger.info("QA runner: immediate run triggered")
    results = run_all_checks()

    for r in results:
        if not r.get("match") and r.get("drift_pct", 0) > DRIFT_THRESHOLD_PCT:
            _create_bug_work_item(r)

    return results
