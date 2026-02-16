"""OEM placement tracker: platform positioning and competitive placement."""

import json
import logging
import sys
import time
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from .. import db
from ..config import PLUGINS_DIR

# Add linear-data plugin to path
sys.path.insert(0, str(PLUGINS_DIR / "linear-data"))

router = APIRouter(prefix="/api/oem", tags=["oem"])
log = logging.getLogger(__name__)

# SQL to get linear TVT by platform (last 30 days)
SQL_PLATFORM_TVT = """
SELECT
    vs.platform AS platform,
    ROUND(SUM(vs.tvt_millisec) / 3600000.0, 0) AS tvt_hours,
    ROUND(
        SUM(vs.tvt_millisec) * 100.0
        / (SELECT SUM(vs2.tvt_millisec)
           FROM core_prod.session.video_session vs2
           JOIN core_prod.content.content_info ci2 ON vs2.content_id = ci2.content_id
           WHERE vs2.date >= DATE_ADD(CURRENT_DATE(), -30)
             AND vs2.tvt_millisec > 0
             AND ci2.content_type = 'LINEAR'),
        2
    ) AS tvt_pct
FROM core_prod.session.video_session vs
JOIN core_prod.content.content_info ci
    ON vs.content_id = ci.content_id
WHERE vs.date >= DATE_ADD(CURRENT_DATE(), -30)
    AND vs.tvt_millisec > 0
    AND ci.content_type = 'LINEAR'
GROUP BY vs.platform
ORDER BY tvt_hours DESC
"""

# Map Databricks platform values to our OEM platform IDs
PLATFORM_MAP = {
    "AMAZONFIRETV": "amazon_fire",
    "ROKU": "roku",
    "SAMSUNG": "samsung",
    "LGTV": "lg",
    "VIZIO": "vizio",
    "ANDROIDTV": "google_tv",
}


def _fetch_platform_tvt() -> dict:
    """Query Databricks for live linear TVT by platform. Returns {platform_id: {tvt_hours, tvt_pct}}."""
    cached = db.get_cached_kpi("oem_platform_tvt")
    if cached is not None:
        return cached

    try:
        from linear_data.connection import get_cursor

        t0 = time.time()
        with get_cursor() as cur:
            cur.execute(SQL_PLATFORM_TVT)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        elapsed = time.time() - t0
        db.log_query(sql_text=SQL_PLATFORM_TVT, query_name="oem_platform_tvt",
                     row_count=len(rows), elapsed_sec=round(elapsed, 2))

        result = {}
        for row in rows:
            db_platform = str(row.get("platform", "")).upper()
            oem_id = PLATFORM_MAP.get(db_platform)
            if oem_id:
                result[oem_id] = {
                    "tvt_hours": row.get("tvt_hours"),
                    "tvt_pct": row.get("tvt_pct"),
                }
        db.set_cached_kpi("oem_platform_tvt", result)
        return result
    except Exception as e:
        log.warning("Databricks platform TVT query failed: %s", e)
        return {}


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
    """Get platform overview with live TVT data from Databricks."""
    # Fetch live TVT data — returns {platform_id: {tvt_hours, tvt_pct}}
    live_tvt = _fetch_platform_tvt()

    # Static platform metadata
    platform_meta = [
        {
            "id": "amazon_fire",
            "name": "Amazon Fire TV",
            "integration": "Live tab deeplinks",
            "dependency_level": "critical",
            "notes": "Biggest platform dependency. Drives linear TVT via Live tab deeplinks.",
            "competitors": ["Amazon Freevee (700+ ch)", "Pluto TV", "Xumo"],
        },
        {
            "id": "roku",
            "name": "Roku",
            "integration": "Roku Channel, Live TV guide",
            "dependency_level": "high",
            "notes": "#1 for VOD. Roku Channel won Best Free Streaming 2025.",
            "competitors": ["Roku Channel (375 ch)", "Pluto TV", "Xumo"],
        },
        {
            "id": "samsung",
            "name": "Samsung TV Plus",
            "integration": "Samsung TV Plus pre-installed",
            "dependency_level": "medium",
            "notes": "300+ channels. Pre-installed on Samsung TVs.",
            "competitors": ["Samsung TV Plus (300+ ch)"],
        },
        {
            "id": "lg",
            "name": "LG Channels",
            "integration": "LG Channels pre-installed",
            "dependency_level": "medium",
            "notes": "Pre-installed on LG TVs.",
            "competitors": ["LG Channels"],
        },
        {
            "id": "vizio",
            "name": "Vizio WatchFree+",
            "integration": "WatchFree+ pre-installed",
            "dependency_level": "medium",
            "notes": "300+ channels. Pre-installed on Vizio TVs.",
            "competitors": ["Vizio WatchFree+ (300+ ch)"],
        },
        {
            "id": "google_tv",
            "name": "Google TV",
            "integration": "Live tab integration",
            "dependency_level": "low",
            "notes": "Growing platform with Live tab.",
            "competitors": ["Google TV Free Channels"],
        },
    ]

    # Merge live data into platform metadata
    platforms = []
    for p in platform_meta:
        tvt_data = live_tvt.get(p["id"], {})
        platforms.append({
            **p,
            "tvt_share": tvt_data.get("tvt_pct"),
            "linear_tvt_pct": tvt_data.get("tvt_pct"),
            "tvt_hours": tvt_data.get("tvt_hours"),
        })

    return {"platforms": platforms, "source": "databricks" if live_tvt else "static"}


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


class GracenoteMappingUpdate(BaseModel):
    gracenote_id: Optional[str] = None
    content_name: Optional[str] = None
    content_type: Optional[str] = None
    match_status: Optional[str] = None
    notes: Optional[str] = None


@router.put("/gracenote/{mapping_id}")
def update_gracenote(mapping_id: int, update: GracenoteMappingUpdate):
    """Update a Gracenote ID mapping."""
    kwargs = {k: v for k, v in update.model_dump().items() if v is not None}
    if not kwargs:
        return {"updated": False}
    db.update_gracenote_mapping(mapping_id, **kwargs)
    return {"updated": True}


@router.delete("/gracenote/{mapping_id}")
def delete_gracenote(mapping_id: int):
    """Delete a Gracenote ID mapping."""
    db.delete_gracenote_mapping(mapping_id)
    return {"deleted": True}
