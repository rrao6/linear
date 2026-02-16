"""Monitoring router: health, sources, events, heartbeats."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from .. import db
from ..config import DATA_DIR
from ..monitoring import check_freshness, get_uptime_seconds

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


class HeartbeatRequest(BaseModel):
    source: str
    items_collected: int = 0
    error: str = ""


class EventRequest(BaseModel):
    event_type: str
    source: str = ""
    message: str
    details: dict = {}


def _disk_usage(path: Path) -> dict:
    """Get disk usage for a directory in bytes."""
    total = 0
    file_count = 0
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
                file_count += 1
    return {"bytes": total, "mb": round(total / (1024 * 1024), 2), "files": file_count}


@router.get("/health")
def get_health():
    """Overall system health: sources, uptime, row counts, disk usage."""
    sources = db.get_data_sources()
    healthy = sum(1 for s in sources if s["status"] == "healthy")
    stale = sum(1 for s in sources if s["status"] == "stale")
    errored = sum(1 for s in sources if s["status"] == "error")

    row_counts = db.get_table_row_counts()

    # Last QA check (most recent data_verification)
    verifications = db.get_verifications(limit=1)
    last_qa = verifications[0] if verifications else None

    return {
        "status": "degraded" if (stale > 0 or errored > 0) else "healthy",
        "uptime_seconds": round(get_uptime_seconds(), 1),
        "sources": {
            "total": len(sources),
            "healthy": healthy,
            "stale": stale,
            "error": errored,
        },
        "row_counts": row_counts,
        "last_qa_check": {
            "metric": last_qa["metric_name"] if last_qa else None,
            "status": last_qa["match_status"] if last_qa else None,
            "at": last_qa["created_at"] if last_qa else None,
        },
        "disk_usage": _disk_usage(DATA_DIR),
        "checked_at": datetime.now().isoformat(),
    }


@router.get("/sources")
def get_sources():
    """Detailed source-by-source freshness with last error messages."""
    sources = db.get_data_sources()
    result = []
    now = datetime.now()
    for src in sources:
        last_success = src["last_success_at"]
        if last_success:
            age_hours = (now - datetime.fromisoformat(last_success)).total_seconds() / 3600
        else:
            age_hours = None

        result.append({
            "source_name": src["source_name"],
            "status": src["status"],
            "last_run_at": src["last_run_at"],
            "last_success_at": src["last_success_at"],
            "last_error": src["last_error"],
            "items_collected": src["items_collected"],
            "expected_interval_hours": src["expected_interval_hours"],
            "age_hours": round(age_hours, 1) if age_hours is not None else None,
            "updated_at": src["updated_at"],
        })
    return result


@router.get("/log")
def get_log(limit: int = 100, event_type: Optional[str] = None):
    """Last N events from the event log."""
    return db.get_event_log(limit=limit, event_type=event_type)


@router.post("/heartbeat")
def post_heartbeat(req: HeartbeatRequest):
    """Collectors call this after completing a run."""
    status = "error" if req.error else "healthy"
    db.upsert_data_source(
        source_name=req.source,
        status=status,
        last_error=req.error,
        items_collected=req.items_collected,
    )
    db.log_event(
        event_type="heartbeat",
        source=req.source,
        message=f"Heartbeat from '{req.source}': {req.items_collected} items" + (
            f" (error: {req.error})" if req.error else ""
        ),
        details={"items_collected": req.items_collected, "error": req.error},
    )
    return {"status": "ok", "source": req.source, "recorded_status": status}


@router.post("/event")
def post_event(req: EventRequest):
    """Log an arbitrary event (workers call this for start/finish)."""
    event_id = db.log_event(
        event_type=req.event_type,
        source=req.source,
        message=req.message,
        details=req.details,
    )
    return {"status": "ok", "event_id": event_id}


@router.post("/check")
def trigger_check():
    """Manually trigger a freshness check."""
    stale = check_freshness()
    return {
        "stale_sources": stale,
        "checked_at": datetime.now().isoformat(),
    }
