"""SQLite database for hub local state — work items, feedback, OEM snapshots, learnings, experiments."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

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

-- Generated PRDs
CREATE TABLE IF NOT EXISTS prds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    content_md TEXT NOT NULL,
    status TEXT DEFAULT 'draft',   -- draft, reviewed, approved
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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

-- AI-generated insights
CREATE TABLE IF NOT EXISTS ai_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,            -- sentiment_trends, competitive_position, data_anomalies, weekly_brief, experiments
    content_json TEXT NOT NULL,    -- JSON blob with structured analysis
    created_at TEXT NOT NULL
);

-- Problem groups: clustered user problems detected from feedback
CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    area TEXT DEFAULT '',
    journey_stage TEXT DEFAULT '',
    severity TEXT DEFAULT 'annoying',
    count INTEGER DEFAULT 0,
    platforms_json TEXT DEFAULT '[]',
    first_seen TEXT,
    last_seen TEXT,
    trend TEXT DEFAULT 'stable',
    score REAL DEFAULT 0.0,
    embedding_json TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Problem quotes: individual feedback items linked to a problem group
CREATE TABLE IF NOT EXISTS problem_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id INTEGER NOT NULL,
    feedback_id INTEGER,
    quote_text TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (problem_id) REFERENCES problems(id)
);

-- Problem links: connect problems to work items or experiments
CREATE TABLE IF NOT EXISTS problem_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id INTEGER NOT NULL,
    work_item_id INTEGER,
    experiment_id INTEGER,
    status TEXT DEFAULT 'linked',
    created_at TEXT NOT NULL,
    FOREIGN KEY (problem_id) REFERENCES problems(id),
    FOREIGN KEY (work_item_id) REFERENCES work_items(id),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);

-- Feedback enrichments: AI-extracted metadata
CREATE TABLE IF NOT EXISTS enrichments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id INTEGER NOT NULL UNIQUE,
    entities_json TEXT DEFAULT '{}',
    user_context_json TEXT DEFAULT '{}',
    product_areas_json TEXT DEFAULT '[]',
    actionability_json TEXT DEFAULT '{}',
    competitive_json TEXT DEFAULT 'null',
    enriched_at TEXT NOT NULL,
    FOREIGN KEY (feedback_id) REFERENCES feedback(id)
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


def delete_work_item(id: int) -> bool:
    with get_db() as conn:
        conn.execute("DELETE FROM work_items WHERE id = ?", (id,))
    return True


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


def deduplicate_experiments() -> int:
    """Remove duplicate experiments by name, keeping the one with lowest rowid."""
    with get_db() as conn:
        dupes = conn.execute(
            """SELECT COUNT(*) - COUNT(DISTINCT name) AS dupe_count FROM experiments"""
        ).fetchone()[0]
        if dupes > 0:
            conn.execute(
                """DELETE FROM experiments WHERE rowid NOT IN
                   (SELECT MIN(rowid) FROM experiments GROUP BY name)"""
            )
        return dupes


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


def update_gracenote_mapping(id: int, **kwargs) -> bool:
    allowed = {"gracenote_id", "content_name", "content_type", "match_status", "notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        conn.execute(f"UPDATE gracenote_mappings SET {set_clause} WHERE id = ?",
                     list(updates.values()) + [id])
    return True


def delete_gracenote_mapping(id: int) -> bool:
    with get_db() as conn:
        conn.execute("DELETE FROM gracenote_mappings WHERE id = ?", (id,))
    return True


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


# --- PRDs ---

def create_prd(topic: str, content_md: str, status: str = "draft") -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO prds (topic, content_md, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (topic, content_md, status, now_iso(), now_iso())
        )
        return cur.lastrowid

# --- AI Insights ---

def save_insight(type: str, content: dict) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO ai_insights (type, content_json, created_at) VALUES (?, ?, ?)",
            (type, json.dumps(content, default=str), now_iso()),
        )
        return cur.lastrowid


def get_prds(status: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM prds WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_prd(id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM prds WHERE id = ?", (id,)).fetchone()
        return dict(row) if row else None


def update_prd(id: int, **kwargs) -> bool:
    allowed = {"topic", "content_md", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        conn.execute(f"UPDATE prds SET {set_clause} WHERE id = ?",
                     list(updates.values()) + [id])
    return True


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


# --- Enrichments ---

def create_enrichment(feedback_id: int, entities: dict, user_context: dict,
                      product_areas: list, actionability: dict,
                      competitive_mention=None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT OR REPLACE INTO enrichments
               (feedback_id, entities_json, user_context_json, product_areas_json,
                actionability_json, competitive_json, enriched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (feedback_id, json.dumps(entities), json.dumps(user_context),
             json.dumps(product_areas), json.dumps(actionability),
             json.dumps(competitive_mention), now_iso())
        )
        return cur.lastrowid


def get_enrichment(feedback_id: int) -> "dict | None":
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM enrichments WHERE feedback_id = ?", (feedback_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for col in ("entities_json", "user_context_json", "product_areas_json",
                     "actionability_json", "competitive_json"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        return d


def get_unenriched_feedback_ids(limit: int = 500) -> list:
    """Return feedback IDs that have no enrichment record."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT f.id FROM feedback f
               LEFT JOIN enrichments e ON f.id = e.feedback_id
               WHERE e.id IS NULL
               ORDER BY f.created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        return [r["id"] for r in rows]


def get_feedback_by_id(feedback_id: int) -> "dict | None":
    with get_db() as conn:
        row = conn.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("topics"), str):
            d["topics"] = json.loads(d["topics"])
        if isinstance(d.get("metadata"), str):
            d["metadata"] = json.loads(d["metadata"])
        return d


def get_feedback_by_product_area(area: str = None, limit: int = 200) -> list:
    """Get feedback grouped by product area from enrichments."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT f.*, e.product_areas_json, e.entities_json, e.actionability_json,
                      e.user_context_json, e.competitive_json
               FROM feedback f
               JOIN enrichments e ON f.id = e.feedback_id
               ORDER BY f.collected_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            areas = json.loads(d.get("product_areas_json", "[]"))
            if area and area not in areas:
                continue
            for col in ("topics", "metadata"):
                if isinstance(d.get(col), str):
                    d[col] = json.loads(d[col])
            for col in ("product_areas_json", "entities_json", "actionability_json",
                         "user_context_json", "competitive_json"):
                if isinstance(d.get(col), str):
                    d[col] = json.loads(d[col])
            results.append(d)
        return results


def get_feedback_by_competitor(limit: int = 200) -> list:
    """Get all feedback with competitive mentions."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT f.*, e.competitive_json, e.entities_json, e.actionability_json,
                      e.product_areas_json
               FROM feedback f
               JOIN enrichments e ON f.id = e.feedback_id
               WHERE e.competitive_json IS NOT NULL AND e.competitive_json != 'null'
               ORDER BY f.collected_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            for col in ("topics", "metadata"):
                if isinstance(d.get(col), str):
                    d[col] = json.loads(d[col])
            for col in ("competitive_json", "entities_json", "actionability_json",
                         "product_areas_json"):
                if isinstance(d.get(col), str):
                    d[col] = json.loads(d[col])
            results.append(d)
        return results


def get_churn_risks(limit: int = 100) -> list:
    """Get feedback flagged as churn risk, most recent first."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT f.*, e.actionability_json, e.entities_json, e.product_areas_json,
                      e.user_context_json, e.competitive_json
               FROM feedback f
               JOIN enrichments e ON f.id = e.feedback_id
               WHERE json_extract(e.actionability_json, '$.is_churn_risk') = 1
               ORDER BY f.collected_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            for col in ("topics", "metadata"):
                if isinstance(d.get(col), str):
                    d[col] = json.loads(d[col])
            for col in ("actionability_json", "entities_json", "product_areas_json",
                         "user_context_json", "competitive_json"):
                if isinstance(d.get(col), str):
                    d[col] = json.loads(d[col])
            results.append(d)
        return results


def get_feature_requests(limit: int = 100) -> list:
    """Get feedback flagged as feature requests."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT f.*, e.actionability_json, e.entities_json, e.product_areas_json,
                      e.user_context_json
               FROM feedback f
               JOIN enrichments e ON f.id = e.feedback_id
               WHERE json_extract(e.actionability_json, '$.is_feature_request') = 1
               ORDER BY f.collected_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            for col in ("topics", "metadata"):
                if isinstance(d.get(col), str):
                    d[col] = json.loads(d[col])
            for col in ("actionability_json", "entities_json", "product_areas_json",
                         "user_context_json"):
                if isinstance(d.get(col), str):
                    d[col] = json.loads(d[col])
            results.append(d)
        return results


def get_table_row_counts() -> dict:
    """Return row counts for all tables."""
    tables = ["work_items", "learnings", "data_verifications", "feedback",
              "experiments", "oem_snapshots", "gracenote_mappings", "query_history",
              "change_log", "kpi_cache", "data_sources", "event_log",
              "prd_reviews", "feature_ideas", "insights", "enrichments",
              "ai_insights", "problems", "problem_quotes", "problem_links"]
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


def get_latest_ai_insight(type: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM ai_insights WHERE type = ? ORDER BY created_at DESC LIMIT 1",
            (type,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["content_json"] = json.loads(result["content_json"])
        return result


def get_ai_insights(type: str = None, limit: int = 20) -> list:
    with get_db() as conn:
        query = "SELECT * FROM ai_insights WHERE 1=1"
        params = []
        if type:
            query += " AND type = ?"
            params.append(type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        for r in rows:
            r["content_json"] = json.loads(r["content_json"])
        return rows


# --- Ask (NL Query) ---

def log_ask(question: str, sql: str, error: str = "", elapsed_sec: float = 0.0,
            rows: int = 0, summary: str = "", results: list = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO query_history (sql_text, query_name, row_count, elapsed_sec, error, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sql, question, rows, elapsed_sec, error, now_iso()),
        )
        return cur.lastrowid


def get_ask_history(limit: int = 50) -> list:
    return get_query_history(limit=limit)


# --- Problems ---

def create_problem(title: str, description: str = "", area: str = "",
                   journey_stage: str = "", severity: str = "annoying",
                   count: int = 0, platforms: list = None,
                   first_seen: str = "", last_seen: str = "",
                   trend: str = "stable", score: float = 0.0,
                   embedding: list = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO problems (title, description, area, journey_stage, severity,
               count, platforms_json, first_seen, last_seen, trend, score, embedding_json,
               created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, area, journey_stage, severity,
             count, json.dumps(platforms or []),
             first_seen or now_iso(), last_seen or now_iso(),
             trend, score, json.dumps(embedding or []),
             now_iso(), now_iso())
        )
        return cur.lastrowid


def get_problems(area: str = None, journey_stage: str = None,
                 severity: str = None, limit: int = 100) -> list:
    with get_db() as conn:
        query = "SELECT * FROM problems WHERE 1=1"
        params = []
        if area:
            query += " AND area = ?"
            params.append(area)
        if journey_stage:
            query += " AND journey_stage = ?"
            params.append(journey_stage)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY score DESC, count DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_problem(id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM problems WHERE id = ?", (id,)).fetchone()
        return dict(row) if row else None


def update_problem(id: int, **kwargs) -> bool:
    allowed = {"title", "description", "area", "journey_stage", "severity",
               "count", "platforms_json", "first_seen", "last_seen", "trend",
               "score", "embedding_json"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        conn.execute(f"UPDATE problems SET {set_clause} WHERE id = ?",
                     list(updates.values()) + [id])
    return True


def create_problem_quote(problem_id: int, quote_text: str,
                         feedback_id: int = None, source: str = "") -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO problem_quotes (problem_id, feedback_id, quote_text, source, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (problem_id, feedback_id, quote_text, source, now_iso())
        )
        return cur.lastrowid


def get_problem_quotes(problem_id: int, limit: int = 50) -> list:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM problem_quotes WHERE problem_id = ? ORDER BY created_at DESC LIMIT ?",
            (problem_id, limit)).fetchall()]


def create_problem_link(problem_id: int, work_item_id: int = None,
                        experiment_id: int = None, status: str = "linked") -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO problem_links (problem_id, work_item_id, experiment_id, status, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (problem_id, work_item_id, experiment_id, status, now_iso())
        )
        return cur.lastrowid


def get_problem_links(problem_id: int) -> list:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM problem_links WHERE problem_id = ?", (problem_id,)).fetchall()]


def get_unaddressed_problems(limit: int = 100) -> list:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT p.* FROM problems p
               LEFT JOIN problem_links pl ON p.id = pl.problem_id
               WHERE pl.id IS NULL
               ORDER BY p.score DESC, p.count DESC
               LIMIT ?""",
            (limit,)).fetchall()]


def get_processed_feedback_ids() -> set:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT feedback_id FROM problem_quotes WHERE feedback_id IS NOT NULL"
        ).fetchall()
        return {r["feedback_id"] for r in rows}


def get_unprocessed_feedback(limit: int = 500) -> list:
    processed_ids = get_processed_feedback_ids()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY collected_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows if r["id"] not in processed_ids]


# Initialize on import
init_db()
