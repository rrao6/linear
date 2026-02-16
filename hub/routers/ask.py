"""Natural language query interface: ask questions in plain English, get data from Databricks."""

import json
import re
import sys
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import OPENAI_API_KEY, PLUGINS_DIR
from .. import db

# Add linear-data plugin to path
sys.path.insert(0, str(PLUGINS_DIR / "linear-data"))

router = APIRouter(prefix="/api/ask", tags=["ask"])

# Load table documentation at module level for the system prompt
_REFERENCES_DIR = PLUGINS_DIR / "linear-data" / "skills" / "linear-data" / "references"


def _load_reference(filename: str) -> str:
    path = _REFERENCES_DIR / filename
    if path.exists():
        return path.read_text()
    return ""


TABLES_DOC = _load_reference("tables.md")
PATTERNS_DOC = _load_reference("query-patterns.md")

SYSTEM_PROMPT = f"""You are a SQL query generator for Tubi's Databricks data warehouse.
Given a natural language question, generate a valid Databricks SQL query.

CRITICAL RULES — you MUST follow these:
1. Always filter on partition key: `date` for video_session, `ds` for dsac tables
2. Always add `tvt_millisec > 0` when querying video_session
3. TVT is in milliseconds — divide by 3600000.0 for hours, 60000.0 for minutes, 1000.0 for seconds
4. `content_info.duration` is in MINUTES, not milliseconds
5. For LINEAR content, `content_id` = channel, not program. Use `linear_epg_video_sessions` for program-level data
6. Default to last 30 days unless the user specifies a different range: `date >= CURRENT_DATE - INTERVAL 30 DAYS`
7. Always LIMIT 100 unless the user explicitly asks for more
8. Always filter `country = 'US'` unless the user asks about a different country
9. Only ~30-40% of viewers are registered (user_id IS NOT NULL)
10. Generate ONLY SELECT statements. Never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, or any DDL/DML.

KEY TABLES:
- core_prod.session.video_session — primary viewing data (partition: date)
- core_prod.tubidw.content_info — content metadata (content_id, content_name, content_type, duration in minutes)
- core_prod.tubidw.linear_epg_video_sessions — program-level linear viewing
- core_prod.tubidw.epg_schedules — linear schedule grid
- core_dev.dsa.dsac_viewpres_vidsession_sample — presentation tracking (partition: ds)
- core_prod.tubidw.content_earnings_daily — revenue data
- core_prod.tubidw.device_first_metrics — new user identification

PLATFORM VALUES: ROKU, AMAZONFIRETV, SAMSUNG, VIZIO, LGTV, ANDROIDTV, IPHONE, IPAD, ANDROID, WEB, PS5, XBOX
CONTENT TYPES: LINEAR, MOVIE, SERIES, SPORTS_EVENT
PAGE SOURCES: HomePage, VideoPlayerPage, LinearBrowsePage, SearchPage, ForYouPage, ContentDetailsPage

COMMON JOINS:
- video_session.content_id = content_info.content_id (for content names/metadata)
- video_session.content_id = linear_epg_video_sessions.content_id (for program-level linear)

TABLE DOCUMENTATION:
{TABLES_DOC}

QUERY PATTERNS:
{PATTERNS_DOC}

Respond with ONLY the SQL query, no explanation, no markdown fences, no comments."""

SUMMARY_PROMPT = """You are a data analyst summarizing query results for a product manager.
Given the original question, the SQL query that was run, and the results, write a concise
plain-English summary (2-4 sentences). Highlight key numbers, trends, or surprises.
Be specific with numbers. Do not include the SQL in your summary."""

# Forbidden SQL patterns
_FORBIDDEN_PATTERNS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|MERGE|CALL)\b',
    re.IGNORECASE
)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    sql: str
    results: list
    summary: str
    rows: int
    error: str = ""


def _validate_sql(sql: str) -> "str | None":
    """Validate that SQL is SELECT-only. Returns error message or None if valid."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped.upper().startswith("SELECT") and not stripped.upper().startswith("WITH"):
        return "Only SELECT queries are allowed"
    if _FORBIDDEN_PATTERNS.search(stripped):
        return "Query contains forbidden statements (INSERT/UPDATE/DELETE/DROP/etc.)"
    return None


def _call_openai(system: str, user: str, max_tokens: int = 2000) -> str:
    """Call OpenAI API. Raises on failure."""
    import httpx

    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _serialize(v):
    """Make values JSON-serializable."""
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


@router.post("")
def ask(req: AskRequest):
    """Ask a question in plain English and get data from Databricks."""
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    start = time.time()

    # Step 1: Generate SQL from question
    try:
        raw_sql = _call_openai(SYSTEM_PROMPT, question, max_tokens=1000)
    except HTTPException:
        raise
    except Exception as e:
        db.log_ask(question, "", error=f"SQL generation failed: {e}")
        return {"sql": "", "results": [], "summary": "", "rows": 0,
                "error": f"Failed to generate SQL: {e}"}

    # Clean up: strip markdown fences if the model included them
    sql = raw_sql.strip()
    if sql.startswith("```"):
        sql = re.sub(r'^```(?:sql)?\s*', '', sql)
        sql = re.sub(r'\s*```$', '', sql)
    sql = sql.strip()

    # Step 2: Validate SQL safety
    validation_error = _validate_sql(sql)
    if validation_error:
        db.log_ask(question, sql, error=validation_error)
        return {"sql": sql, "results": [], "summary": "", "rows": 0,
                "error": validation_error}

    # Step 3: Execute against Databricks
    try:
        from linear_data.connection import get_cursor
    except ImportError:
        db.log_ask(question, sql, error="Databricks connector not available")
        return {"sql": sql, "results": [], "summary": "", "rows": 0,
                "error": "Databricks connector not available. Install: pip install databricks-sql-connector"}

    try:
        with get_cursor() as cursor:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            raw_rows = cursor.fetchmany(200)
        rows_data = [dict(zip(columns, [_serialize(v) for v in row])) for row in raw_rows]
    except Exception as e:
        elapsed = time.time() - start
        db.log_ask(question, sql, error=str(e), elapsed_sec=elapsed)
        return {"sql": sql, "results": [], "summary": "", "rows": 0,
                "error": f"Query execution failed: {e}"}

    elapsed = time.time() - start

    # Step 4: Generate summary
    summary = ""
    try:
        results_preview = json.dumps(rows_data[:20], default=str)
        summary_input = (
            f"Question: {question}\n\n"
            f"SQL: {sql}\n\n"
            f"Results ({len(rows_data)} rows):\n{results_preview}"
        )
        summary = _call_openai(SUMMARY_PROMPT, summary_input, max_tokens=300)
    except Exception:
        summary = f"Query returned {len(rows_data)} rows."

    # Step 5: Log to history
    db.log_ask(
        question=question,
        sql=sql,
        results=rows_data,
        summary=summary,
        rows=len(rows_data),
        elapsed_sec=round(elapsed, 2),
    )

    return {
        "sql": sql,
        "results": rows_data,
        "summary": summary,
        "rows": len(rows_data),
    }


@router.get("/history")
def ask_history(limit: int = 20):
    """Return past natural language queries with their results."""
    history = db.get_ask_history(limit=limit)
    # Trim results in history to save bandwidth — keep only first 5 rows per entry
    for entry in history:
        if isinstance(entry.get("results"), list) and len(entry["results"]) > 5:
            entry["results"] = entry["results"][:5]
    return history
