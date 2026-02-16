"""OEM placement tracker: platform positioning and competitive placement."""

import json
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from .. import db

router = APIRouter(prefix="/api/oem", tags=["oem"])


class OEMSnapshotCreate(BaseModel):
    platform: str
    date: str
    tubi_placement: dict = {}
    competitor_placements: dict = {}
    notes: str = ""
    screenshot_path: str = ""


@router.get("/snapshots")
def list_snapshots(platform: Optional[str] = None, limit: int = 100):
    """List OEM placement snapshots."""
    snapshots = db.get_oem_snapshots(platform=platform, limit=limit)
    for s in snapshots:
        for field in ("tubi_placement", "competitor_placements"):
            if isinstance(s.get(field), str):
                s[field] = json.loads(s[field])
    return snapshots


@router.post("/snapshots")
def create_snapshot(snap: OEMSnapshotCreate):
    """Record an OEM placement snapshot."""
    id = db.create_oem_snapshot(
        platform=snap.platform, date=snap.date,
        tubi_placement=snap.tubi_placement,
        competitor_placements=snap.competitor_placements,
        notes=snap.notes, screenshot_path=snap.screenshot_path,
    )
    return {"id": id}


@router.get("/platforms")
def get_platforms():
    """Get platform overview with known dependencies."""
    return {
        "platforms": [
            {
                "id": "amazon_fire",
                "name": "Amazon Fire TV",
                "tvt_share": 31.5,
                "linear_tvt_pct": 31.5,
                "integration": "Live tab deeplinks",
                "dependency_level": "critical",
                "notes": "Biggest platform dependency. Drives 31.5% of linear TVT via Live tab deeplinks.",
                "competitors": ["Amazon Freevee (700+ ch)", "Pluto TV", "Xumo"],
            },
            {
                "id": "roku",
                "name": "Roku",
                "tvt_share": 18.0,
                "linear_tvt_pct": None,
                "integration": "Roku Channel, Live TV guide",
                "dependency_level": "high",
                "notes": "#1 for VOD. Roku Channel won Best Free Streaming 2025.",
                "competitors": ["Roku Channel (375 ch)", "Pluto TV", "Xumo"],
            },
            {
                "id": "samsung",
                "name": "Samsung TV Plus",
                "tvt_share": None,
                "linear_tvt_pct": None,
                "integration": "Samsung TV Plus pre-installed",
                "dependency_level": "medium",
                "notes": "300+ channels. Pre-installed on Samsung TVs.",
                "competitors": ["Samsung TV Plus (300+ ch)"],
            },
            {
                "id": "lg",
                "name": "LG Channels",
                "tvt_share": None,
                "linear_tvt_pct": None,
                "integration": "LG Channels pre-installed",
                "dependency_level": "medium",
                "notes": "Pre-installed on LG TVs.",
                "competitors": ["LG Channels"],
            },
            {
                "id": "vizio",
                "name": "Vizio WatchFree+",
                "tvt_share": None,
                "linear_tvt_pct": None,
                "integration": "WatchFree+ pre-installed",
                "dependency_level": "medium",
                "notes": "300+ channels. Pre-installed on Vizio TVs.",
                "competitors": ["Vizio WatchFree+ (300+ ch)"],
            },
            {
                "id": "google_tv",
                "name": "Google TV",
                "tvt_share": None,
                "linear_tvt_pct": None,
                "integration": "Live tab integration",
                "dependency_level": "low",
                "notes": "Growing platform with Live tab.",
                "competitors": ["Google TV Free Channels"],
            },
        ],
    }


@router.get("/gracenote")
def list_gracenote(status: Optional[str] = None, limit: int = 100):
    """List Gracenote ID mappings."""
    mappings = db.get_gracenote_mappings(status=status, limit=limit)
    return mappings


class GracenoteMappingCreate(BaseModel):
    tubi_content_id: str
    gracenote_id: str = ""
    content_name: str = ""
    content_type: str = ""
    match_status: str = "unmapped"
    notes: str = ""


@router.post("/gracenote")
def create_gracenote(m: GracenoteMappingCreate):
    """Create a Gracenote ID mapping."""
    id = db.create_gracenote_mapping(
        tubi_content_id=m.tubi_content_id, gracenote_id=m.gracenote_id,
        content_name=m.content_name, content_type=m.content_type,
        match_status=m.match_status, notes=m.notes,
    )
    return {"id": id}
