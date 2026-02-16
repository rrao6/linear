"""Background monitoring: freshness checks and staleness alerting."""

import threading
import time
from datetime import datetime, timedelta

from . import db

# Expected refresh intervals per source (hours)
DEFAULT_INTERVALS = {
    "databricks": 2,
    "reddit": 6,
    "appstore": 12,
    "sprout_social": 12,
    "intel_scan": 24,
}

_checker_thread = None
_stop_event = threading.Event()
_start_time = None


def get_uptime_seconds() -> float:
    if _start_time is None:
        return 0
    return (datetime.now() - _start_time).total_seconds()


def ensure_default_sources():
    """Seed data_sources table with known sources if they don't exist."""
    for name, interval in DEFAULT_INTERVALS.items():
        existing = db.get_data_source(name)
        if not existing:
            db.upsert_data_source(
                source_name=name,
                status="unknown",
                expected_interval_hours=interval,
            )


def check_freshness():
    """Check all sources for staleness. Returns list of stale source names."""
    sources = db.get_data_sources()
    stale_sources = []
    now = datetime.now()

    for src in sources:
        name = src["source_name"]
        interval_hours = src["expected_interval_hours"] or DEFAULT_INTERVALS.get(name, 24)
        last_success = src["last_success_at"]

        if not last_success:
            # Never collected — mark stale if source has been registered for > interval
            created = datetime.fromisoformat(src["created_at"])
            if (now - created).total_seconds() > interval_hours * 3600:
                db.update_data_source_status(name, "stale")
                stale_sources.append(name)
            continue

        last_ts = datetime.fromisoformat(last_success)
        age_hours = (now - last_ts).total_seconds() / 3600

        if src["status"] == "error":
            stale_sources.append(name)
            continue

        if age_hours > interval_hours:
            db.update_data_source_status(name, "stale")
            stale_sources.append(name)
        else:
            db.update_data_source_status(name, "healthy")

    return stale_sources


def _create_staleness_alert(source_name: str):
    """Create a work item alert for a stale source, avoiding duplicates."""
    title = f"[ALERT] Data source '{source_name}' is stale"
    # Check for existing open alert
    existing = db.get_work_items(status="open", type="alert", limit=500)
    for item in existing:
        if item["title"] == title:
            return  # Already exists

    src = db.get_data_source(source_name)
    last_success = src["last_success_at"] or "never"
    interval = src["expected_interval_hours"] or DEFAULT_INTERVALS.get(source_name, 24)
    description = (
        f"Data source '{source_name}' has not been refreshed within its expected interval.\n"
        f"Expected interval: {interval}h\n"
        f"Last success: {last_success}\n"
        f"Last error: {src.get('last_error', 'none')}"
    )
    db.create_work_item(
        type="alert",
        title=title,
        description=description,
        priority="high",
        tags=["monitoring", "staleness", source_name],
    )
    db.log_event(
        event_type="alert",
        source=source_name,
        message=f"Staleness alert created for '{source_name}'",
        details={"last_success_at": last_success, "interval_hours": interval},
    )


def _checker_loop(interval_seconds: int = 1800):
    """Background loop: check freshness every interval_seconds (default 30 min)."""
    while not _stop_event.is_set():
        try:
            stale = check_freshness()
            for name in stale:
                _create_staleness_alert(name)
            if stale:
                db.log_event(
                    event_type="freshness_check",
                    message=f"Freshness check found {len(stale)} stale source(s): {', '.join(stale)}",
                )
            else:
                db.log_event(
                    event_type="freshness_check",
                    message="Freshness check: all sources healthy",
                )
        except Exception as e:
            db.log_event(
                event_type="error",
                message=f"Freshness checker error: {e}",
            )
        _stop_event.wait(interval_seconds)


def start_checker(interval_seconds: int = 1800):
    """Start the background freshness checker thread."""
    global _checker_thread, _start_time
    _start_time = datetime.now()
    _stop_event.clear()
    ensure_default_sources()
    _checker_thread = threading.Thread(
        target=_checker_loop,
        args=(interval_seconds,),
        daemon=True,
        name="freshness-checker",
    )
    _checker_thread.start()


def stop_checker():
    """Stop the background freshness checker."""
    _stop_event.set()
    if _checker_thread:
        _checker_thread.join(timeout=5)
