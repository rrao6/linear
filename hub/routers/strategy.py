"""Strategy workspace: PRDs, decisions, work items, learnings, change log."""

import json
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from .. import db

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

@router.post("/generate-prd")
def generate_prd(context: dict):
    """Generate a PRD template with context from all modules."""
    title = context.get("title", "Untitled PRD")
    problem = context.get("problem", "")
    hypothesis = context.get("hypothesis", "")

    # Pull relevant data
    verifications = db.get_verifications(limit=10)
    feedback = db.get_feedback(limit=20)
    learnings = db.get_learnings(limit=10)
    experiments = db.get_experiments(limit=10)

    prd_md = f"""# {title}

> Date: {{date}}
> Author: {{author}}
> Status: DRAFT

## Problem Statement
{problem}

## Hypothesis
{hypothesis}

## Evidence

### Data Verifications
"""
    for v in verifications[:5]:
        prd_md += f"- **{v['metric_name']}**: expected={v['expected_value']}, actual={v['actual_value']} ({v['match_status']})\n"

    prd_md += "\n### User Feedback Themes\n"
    sentiment = db.get_sentiment_summary()
    prd_md += f"- Total feedback items: {sentiment['total']}\n"
    prd_md += f"- Average sentiment: {sentiment['avg_score']}\n"
    for s, c in sentiment.get("by_sentiment", {}).items():
        prd_md += f"- {s}: {c}\n"

    prd_md += "\n### Relevant Learnings\n"
    for l in learnings[:5]:
        prd_md += f"- [{l['category']}] {l['title']}: {l['description'][:100]}\n"

    prd_md += """
## Solution

### What we're building
[TODO]

### What we're NOT building
[TODO]

## Success Metrics
| Metric | Baseline | Target | Guardrail |
|--------|----------|--------|-----------|
| Linear TVT | | | |
| Global TVT | | | |
| Conversion | | | |

## Experiment Plan
[TODO]

## Risks & Mitigations
[TODO]

## Timeline
[TODO]
"""
    return {"prd_markdown": prd_md}
