"""SQLite database for hub local state — work items, feedback, OEM snapshots, learnings, experiments."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

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


# Initialize on import
init_db()
