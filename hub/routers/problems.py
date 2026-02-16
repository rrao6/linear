"""Problem detection and clustering API routes."""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional

from .. import db
from ..problem_engine import detect_and_cluster, extract_problem, get_embedding, cosine_similarity, CLUSTER_THRESHOLD, score_problem_group

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/problems", tags=["problems"])


# --- Pydantic Models ---

class ProblemLink(BaseModel):
    work_item_id: Optional[int] = None
    experiment_id: Optional[int] = None
    status: str = "linked"


# --- Helper Functions ---

def _parse_json_field(item: dict, field: str) -> dict:
    """Parse a JSON string field in-place."""
    val = item.get(field)
    if isinstance(val, str) and val:
        try:
            item[field] = json.loads(val)
        except (json.JSONDecodeError, TypeError):
            pass
    return item


def _enrich_problem(p: dict) -> dict:
    """Parse JSON fields on a problem dict for API response."""
    _parse_json_field(p, "platforms_json")
    # Don't send raw embedding to clients
    p.pop("embedding_json", None)
    return p


def _run_detection():
    """Background task: detect problems from unprocessed feedback."""
    unprocessed = db.get_unprocessed_feedback(limit=500)
    if not unprocessed:
        logger.info("No unprocessed feedback to detect problems from")
        return {"new_problems": 0, "updated_problems": 0, "processed": 0}

    # Run extraction and clustering
    groups = detect_and_cluster(unprocessed)

    # Load existing problems for matching
    existing = db.get_problems(limit=1000)
    existing_embeddings = []
    for ep in existing:
        emb_str = ep.get("embedding_json", "")
        if isinstance(emb_str, str) and emb_str:
            try:
                emb = json.loads(emb_str)
                if emb:
                    existing_embeddings.append((ep, emb))
            except (json.JSONDecodeError, TypeError):
                pass

    new_count = 0
    updated_count = 0

    for group in groups:
        embedding = group.get("embedding", [])
        members = group.get("members", [])

        # Check if this matches an existing problem
        matched_existing = None
        if embedding and existing_embeddings:
            for ep, ep_emb in existing_embeddings:
                sim = cosine_similarity(embedding, ep_emb)
                if sim >= CLUSTER_THRESHOLD:
                    matched_existing = ep
                    break

        if matched_existing:
            # Update existing problem
            pid = matched_existing["id"]
            new_count_val = matched_existing.get("count", 0) + group["count"]
            db.update_problem(
                pid,
                count=new_count_val,
                last_seen=group["last_seen"],
                trend=group["trend"],
                score=score_problem_group({
                    **group,
                    "count": new_count_val,
                }),
            )
            # Add new quotes
            for m in members:
                db.create_problem_quote(
                    problem_id=pid,
                    quote_text=m.get("quote_text", m.get("problem", "")),
                    feedback_id=m.get("feedback_id"),
                    source=m.get("source", ""),
                )
            updated_count += 1
        else:
            # Create new problem
            pid = db.create_problem(
                title=group["title"],
                description=group.get("description", ""),
                area=group.get("area", ""),
                journey_stage=group.get("journey_stage", ""),
                severity=group.get("severity", "annoying"),
                count=group["count"],
                platforms=group.get("platforms", []),
                first_seen=group.get("first_seen", ""),
                last_seen=group.get("last_seen", ""),
                trend=group.get("trend", "stable"),
                score=group.get("score", 0),
                embedding=embedding,
            )
            # Add quotes
            for m in members:
                db.create_problem_quote(
                    problem_id=pid,
                    quote_text=m.get("quote_text", m.get("problem", "")),
                    feedback_id=m.get("feedback_id"),
                    source=m.get("source", ""),
                )
            new_count += 1

    return {
        "new_problems": new_count,
        "updated_problems": updated_count,
        "processed": len(unprocessed),
    }


# --- Endpoints ---

@router.get("")
def list_problems(area: str = None, journey_stage: str = None,
                  severity: str = None, limit: int = 100):
    """Ranked list of problem groups with all metadata."""
    problems = db.get_problems(area=area, journey_stage=journey_stage,
                               severity=severity, limit=limit)
    for p in problems:
        _enrich_problem(p)
        p["quotes"] = db.get_problem_quotes(p["id"], limit=3)
        p["links"] = db.get_problem_links(p["id"])
    return problems


@router.get("/by-area")
def problems_by_area():
    """Problems grouped by product area."""
    all_problems = db.get_problems(limit=500)
    by_area = {}
    for p in all_problems:
        _enrich_problem(p)
        area = p.get("area", "unknown")
        if area not in by_area:
            by_area[area] = {"area": area, "problems": [], "total_count": 0, "top_severity": "cosmetic"}
        by_area[area]["problems"].append(p)
        by_area[area]["total_count"] += p.get("count", 0)
        # Track worst severity
        sev_order = {"blocking": 0, "degraded": 1, "annoying": 2, "cosmetic": 3}
        current_worst = sev_order.get(by_area[area]["top_severity"], 3)
        this_sev = sev_order.get(p.get("severity", "cosmetic"), 3)
        if this_sev < current_worst:
            by_area[area]["top_severity"] = p.get("severity", "cosmetic")

    result = sorted(by_area.values(), key=lambda x: x["total_count"], reverse=True)
    return result


@router.get("/by-journey")
def problems_by_journey():
    """Problems grouped by user journey stage."""
    all_problems = db.get_problems(limit=500)
    by_stage = {}
    for p in all_problems:
        _enrich_problem(p)
        stage = p.get("journey_stage", "unknown")
        if stage not in by_stage:
            by_stage[stage] = {"journey_stage": stage, "problems": [], "total_count": 0}
        by_stage[stage]["problems"].append(p)
        by_stage[stage]["total_count"] += p.get("count", 0)

    # Order by journey flow
    stage_order = {"discovery": 0, "browsing": 1, "channel_switching": 2, "playback": 3, "returning": 4}
    result = sorted(by_stage.values(), key=lambda x: stage_order.get(x["journey_stage"], 99))
    return result


@router.get("/unaddressed")
def unaddressed_problems(limit: int = 100):
    """Problems with no linked work items — the gap."""
    problems = db.get_unaddressed_problems(limit=limit)
    for p in problems:
        _enrich_problem(p)
        p["quotes"] = db.get_problem_quotes(p["id"], limit=3)
    return problems


@router.get("/{problem_id}")
def get_problem(problem_id: int):
    """Single problem with all related quotes, timeline, and linked work items."""
    p = db.get_problem(problem_id)
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")
    _enrich_problem(p)
    p["quotes"] = db.get_problem_quotes(problem_id, limit=50)
    p["links"] = db.get_problem_links(problem_id)

    # Enrich links with work item / experiment details
    for link in p["links"]:
        if link.get("work_item_id"):
            items = db.get_work_items(limit=1)
            # Direct lookup
            with db.get_db() as conn:
                row = conn.execute("SELECT * FROM work_items WHERE id = ?",
                                   (link["work_item_id"],)).fetchone()
                if row:
                    link["work_item"] = dict(row)
        if link.get("experiment_id"):
            with db.get_db() as conn:
                row = conn.execute("SELECT * FROM experiments WHERE id = ?",
                                   (link["experiment_id"],)).fetchone()
                if row:
                    link["experiment"] = dict(row)

    return p


@router.post("/detect")
def detect_problems(background_tasks: BackgroundTasks):
    """Run detection on all unprocessed feedback. Returns immediately, runs in background."""
    # Check how many unprocessed items there are
    unprocessed = db.get_unprocessed_feedback(limit=1)
    if not unprocessed:
        return {"status": "no_unprocessed_feedback", "message": "All feedback has been processed"}

    # For small batches, run synchronously; for large, use background
    total_unprocessed = len(db.get_unprocessed_feedback(limit=500))
    if total_unprocessed <= 10:
        result = _run_detection()
        return {"status": "completed", **result}
    else:
        background_tasks.add_task(_run_detection)
        return {
            "status": "started",
            "message": f"Processing {total_unprocessed} feedback items in background",
        }


@router.post("/link/{problem_id}")
def link_problem(problem_id: int, link: ProblemLink):
    """Link a problem to a work item or experiment."""
    p = db.get_problem(problem_id)
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")
    if not link.work_item_id and not link.experiment_id:
        raise HTTPException(status_code=400, detail="Must provide work_item_id or experiment_id")

    link_id = db.create_problem_link(
        problem_id=problem_id,
        work_item_id=link.work_item_id,
        experiment_id=link.experiment_id,
        status=link.status,
    )
    return {"id": link_id, "problem_id": problem_id}
