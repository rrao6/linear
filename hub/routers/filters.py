"""Universal filtering, classification, and sorting system for the hub.

Provides advanced filtering across all data types: sentiment/feedback,
learnings, work items, and unified cross-type search.
"""

import json
import math
from typing import Optional

from fastapi import APIRouter, Query

from .. import db

router = APIRouter(prefix="/api/filter", tags=["filters"])


def _parse_json_field(item: dict, field: str):
    """Parse a JSON string field in-place."""
    val = item.get(field)
    if isinstance(val, str):
        try:
            item[field] = json.loads(val)
        except (json.JSONDecodeError, TypeError):
            pass


def _paginate(items: list, page: int, per_page: int) -> dict:
    """Paginate a list of items and return metadata."""
    total = len(items)
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


def _text_match(text: str, query: str) -> float:
    """Simple relevance scoring: returns 0.0-1.0 based on term matching."""
    if not query or not text:
        return 0.0
    text_lower = text.lower()
    terms = query.lower().split()
    if not terms:
        return 0.0
    matched = sum(1 for t in terms if t in text_lower)
    score = matched / len(terms)
    # Boost for exact phrase match
    if query.lower() in text_lower:
        score = min(1.0, score + 0.3)
    return round(score, 3)


# ---------------------------------------------------------------------------
# GET /api/filter/sentiment — advanced sentiment/feedback filtering
# ---------------------------------------------------------------------------
@router.get("/sentiment")
def filter_sentiment(
    source: Optional[str] = None,
    sentiment: Optional[str] = None,
    topic: Optional[str] = None,
    platform: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    has_problem: Optional[bool] = None,
    sort_by: str = "date",
    order: str = "desc",
    page: int = 1,
    per_page: int = Query(default=25, le=200),
):
    # Pull a large set and filter in Python for flexibility with JSON fields
    with db.get_db() as conn:
        query = """
            SELECT f.*, e.product_areas_json, e.entities_json,
                   e.actionability_json, e.user_context_json, e.competitive_json
            FROM feedback f
            LEFT JOIN enrichments e ON f.id = e.feedback_id
            WHERE 1=1
        """
        params = []

        if source:
            query += " AND f.source = ?"
            params.append(source)
        if sentiment:
            query += " AND f.sentiment = ?"
            params.append(sentiment)
        if date_from:
            query += " AND f.collected_at >= ?"
            params.append(date_from)
        if date_to:
            query += " AND f.collected_at <= ?"
            params.append(date_to)
        if min_score is not None:
            query += " AND f.sentiment_score >= ?"
            params.append(min_score)
        if max_score is not None:
            query += " AND f.sentiment_score <= ?"
            params.append(max_score)

        query += " ORDER BY f.collected_at DESC LIMIT 2000"
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

    # Parse JSON fields
    for item in rows:
        for field in ("topics", "metadata"):
            _parse_json_field(item, field)
        for field in ("product_areas_json", "entities_json", "actionability_json",
                       "user_context_json", "competitive_json"):
            _parse_json_field(item, field)

    # Post-filter on JSON fields
    if topic:
        rows = [r for r in rows if topic in (r.get("topics") or [])]

    if platform:
        rows = [r for r in rows
                if platform in (r.get("product_areas_json") or [])]

    if has_problem is not None:
        problem_fb_ids = set()
        with db.get_db() as conn:
            pq_rows = conn.execute(
                "SELECT DISTINCT feedback_id FROM problem_quotes WHERE feedback_id IS NOT NULL"
            ).fetchall()
            problem_fb_ids = {r["feedback_id"] for r in pq_rows}
        if has_problem:
            rows = [r for r in rows if r["id"] in problem_fb_ids]
        else:
            rows = [r for r in rows if r["id"] not in problem_fb_ids]

    # Sort
    if sort_by == "score":
        rows.sort(key=lambda r: r.get("sentiment_score", 0),
                  reverse=(order == "desc"))
    elif sort_by == "relevance" and topic:
        rows.sort(key=lambda r: (
            1 if topic in (r.get("topics") or []) else 0,
            r.get("sentiment_score", 0),
        ), reverse=(order == "desc"))
    else:  # date
        rows.sort(key=lambda r: r.get("collected_at", ""),
                  reverse=(order == "desc"))

    return _paginate(rows, page, per_page)


# ---------------------------------------------------------------------------
# GET /api/filter/learnings — filter and search learnings
# ---------------------------------------------------------------------------
@router.get("/learnings")
def filter_learnings(
    category: Optional[str] = None,
    tags: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "date",
    order: str = "desc",
    page: int = 1,
    per_page: int = Query(default=25, le=200),
):
    with db.get_db() as conn:
        query = "SELECT * FROM learnings WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if date_from:
            query += " AND created_at >= ?"
            params.append(date_from)
        if date_to:
            query += " AND created_at <= ?"
            params.append(date_to)

        query += " ORDER BY created_at DESC LIMIT 2000"
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

    for item in rows:
        _parse_json_field(item, "tags")

    # Tag filter (comma-separated)
    if tags:
        tag_set = {t.strip().lower() for t in tags.split(",") if t.strip()}
        rows = [r for r in rows
                if tag_set & {t.lower() for t in (r.get("tags") or [])}]

    # Full-text search
    if search:
        scored = []
        for r in rows:
            text = f"{r.get('title', '')} {r.get('description', '')} {r.get('source', '')}"
            score = _text_match(text, search)
            if score > 0:
                r["_relevance"] = score
                scored.append(r)
        rows = scored

    # Sort
    if sort_by == "category":
        rows.sort(key=lambda r: r.get("category", ""),
                  reverse=(order == "desc"))
    elif sort_by == "title":
        rows.sort(key=lambda r: r.get("title", "").lower(),
                  reverse=(order == "desc"))
    elif search and sort_by == "relevance":
        rows.sort(key=lambda r: r.get("_relevance", 0), reverse=True)
    else:  # date
        rows.sort(key=lambda r: r.get("created_at", ""),
                  reverse=(order == "desc"))

    # Build category counts from full (pre-paginate) result set
    category_counts = {}
    for r in rows:
        cat = r.get("category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    result = _paginate(rows, page, per_page)
    result["category_counts"] = category_counts
    return result


# ---------------------------------------------------------------------------
# GET /api/filter/work — advanced work queue filtering
# ---------------------------------------------------------------------------
@router.get("/work")
def filter_work(
    type: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    owner: Optional[str] = None,
    tags: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: str = "priority",
    order: str = "desc",
    page: int = 1,
    per_page: int = Query(default=25, le=200),
):
    with db.get_db() as conn:
        query = "SELECT * FROM work_items WHERE 1=1"
        params = []

        if type:
            query += " AND type = ?"
            params.append(type)
        if status:
            query += " AND status = ?"
            params.append(status)
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        if owner:
            query += " AND owner = ?"
            params.append(owner)
        if date_from:
            query += " AND created_at >= ?"
            params.append(date_from)
        if date_to:
            query += " AND created_at <= ?"
            params.append(date_to)

        query += " ORDER BY created_at DESC LIMIT 2000"
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

    for item in rows:
        _parse_json_field(item, "tags")
        _parse_json_field(item, "metadata")

    # Tag filter
    if tags:
        tag_set = {t.strip().lower() for t in tags.split(",") if t.strip()}
        rows = [r for r in rows
                if tag_set & {t.lower() for t in (r.get("tags") or [])}]

    # Sort
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    if sort_by == "priority":
        rows.sort(key=lambda r: priority_order.get(r.get("priority", "medium"), 2),
                  reverse=(order == "desc"))
    elif sort_by == "type":
        rows.sort(key=lambda r: r.get("type", ""),
                  reverse=(order == "desc"))
    else:  # date
        rows.sort(key=lambda r: r.get("created_at", ""),
                  reverse=(order == "desc"))

    # Facet counts from full result set
    facets = {"by_type": {}, "by_status": {}, "by_priority": {}}
    for r in rows:
        t = r.get("type", "unknown")
        s = r.get("status", "unknown")
        p = r.get("priority", "unknown")
        facets["by_type"][t] = facets["by_type"].get(t, 0) + 1
        facets["by_status"][s] = facets["by_status"].get(s, 0) + 1
        facets["by_priority"][p] = facets["by_priority"].get(p, 0) + 1

    result = _paginate(rows, page, per_page)
    result["facets"] = facets
    return result


# ---------------------------------------------------------------------------
# GET /api/filter/all — unified search across everything
# ---------------------------------------------------------------------------
@router.get("/all")
def filter_all(
    q: str = "",
    page: int = 1,
    per_page: int = Query(default=10, le=50),
):
    if not q.strip():
        return {"sentiment": [], "learnings": [], "work_items": [], "experiments": []}

    query_text = q.strip()

    # Search feedback
    feedback_items = []
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY collected_at DESC LIMIT 1000"
        ).fetchall()
        for r in rows:
            item = dict(r)
            _parse_json_field(item, "topics")
            _parse_json_field(item, "metadata")
            score = _text_match(
                f"{item.get('text', '')} {' '.join(item.get('topics') or [])}",
                query_text,
            )
            if score > 0:
                item["relevance"] = score
                item["_type"] = "sentiment"
                feedback_items.append(item)
    feedback_items.sort(key=lambda x: x["relevance"], reverse=True)

    # Search learnings
    learning_items = []
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM learnings ORDER BY created_at DESC LIMIT 1000"
        ).fetchall()
        for r in rows:
            item = dict(r)
            _parse_json_field(item, "tags")
            score = _text_match(
                f"{item.get('title', '')} {item.get('description', '')}",
                query_text,
            )
            if score > 0:
                item["relevance"] = score
                item["_type"] = "learning"
                learning_items.append(item)
    learning_items.sort(key=lambda x: x["relevance"], reverse=True)

    # Search work items
    work_items = []
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM work_items ORDER BY created_at DESC LIMIT 1000"
        ).fetchall()
        for r in rows:
            item = dict(r)
            _parse_json_field(item, "tags")
            _parse_json_field(item, "metadata")
            score = _text_match(
                f"{item.get('title', '')} {item.get('description', '')}",
                query_text,
            )
            if score > 0:
                item["relevance"] = score
                item["_type"] = "work_item"
                work_items.append(item)
    work_items.sort(key=lambda x: x["relevance"], reverse=True)

    # Search experiments
    experiment_items = []
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM experiments ORDER BY updated_at DESC LIMIT 1000"
        ).fetchall()
        for r in rows:
            item = dict(r)
            _parse_json_field(item, "platforms")
            _parse_json_field(item, "metrics")
            score = _text_match(
                f"{item.get('name', '')} {item.get('hypothesis', '')} {item.get('notes', '')}",
                query_text,
            )
            if score > 0:
                item["relevance"] = score
                item["_type"] = "experiment"
                experiment_items.append(item)
    experiment_items.sort(key=lambda x: x["relevance"], reverse=True)

    limit = int(per_page)
    return {
        "sentiment": feedback_items[:limit],
        "learnings": learning_items[:limit],
        "work_items": work_items[:limit],
        "experiments": experiment_items[:limit],
        "total_matches": (len(feedback_items) + len(learning_items)
                          + len(work_items) + len(experiment_items)),
    }


# ---------------------------------------------------------------------------
# GET /api/taxonomy — all available filter values for frontend dropdowns
# ---------------------------------------------------------------------------
@router.get("/taxonomy", tags=["filters"])
def get_taxonomy():
    with db.get_db() as conn:
        sources = [r[0] for r in conn.execute(
            "SELECT DISTINCT source FROM feedback WHERE source != '' ORDER BY source"
        ).fetchall()]

        sentiments = [r[0] for r in conn.execute(
            "SELECT DISTINCT sentiment FROM feedback ORDER BY sentiment"
        ).fetchall()]

        # Collect all topics from JSON arrays
        topic_rows = conn.execute(
            "SELECT topics FROM feedback WHERE topics != '[]'"
        ).fetchall()
        topic_set = set()
        for r in topic_rows:
            try:
                topics = json.loads(r[0]) if isinstance(r[0], str) else r[0]
                if isinstance(topics, list):
                    topic_set.update(topics)
            except (json.JSONDecodeError, TypeError):
                pass

        categories = [r[0] for r in conn.execute(
            "SELECT DISTINCT category FROM learnings WHERE category != '' ORDER BY category"
        ).fetchall()]

        work_types = [r[0] for r in conn.execute(
            "SELECT DISTINCT type FROM work_items WHERE type != '' ORDER BY type"
        ).fetchall()]

        work_statuses = [r[0] for r in conn.execute(
            "SELECT DISTINCT status FROM work_items ORDER BY status"
        ).fetchall()]

        priorities = [r[0] for r in conn.execute(
            "SELECT DISTINCT priority FROM work_items WHERE priority != '' ORDER BY priority"
        ).fetchall()]

        owners = [r[0] for r in conn.execute(
            "SELECT DISTINCT owner FROM work_items WHERE owner != '' ORDER BY owner"
        ).fetchall()]

        # Platforms from enrichments product_areas
        pa_rows = conn.execute(
            "SELECT product_areas_json FROM enrichments WHERE product_areas_json != '[]'"
        ).fetchall()
        platform_set = set()
        for r in pa_rows:
            try:
                areas = json.loads(r[0]) if isinstance(r[0], str) else r[0]
                if isinstance(areas, list):
                    platform_set.update(areas)
            except (json.JSONDecodeError, TypeError):
                pass

        experiment_statuses = [r[0] for r in conn.execute(
            "SELECT DISTINCT status FROM experiments ORDER BY status"
        ).fetchall()]

    return {
        "sources": sources,
        "sentiments": sentiments,
        "topics": sorted(topic_set),
        "categories": categories,
        "work_types": work_types,
        "work_statuses": work_statuses,
        "priorities": priorities,
        "owners": owners,
        "platforms": sorted(platform_set),
        "experiment_statuses": experiment_statuses,
    }
