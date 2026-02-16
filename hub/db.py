"""SQLite database for hub local state — work items, feedback, OEM snapshots, learnings, experiments."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .config import HUB_DB_PATH

HUB_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
-- Work items: tasks, PRDs, changes, plans
CREATE TABLE IF NOT EXISTS work_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,            -- task, prd, change, plan, investigation
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'open',    -- open, in_progress, blocked, done, cancelled
    priority TEXT DEFAULT 'medium', -- critical, high, medium, low
    owner TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',        -- JSON array of tags
    parent_id INTEGER,             -- for subtasks
    metadata TEXT DEFAULT '{}',    -- JSON blob
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (parent_id) REFERENCES work_items(id)
);

-- Learnings: verified facts, gotchas, data issues
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,        -- data_issue, query_gotcha, metric_verified, platform_behavior, process
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    source TEXT DEFAULT '',        -- where we learned this
    verified BOOLEAN DEFAULT 0,
    tags TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Data verifications: track what's been verified against dashboards
CREATE TABLE IF NOT EXISTS data_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    query_sql TEXT NOT NULL,
    expected_value TEXT,
    actual_value TEXT,
    dashboard_source TEXT DEFAULT '',
    match_status TEXT DEFAULT 'pending',  -- pending, match, mismatch, investigating
    notes TEXT DEFAULT '',
    verified_at TEXT,
    created_at TEXT NOT NULL
);

-- Sentiment feedback
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,          -- reddit, appstore, twitter, manual, slack
    text TEXT NOT NULL,
    sentiment TEXT DEFAULT 'neutral',  -- positive, negative, neutral, mixed
    sentiment_score REAL DEFAULT 0.0,  -- -1.0 to 1.0
    topics TEXT DEFAULT '[]',     -- JSON array
    author TEXT DEFAULT '',
    url TEXT DEFAULT '',
    metadata TEXT DEFAULT '{}',
    collected_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Experiments / feature adoption
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phase TEXT DEFAULT '',         -- phase_1, phase_2, etc.
    hypothesis TEXT DEFAULT '',
    status TEXT DEFAULT 'planned', -- planned, running, analyzing, completed, killed
    start_date TEXT,
    end_date TEXT,
    platforms TEXT DEFAULT '[]',   -- JSON array
    metrics TEXT DEFAULT '{}',     -- JSON: {metric_name: {baseline, current, target}}
    statsig_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- OEM placement snapshots
CREATE TABLE IF NOT EXISTS oem_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,        -- amazon_fire, roku, samsung, lg, vizio, google_tv
    date TEXT NOT NULL,
    tubi_placement TEXT DEFAULT '{}',   -- JSON: position, prominence, section
    competitor_placements TEXT DEFAULT '{}', -- JSON: {competitor: placement}
    notes TEXT DEFAULT '',
    screenshot_path TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- Gracenote ID mappings
CREATE TABLE IF NOT EXISTS gracenote_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tubi_content_id TEXT NOT NULL,
    gracenote_id TEXT DEFAULT '',
    content_name TEXT DEFAULT '',
    content_type TEXT DEFAULT '',  -- channel, program, series
    match_status TEXT DEFAULT 'unmapped', -- mapped, unmapped, ambiguous, manual
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- PRD reviews
CREATE TABLE IF NOT EXISTS prd_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prd_id INTEGER,                -- optional link to work_items
    prd_content TEXT DEFAULT '',   -- raw PRD text that was reviewed
    reviewer TEXT DEFAULT 'ai',
    score INTEGER DEFAULT 0,       -- 1-10 readiness score
    feedback_json TEXT DEFAULT '{}', -- {gaps, risks, metrics_check, sentiment_alignment, suggestions}
    created_at TEXT NOT NULL
);

-- Feature ideas
CREATE TABLE IF NOT EXISTS feature_ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area TEXT NOT NULL,             -- epg, discovery, sports, ads, etc.
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    user_need TEXT DEFAULT '',
    competitive_advantage TEXT DEFAULT '',
    estimated_impact TEXT DEFAULT '',
    effort TEXT DEFAULT 'M',       -- S, M, L
    votes INTEGER DEFAULT 0,
    source_generation_id TEXT DEFAULT '', -- links ideas from same generation
    created_at TEXT NOT NULL
);

-- Synthesized insights
CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer_md TEXT DEFAULT '',
    citations_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);

-- Query history
CREATE TABLE IF NOT EXISTS query_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sql_text TEXT NOT NULL,
    query_name TEXT DEFAULT '',
    row_count INTEGER DEFAULT 0,
    elapsed_sec REAL DEFAULT 0,
    error TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- Change log: what happened, decisions made
CREATE TABLE IF NOT EXISTS change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,            -- decision, change, rollback, launch, finding
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    impact TEXT DEFAULT '',
    evidence TEXT DEFAULT '',      -- links, data references
    tags TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);

-- KPI cache: Databricks query results with TTL
CREATE TABLE IF NOT EXISTS kpi_cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,           -- JSON-encoded result
    fetched_at TEXT NOT NULL       -- ISO timestamp of when data was fetched
);

-- QA accuracy checks: continuous data verification
CREATE TABLE IF NOT EXISTS qa_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    expected_value TEXT DEFAULT '',
    actual_value TEXT DEFAULT '',
    match BOOLEAN DEFAULT 0,
    drift_pct REAL DEFAULT 0.0,
    error TEXT DEFAULT '',
    checked_at TEXT NOT NULL
);

-- Data source freshness tracking
CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL UNIQUE,
    last_run_at TEXT,
    last_success_at TEXT,
    last_error TEXT DEFAULT '',
    items_collected INTEGER DEFAULT 0,
    status TEXT DEFAULT 'unknown',  -- healthy, stale, error, unknown
    expected_interval_hours REAL DEFAULT 24,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Event log for monitoring
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,       -- collection, error, qa_check, worker_start, worker_complete, alert, heartbeat
    source TEXT DEFAULT '',
    message TEXT NOT NULL,
    details TEXT DEFAULT '{}',      -- JSON blob
    created_at TEXT NOT NULL
);
"""


@contextmanager
def get_db():
    """Get a database connection context manager."""
    conn = sqlite3.connect(str(HUB_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        conn.executescript(SCHEMA)


def now_iso():
    return datetime.now().isoformat()


# --- Work Items ---

def create_work_item(type: str, title: str, description: str = "", priority: str = "medium",
                     owner: str = "", tags: list = None, parent_id: int = None,
                     metadata: dict = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO work_items (type, title, description, priority, owner, tags, parent_id, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (type, title, description, priority, owner,
             json.dumps(tags or []), parent_id, json.dumps(metadata or {}),
             now_iso(), now_iso())
        )
        return cur.lastrowid


def get_work_items(status: str = None, type: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM work_items WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if type:
            query += " AND type = ?"
            params.append(type)
        query += " ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def update_work_item(id: int, **kwargs) -> bool:
    allowed = {"title", "description", "status", "priority", "owner", "tags", "metadata", "completed_at"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    if "tags" in updates and isinstance(updates["tags"], list):
        updates["tags"] = json.dumps(updates["tags"])
    if "metadata" in updates and isinstance(updates["metadata"], dict):
        updates["metadata"] = json.dumps(updates["metadata"])
    updates["updated_at"] = now_iso()
    if updates.get("status") == "done":
        updates["completed_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        conn.execute(f"UPDATE work_items SET {set_clause} WHERE id = ?",
                     list(updates.values()) + [id])
    return True


# --- Learnings ---

def create_learning(category: str, title: str, description: str, source: str = "",
                    verified: bool = False, tags: list = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO learnings (category, title, description, source, verified, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (category, title, description, source, verified,
             json.dumps(tags or []), now_iso(), now_iso())
        )
        return cur.lastrowid


def get_learnings(category: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM learnings WHERE 1=1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


# --- Data Verifications ---

def create_verification(metric_name: str, query_sql: str, expected_value: str = "",
                        actual_value: str = "", dashboard_source: str = "",
                        match_status: str = "pending", notes: str = "") -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO data_verifications (metric_name, query_sql, expected_value, actual_value,
               dashboard_source, match_status, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (metric_name, query_sql, expected_value, actual_value,
             dashboard_source, match_status, notes, now_iso())
        )
        return cur.lastrowid


def get_verifications(status: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM data_verifications WHERE 1=1"
        params = []
        if status:
            query += " AND match_status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


# --- Feedback ---

def create_feedback(source: str, text: str, sentiment: str = "neutral",
                    sentiment_score: float = 0.0, topics: list = None,
                    author: str = "", url: str = "", metadata: dict = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO feedback (source, text, sentiment, sentiment_score, topics,
               author, url, metadata, collected_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source, text, sentiment, sentiment_score,
             json.dumps(topics or []), author, url,
             json.dumps(metadata or {}), now_iso(), now_iso())
        )
        return cur.lastrowid


def get_feedback(source: str = None, sentiment: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM feedback WHERE 1=1"
        params = []
        if source:
            query += " AND source = ?"
            params.append(source)
        if sentiment:
            query += " AND sentiment = ?"
            params.append(sentiment)
        query += " ORDER BY collected_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_sentiment_summary() -> dict:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        by_sentiment = {r["sentiment"]: r["cnt"] for r in conn.execute(
            "SELECT sentiment, COUNT(*) as cnt FROM feedback GROUP BY sentiment").fetchall()}
        by_source = {r["source"]: r["cnt"] for r in conn.execute(
            "SELECT source, COUNT(*) as cnt FROM feedback GROUP BY source").fetchall()}
        avg_score = conn.execute("SELECT AVG(sentiment_score) FROM feedback").fetchone()[0] or 0
        return {
            "total": total,
            "by_sentiment": by_sentiment,
            "by_source": by_source,
            "avg_score": round(avg_score, 3),
        }


# --- Experiments ---

def create_experiment(name: str, phase: str = "", hypothesis: str = "",
                      status: str = "planned", platforms: list = None,
                      statsig_id: str = "", notes: str = "") -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO experiments (name, phase, hypothesis, status, platforms,
               statsig_id, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, phase, hypothesis, status,
             json.dumps(platforms or []), statsig_id, notes,
             now_iso(), now_iso())
        )
        return cur.lastrowid


def get_experiments(status: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM experiments WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def update_experiment(id: int, **kwargs) -> bool:
    allowed = {"name", "phase", "hypothesis", "status", "start_date", "end_date",
               "platforms", "metrics", "statsig_id", "notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    if "platforms" in updates and isinstance(updates["platforms"], list):
        updates["platforms"] = json.dumps(updates["platforms"])
    if "metrics" in updates and isinstance(updates["metrics"], dict):
        updates["metrics"] = json.dumps(updates["metrics"])
    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        conn.execute(f"UPDATE experiments SET {set_clause} WHERE id = ?",
                     list(updates.values()) + [id])
    return True


# --- OEM Snapshots ---

def create_oem_snapshot(platform: str, date: str, tubi_placement: dict = None,
                        competitor_placements: dict = None, notes: str = "",
                        screenshot_path: str = "") -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO oem_snapshots (platform, date, tubi_placement, competitor_placements,
               notes, screenshot_path, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (platform, date, json.dumps(tubi_placement or {}),
             json.dumps(competitor_placements or {}), notes, screenshot_path,
             now_iso())
        )
        return cur.lastrowid


def get_oem_snapshots(platform: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM oem_snapshots WHERE 1=1"
        params = []
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


# --- Gracenote Mappings ---

def create_gracenote_mapping(tubi_content_id: str, gracenote_id: str = "",
                              content_name: str = "", content_type: str = "",
                              match_status: str = "unmapped", notes: str = "") -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO gracenote_mappings (tubi_content_id, gracenote_id, content_name,
               content_type, match_status, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (tubi_content_id, gracenote_id, content_name, content_type,
             match_status, notes, now_iso(), now_iso())
        )
        return cur.lastrowid


def get_gracenote_mappings(status: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM gracenote_mappings WHERE 1=1"
        params = []
        if status:
            query += " AND match_status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


# --- Query History ---

def log_query(sql_text: str, query_name: str = "", row_count: int = 0,
              elapsed_sec: float = 0, error: str = "") -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO query_history (sql_text, query_name, row_count, elapsed_sec, error, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sql_text, query_name, row_count, elapsed_sec, error, now_iso())
        )
        return cur.lastrowid


def get_query_history(limit: int = 50) -> list:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM query_history ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()]


# --- Change Log ---

def create_change(type: str, title: str, description: str = "",
                  impact: str = "", evidence: str = "", tags: list = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO change_log (type, title, description, impact, evidence, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (type, title, description, impact, evidence,
             json.dumps(tags or []), now_iso())
        )
        return cur.lastrowid


def get_change_log(type: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM change_log WHERE 1=1"
        params = []
        if type:
            query += " AND type = ?"
            params.append(type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


# --- KPI Cache ---

KPI_CACHE_TTL_SECONDS = 3600  # 1 hour


def get_cached_kpi(key: str):
    """Return cached value if it exists and is within TTL, else None."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT value, fetched_at FROM kpi_cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        fetched_at = datetime.fromisoformat(row["fetched_at"])
        age = (datetime.now() - fetched_at).total_seconds()
        if age > KPI_CACHE_TTL_SECONDS:
            return None
        return json.loads(row["value"])


def set_cached_kpi(key: str, value) -> None:
    """Upsert a cache entry."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO kpi_cache (key, value, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(value, default=str), now_iso()),
        )


# --- Data Sources (Monitoring) ---

def upsert_data_source(source_name: str, status: str = "unknown",
                       last_error: str = "", items_collected: int = 0,
                       expected_interval_hours: float = 24) -> int:
    """Create or update a data source entry."""
    ts = now_iso()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM data_sources WHERE source_name = ?", (source_name,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE data_sources SET status = ?, last_run_at = ?, last_error = ?,
                   items_collected = ?, updated_at = ?
                   WHERE source_name = ?""",
                (status, ts, last_error, items_collected, ts, source_name)
            )
            if status == "healthy":
                conn.execute(
                    "UPDATE data_sources SET last_success_at = ? WHERE source_name = ?",
                    (ts, source_name)
                )
            return existing["id"]
        else:
            cur = conn.execute(
                """INSERT INTO data_sources (source_name, last_run_at, last_success_at, last_error,
                   items_collected, status, expected_interval_hours, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_name, ts, ts if status == "healthy" else None, last_error,
                 items_collected, status, expected_interval_hours, ts, ts)
            )
            return cur.lastrowid


def get_data_sources() -> list:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM data_sources ORDER BY source_name").fetchall()]


def get_data_source(source_name: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM data_sources WHERE source_name = ?", (source_name,)
        ).fetchone()
        return dict(row) if row else None


def update_data_source_status(source_name: str, status: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE data_sources SET status = ?, updated_at = ? WHERE source_name = ?",
            (status, now_iso(), source_name)
        )


# --- Event Log (Monitoring) ---

def log_event(event_type: str, message: str, source: str = "",
              details: dict = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO event_log (event_type, source, message, details, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (event_type, source, message, json.dumps(details or {}), now_iso())
        )
        return cur.lastrowid


def get_event_log(limit: int = 100, event_type: str = None) -> list:
    with get_db() as conn:
        query = "SELECT * FROM event_log WHERE 1=1"
        params = []
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_table_row_counts() -> dict:
    """Return row counts for all tables."""
    tables = ["work_items", "learnings", "data_verifications", "feedback",
              "experiments", "oem_snapshots", "gracenote_mappings", "query_history",
              "change_log", "kpi_cache", "data_sources", "event_log",
              "prd_reviews", "feature_ideas", "insights"]
    counts = {}
    with get_db() as conn:
        for t in tables:
            try:
                counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                counts[t] = 0
    return counts


# --- PRD Reviews ---

def create_prd_review(prd_id: int = None, prd_content: str = "", reviewer: str = "ai",
                      score: int = 0, feedback_json: dict = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO prd_reviews (prd_id, prd_content, reviewer, score, feedback_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (prd_id, prd_content, reviewer, score,
             json.dumps(feedback_json or {}), now_iso())
        )
        return cur.lastrowid


def get_prd_reviews(prd_id: int = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM prd_reviews WHERE 1=1"
        params = []
        if prd_id is not None:
            query += " AND prd_id = ?"
            params.append(prd_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


# --- Feature Ideas ---

def create_feature_idea(area: str, title: str, description: str = "",
                        user_need: str = "", competitive_advantage: str = "",
                        estimated_impact: str = "", effort: str = "M",
                        source_generation_id: str = "") -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO feature_ideas (area, title, description, user_need,
               competitive_advantage, estimated_impact, effort, source_generation_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (area, title, description, user_need, competitive_advantage,
             estimated_impact, effort, source_generation_id, now_iso())
        )
        return cur.lastrowid


def get_feature_ideas(area: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM feature_ideas WHERE 1=1"
        params = []
        if area:
            query += " AND area = ?"
            params.append(area)
        query += " ORDER BY votes DESC, created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def vote_feature_idea(id: int, direction: int = 1) -> int:
    """Vote on a feature idea. direction=1 for upvote, -1 for downvote."""
    with get_db() as conn:
        conn.execute("UPDATE feature_ideas SET votes = votes + ? WHERE id = ?",
                     (direction, id))
        row = conn.execute("SELECT votes FROM feature_ideas WHERE id = ?", (id,)).fetchone()
        return row["votes"] if row else 0


# --- Insights ---

def create_insight(question: str, answer_md: str = "", citations_json: list = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO insights (question, answer_md, citations_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (question, answer_md, json.dumps(citations_json or []), now_iso())
        )
        return cur.lastrowid


def get_insights(limit: int = 100) -> list:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM insights ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()]
>>>>>>> 3fe94d3 (Add knowledge engine: PRD reviewer, idea generator, insight synthesizer, weekly digest)


# Initialize on import
init_db()
