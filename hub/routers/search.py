"""Unified search: semantic search across all hub data."""

import json
import sys

from fastapi import APIRouter

from ..config import SCANNER_DIR
from .. import db

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/")
def unified_search(q: str, limit: int = 20):
    """Search across ChromaDB vectors, work items, learnings, feedback, and changelog."""
    results = {"query": q, "sources": {}}

    # 1. Vector memory search (ChromaDB)
    try:
        sys.path.insert(0, str(SCANNER_DIR))
        from memory import VectorMemory
        mem = VectorMemory()
        vector_results = mem.search(q, n_results=min(limit, 10))
        results["sources"]["intel_memory"] = vector_results
    except Exception as e:
        results["sources"]["intel_memory"] = {"error": str(e)}

    # 2. Search work items
    work_items = db.get_work_items(limit=200)
    q_lower = q.lower()
    matched_work = [w for w in work_items
                    if q_lower in w.get("title", "").lower()
                    or q_lower in w.get("description", "").lower()]
    results["sources"]["work_items"] = matched_work[:limit]

    # 3. Search learnings
    learnings = db.get_learnings(limit=200)
    matched_learnings = [l for l in learnings
                         if q_lower in l.get("title", "").lower()
                         or q_lower in l.get("description", "").lower()]
    results["sources"]["learnings"] = matched_learnings[:limit]

    # 4. Search feedback
    feedback = db.get_feedback(limit=500)
    matched_feedback = [f for f in feedback
                        if q_lower in f.get("text", "").lower()]
    results["sources"]["feedback"] = matched_feedback[:limit]

    # 5. Search changelog
    changelog = db.get_change_log(limit=200)
    matched_changes = [c for c in changelog
                       if q_lower in c.get("title", "").lower()
                       or q_lower in c.get("description", "").lower()]
    results["sources"]["changelog"] = matched_changes[:limit]

    return results


@router.get("/memory/stats")
def memory_stats():
    """Get ChromaDB vector memory statistics."""
    try:
        sys.path.insert(0, str(SCANNER_DIR))
        from memory import VectorMemory
        mem = VectorMemory()
        return mem.stats()
    except Exception as e:
        return {"error": str(e)}
