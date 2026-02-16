"""Strategy workspace: PRDs, decisions, work items, learnings, change log."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db
from ..config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


# --- Work Items ---

class WorkItemCreate(BaseModel):
    type: str = "task"
    title: str
    description: str = ""
    priority: str = "medium"
    owner: str = ""
    tags: list = []
    parent_id: Optional[int] = None
    metadata: dict = {}


class WorkItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[list] = None
    metadata: Optional[dict] = None


@router.get("/work")
def list_work(status: Optional[str] = None, type: Optional[str] = None, limit: int = 100):
    """List work items."""
    items = db.get_work_items(status=status, type=type, limit=limit)
    for item in items:
        for field in ("tags", "metadata"):
            if isinstance(item.get(field), str):
                item[field] = json.loads(item[field])
    return items


@router.post("/work")
def create_work(w: WorkItemCreate):
    """Create a work item."""
    id = db.create_work_item(
        type=w.type, title=w.title, description=w.description,
        priority=w.priority, owner=w.owner, tags=w.tags,
        parent_id=w.parent_id, metadata=w.metadata,
    )
    return {"id": id}


@router.put("/work/{item_id}")
def update_work(item_id: int, update: WorkItemUpdate):
    """Update a work item."""
    kwargs = {k: v for k, v in update.model_dump().items() if v is not None}
    db.update_work_item(item_id, **kwargs)
    return {"updated": True}


@router.delete("/work/{item_id}")
def delete_work(item_id: int):
    """Delete a work item."""
    db.delete_work_item(item_id)
    return {"deleted": True}


# --- Learnings ---

class LearningCreate(BaseModel):
    category: str
    title: str
    description: str
    source: str = ""
    verified: bool = False
    tags: list = []


@router.get("/learnings")
def list_learnings(category: Optional[str] = None, limit: int = 100):
    """List learnings."""
    items = db.get_learnings(category=category, limit=limit)
    for item in items:
        if isinstance(item.get("tags"), str):
            item["tags"] = json.loads(item["tags"])
    return items


@router.post("/learnings")
def create_learning(l: LearningCreate):
    """Record a learning."""
    id = db.create_learning(
        category=l.category, title=l.title, description=l.description,
        source=l.source, verified=l.verified, tags=l.tags,
    )
    return {"id": id}


# --- Data Verifications ---

class VerificationCreate(BaseModel):
    metric_name: str
    query_sql: str
    expected_value: str = ""
    actual_value: str = ""
    dashboard_source: str = ""
    match_status: str = "pending"
    notes: str = ""


@router.get("/verifications")
def list_verifications(status: Optional[str] = None, limit: int = 100):
    """List data verifications."""
    return db.get_verifications(status=status, limit=limit)


@router.post("/verifications")
def create_verification(v: VerificationCreate):
    """Create a data verification."""
    id = db.create_verification(
        metric_name=v.metric_name, query_sql=v.query_sql,
        expected_value=v.expected_value, actual_value=v.actual_value,
        dashboard_source=v.dashboard_source, match_status=v.match_status,
        notes=v.notes,
    )
    return {"id": id}


# --- Change Log ---

class ChangeCreate(BaseModel):
    type: str
    title: str
    description: str = ""
    impact: str = ""
    evidence: str = ""
    tags: list = []


@router.get("/changelog")
def list_changes(type: Optional[str] = None, limit: int = 100):
    """List change log entries."""
    items = db.get_change_log(type=type, limit=limit)
    for item in items:
        if isinstance(item.get("tags"), str):
            item["tags"] = json.loads(item["tags"])
    return items


@router.post("/changelog")
def create_change(c: ChangeCreate):
    """Record a change."""
    id = db.create_change(
        type=c.type, title=c.title, description=c.description,
        impact=c.impact, evidence=c.evidence, tags=c.tags,
    )
    return {"id": id}


# --- PRD Generator ---

class PRDRequest(BaseModel):
    topic: str
    context: str = ""


class PRDUpdate(BaseModel):
    status: Optional[str] = None
    content_md: Optional[str] = None


def _gather_hub_context(topic: str) -> dict:
    """Pull all relevant context from the hub for PRD generation."""
    # Sentiment topics — what users complain/talk about most
    feedback_items = db.get_feedback(limit=200)
    topic_counts = {}
    for item in feedback_items:
        topics = item.get("topics", "[]")
        if isinstance(topics, str):
            topics = json.loads(topics)
        for t in topics:
            topic_counts[t] = topic_counts.get(t, 0) + 1
    sorted_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:15]
    sentiment_summary = db.get_sentiment_summary()

    # Grab actual negative feedback quotes for context
    negative_feedback = [
        f for f in feedback_items
        if f.get("sentiment") == "negative"
    ][:10]

    # Competitive threats — from latest intel scan
    from .intel import get_threats, get_opportunities
    threats = get_threats()
    opportunities = get_opportunities()

    # Current metrics from dashboard
    from .dashboard import get_overview, get_goals
    overview = get_overview()
    goals = get_goals()

    # Open work items
    work_items = db.get_work_items(status="open", limit=20)
    in_progress = db.get_work_items(status="in_progress", limit=20)

    # Experiment results
    experiments = db.get_experiments(limit=20)
    for exp in experiments:
        for field in ("platforms", "metrics"):
            if isinstance(exp.get(field), str):
                exp[field] = json.loads(exp[field])

    # Learnings
    learnings = db.get_learnings(limit=20)

    # Verifications
    verifications = db.get_verifications(limit=10)

    return {
        "topic": topic,
        "sentiment_topics": sorted_topics,
        "sentiment_summary": sentiment_summary,
        "negative_feedback": [
            {"text": f["text"], "source": f["source"], "score": f.get("sentiment_score")}
            for f in negative_feedback
        ],
        "threats": threats[:10] if isinstance(threats, list) else [],
        "opportunities": opportunities[:10] if isinstance(opportunities, list) else [],
        "kpis": overview.get("kpis", {}),
        "goals": goals,
        "work_open": [{"title": w["title"], "type": w["type"], "priority": w["priority"]} for w in work_items[:10]],
        "work_in_progress": [{"title": w["title"], "type": w["type"]} for w in in_progress[:10]],
        "experiments": [
            {"name": e["name"], "status": e["status"], "hypothesis": e.get("hypothesis", ""),
             "metrics": e.get("metrics", {})}
            for e in experiments[:10]
        ],
        "learnings": [
            {"title": l["title"], "category": l["category"], "description": l["description"][:200]}
            for l in learnings[:10]
        ],
        "verifications": [
            {"metric": v["metric_name"], "expected": v["expected_value"],
             "actual": v["actual_value"], "status": v["match_status"]}
            for v in verifications[:10]
        ],
    }


def _build_prd_prompt(topic: str, user_context: str, hub_data: dict) -> str:
    """Build the system + user prompt for OpenAI PRD generation."""
    system = """You are a senior product manager at Tubi, a free ad-supported streaming service.
You write concise, data-driven PRDs that reference real metrics and user feedback.
Your PRDs are actionable and grounded in evidence, not aspirational fluff.

Output a complete PRD in markdown format with these exact sections:
1. **Problem Statement** — derived from sentiment data and competitive threats
2. **User Need** — backed by actual user quotes and sentiment data
3. **Proposed Solution** — concrete description of what to build
4. **Success Metrics** — table with Metric, Current Baseline, Target, Guardrail columns using real numbers
5. **Competitive Context** — what competitors are doing in this space
6. **Risks and Open Questions** — honest assessment
7. **Implementation Phases** — phased rollout plan

Use the hub data provided to ground every section in real numbers and quotes.
Do NOT invent data — if something is missing, note it as a gap."""

    hub_summary = json.dumps(hub_data, indent=2, default=str)

    user_msg = f"""Generate a PRD for: **{topic}**

Additional context from the requester:
{user_context if user_context else "(none provided)"}

--- HUB DATA (real data from our systems) ---
{hub_summary}
"""
    return system, user_msg


@router.post("/generate-prd")
def generate_prd(req: PRDRequest):
    """Generate a PRD using OpenAI, grounded in all hub data."""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    # 1. Gather all hub context
    hub_data = _gather_hub_context(req.topic)

    # 2. Build prompt
    system_prompt, user_prompt = _build_prd_prompt(req.topic, req.context, hub_data)

    # 3. Call OpenAI
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
        )
        prd_md = response.choices[0].message.content
    except Exception as e:
        logger.error("OpenAI PRD generation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"OpenAI call failed: {e}")

    # 4. Store in database
    prd_id = db.create_prd(topic=req.topic, content_md=prd_md)

    return {"id": prd_id, "topic": req.topic, "status": "draft", "prd_markdown": prd_md}


@router.get("/prds")
def list_prds(status: Optional[str] = None, limit: int = 100):
    """List all generated PRDs."""
    return db.get_prds(status=status, limit=limit)


@router.get("/prds/{prd_id}")
def get_prd(prd_id: int):
    """Get a single PRD by ID."""
    prd = db.get_prd(prd_id)
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")
    return prd


@router.put("/prds/{prd_id}")
def update_prd(prd_id: int, update: PRDUpdate):
    """Update PRD status or content after review."""
    existing = db.get_prd(prd_id)
    if not existing:
        raise HTTPException(status_code=404, detail="PRD not found")
    kwargs = {k: v for k, v in update.model_dump().items() if v is not None}
    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")
    db.update_prd(prd_id, **kwargs)
    return {"updated": True, "id": prd_id}
