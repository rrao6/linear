"""Feature adoption tracker: experiments, rollouts, metrics."""

import json
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from .. import db

router = APIRouter(prefix="/api/features", tags=["features"])


class ExperimentCreate(BaseModel):
    name: str
    phase: str = ""
    hypothesis: str = ""
    status: str = "planned"
    platforms: list = []
    statsig_id: str = ""
    notes: str = ""


class ExperimentUpdate(BaseModel):
    name: Optional[str] = None
    phase: Optional[str] = None
    hypothesis: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    platforms: Optional[list] = None
    metrics: Optional[dict] = None
    statsig_id: Optional[str] = None
    notes: Optional[str] = None


@router.get("/experiments")
def list_experiments(status: Optional[str] = None, limit: int = 100):
    """List experiments with optional status filter."""
    exps = db.get_experiments(status=status, limit=limit)
    for exp in exps:
        for field in ("platforms", "metrics"):
            if isinstance(exp.get(field), str):
                exp[field] = json.loads(exp[field])
    return exps


@router.post("/experiments")
def create_experiment(exp: ExperimentCreate):
    """Create a new experiment."""
    id = db.create_experiment(
        name=exp.name, phase=exp.phase, hypothesis=exp.hypothesis,
        status=exp.status, platforms=exp.platforms,
        statsig_id=exp.statsig_id, notes=exp.notes,
    )
    return {"id": id}


@router.put("/experiments/{exp_id}")
def update_experiment(exp_id: int, update: ExperimentUpdate):
    """Update an experiment."""
    kwargs = {k: v for k, v in update.model_dump().items() if v is not None}
    db.update_experiment(exp_id, **kwargs)
    return {"updated": True}


@router.get("/roadmap")
def get_roadmap():
    """EPG roadmap phases and status."""
    return {
        "phases": [
            {
                "id": "phase_1",
                "name": "Bring EPG Browse & Player to Parity",
                "status": "in_progress",
                "experiments": [
                    {"id": "1.1", "name": "Modernize EPG browsing", "status": "development",
                     "metrics": ["CTR from EPG", "Linear conversion", "Linear TVT"]},
                    {"id": "1.2", "name": "Unify player EPG", "status": "planned",
                     "metrics": ["Linear TVT", "Favorite channel rate"]},
                    {"id": "1.3", "name": "Coming Soon browsing + reminders", "status": "planned",
                     "metrics": ["Reminder set rate", "Return rate"]},
                ],
            },
            {
                "id": "phase_2",
                "name": "Content-First Discovery",
                "status": "planned",
                "experiments": [
                    {"id": "2.1", "name": "On Now container at EPG top", "status": "planned",
                     "metrics": ["Linear TVT", "Container CTR"]},
                    {"id": "2.2", "name": "For You mixed container", "status": "planned",
                     "metrics": ["Linear TVT", "Global TVT"]},
                ],
            },
            {
                "id": "phase_3",
                "name": "YMAL & Continuation",
                "status": "planned",
                "experiments": [
                    {"id": "3.1", "name": "YMAL in Linear Player", "status": "planned",
                     "metrics": ["AVT", "Session depth"]},
                    {"id": "3.2", "name": "Linear content in VOD YMAL", "status": "planned",
                     "metrics": ["Linear TVT", "Cross-content conversion"]},
                    {"id": "3.3", "name": "VOD content in Linear YMAL", "status": "planned",
                     "metrics": ["Global TVT"]},
                    {"id": "3.4", "name": "Up-next experience", "status": "planned",
                     "metrics": ["Continuation rate", "AVT"]},
                ],
            },
            {
                "id": "phase_4",
                "name": "Coming Soon & Return Loops",
                "status": "planned",
                "experiments": [
                    {"id": "4.1", "name": "Coming Soon to My List", "status": "planned",
                     "metrics": ["Save rate", "Return rate"]},
                    {"id": "4.2", "name": "Coming Soon container", "status": "planned",
                     "metrics": ["Container CTR", "Reminder conversion"]},
                ],
            },
        ],
    }
