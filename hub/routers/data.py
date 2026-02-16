"""Data explorer: Databricks query proxy and query library."""

import sys
import time

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import PLUGINS_DIR
from .. import db

# Add linear-data plugin to path
sys.path.insert(0, str(PLUGINS_DIR / "linear-data"))

router = APIRouter(prefix="/api/data", tags=["data"])


class SQLQuery(BaseModel):
    sql: str
    limit: int = 100


class NamedQuery(BaseModel):
    name: str
    days: int = 30
    limit: int = 50


def _run_sql(sql: str, limit: int = 100) -> dict:
    """Execute SQL and return structured results."""
    try:
        from linear_data.connection import get_cursor
    except ImportError:
        return {"error": "Databricks connector not available. Install: pip install databricks-sql-connector"}

    start = time.time()
    try:
        with get_cursor() as cursor:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchmany(limit)
        elapsed = time.time() - start
        data = [dict(zip(columns, [_serialize(v) for v in row])) for row in rows]
        db.log_query(sql, row_count=len(data), elapsed_sec=elapsed)
        return {
            "columns": columns,
            "rows": data,
            "row_count": len(data),
            "elapsed_sec": round(elapsed, 2),
        }
    except Exception as e:
        elapsed = time.time() - start
        db.log_query(sql, error=str(e), elapsed_sec=elapsed)
        return {"error": str(e), "elapsed_sec": round(elapsed, 2)}


def _serialize(v):
    """Make values JSON-serializable."""
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


@router.post("/query")
def run_query(q: SQLQuery):
    """Execute raw SQL against Databricks."""
    return _run_sql(q.sql, q.limit)


@router.post("/named")
def run_named(q: NamedQuery):
    """Run a canonical named query."""
    try:
        from linear_data.cli import get_canonical_queries
    except ImportError:
        return {"error": "linear_data CLI not available"}

    queries = get_canonical_queries()
    if q.name not in queries:
        return {"error": f"Unknown query: {q.name}", "available": list(queries.keys())}

    sql = queries[q.name]["sql"].format(days=q.days, limit=q.limit)
    result = _run_sql(sql, q.limit)
    result["query_name"] = q.name
    result["description"] = queries[q.name]["description"]
    return result


@router.get("/queries")
def list_queries():
    """List all canonical queries."""
    try:
        from linear_data.cli import get_canonical_queries
    except ImportError:
        return {"error": "linear_data CLI not available"}

    queries = get_canonical_queries()
    return [{"name": k, "description": v["description"]} for k, v in queries.items()]


@router.get("/history")
def query_history(limit: int = 50):
    """Get query execution history."""
    return db.get_query_history(limit)


@router.get("/tables")
def get_tables():
    """Return key table reference info."""
    return {
        "primary": [
            {"name": "core_prod.session.video_session", "partition": "date",
             "description": "Primary viewing data (one row per session)"},
            {"name": "core_prod.tubidw.content_info", "partition": None,
             "description": "Content metadata (names, genres, duration in minutes)"},
            {"name": "core_prod.tubidw.linear_epg_video_sessions", "partition": None,
             "description": "Program-level linear viewing (schedule-aware)"},
            {"name": "core_prod.tubidw.epg_schedules", "partition": None,
             "description": "Linear schedule grid (live_broadcast flag)"},
            {"name": "core_dev.dsa.dsac_viewpres_vidsession_sample", "partition": "ds",
             "description": "Presentation tracking (what was shown + watched)"},
            {"name": "core_prod.analytics.viewable_impression", "partition": "date",
             "description": "Container impression tracking"},
            {"name": "core_prod.events.presentation_event", "partition": "date",
             "description": "Full presentation events with container ordering"},
        ],
        "gotchas": [
            "Always filter on partition key (date or ds)",
            "Always add tvt_millisec > 0",
            "TVT is in milliseconds: /3600000.0 for hours",
            "content_info.duration is in minutes (not ms)",
            "For LINEAR, content_id = channel, not program — use linear_epg_video_sessions for program-level",
            "Only ~30-40% of viewers are registered (user_id IS NOT NULL)",
            "49.8% of linear sessions have empty page_source",
        ],
    }
