"""Sentiment tracker: user feedback aggregation and trends."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from .. import db
from ..config import SPROUT_SOCIAL_API_KEY

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


class FeedbackCreate(BaseModel):
    source: str  # reddit, appstore, twitter, manual, slack
    text: str
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    topics: list = []
    author: str = ""
    url: str = ""
    metadata: dict = {}


class FeedbackBatch(BaseModel):
    items: List[FeedbackCreate]


class SproutMessage(BaseModel):
    """A single message from Sprout Social's listening/inbox API."""
    network: str = ""        # twitter, facebook, instagram, etc.
    text: str = ""
    sentiment: str = "neutral"  # positive, negative, neutral
    author: str = ""
    url: str = ""
    profile_name: str = ""
    created_time: str = ""
    tags: List[str] = []
    metrics: dict = {}       # likes, shares, impressions, etc.


class SproutCollectPayload(BaseModel):
    """Payload from Sprout Social webhook or manual collection."""
    messages: List[SproutMessage]
    topic: str = ""          # listening topic / query name
    date_range: str = ""     # e.g. "2026-02-01 to 2026-02-15"


@router.get("/summary")
def sentiment_summary():
    """Get overall sentiment summary."""
    return db.get_sentiment_summary()


@router.get("/feed")
def sentiment_feed(source: Optional[str] = None,
                   sentiment: Optional[str] = None,
                   limit: int = 50):
    """Get sentiment feed with optional filters."""
    items = db.get_feedback(source=source, sentiment=sentiment, limit=limit)
    for item in items:
        if isinstance(item.get("topics"), str):
            item["topics"] = json.loads(item["topics"])
        if isinstance(item.get("metadata"), str):
            item["metadata"] = json.loads(item["metadata"])
    return items


@router.post("/feedback")
def add_feedback(f: FeedbackCreate):
    """Add a single feedback item."""
    id = db.create_feedback(
        source=f.source, text=f.text, sentiment=f.sentiment,
        sentiment_score=f.sentiment_score, topics=f.topics,
        author=f.author, url=f.url, metadata=f.metadata,
    )
    return {"id": id}


@router.post("/feedback/batch")
def add_feedback_batch(batch: FeedbackBatch):
    """Add multiple feedback items."""
    ids = []
    for f in batch.items:
        id = db.create_feedback(
            source=f.source, text=f.text, sentiment=f.sentiment,
            sentiment_score=f.sentiment_score, topics=f.topics,
            author=f.author, url=f.url, metadata=f.metadata,
        )
        ids.append(id)
    return {"ids": ids, "count": len(ids)}


@router.post("/collect/sprout/ingest")
def ingest_sprout(payload: SproutCollectPayload):
    """Ingest social listening data from Sprout Social webhook/manual push.

    Converts Sprout messages into feedback items, mapping network names
    to the source field and preserving Sprout-specific metrics in metadata.
    """
    _sentiment_map = {"positive": 0.5, "negative": -0.5, "neutral": 0.0}
    ids = []
    for msg in payload.messages:
        score = _sentiment_map.get(msg.sentiment, 0.0)
        meta = {
            "sprout_network": msg.network,
            "sprout_topic": payload.topic,
            "sprout_date_range": payload.date_range,
            "sprout_profile": msg.profile_name,
            "sprout_created_time": msg.created_time,
            "sprout_metrics": msg.metrics,
        }
        fb_id = db.create_feedback(
            source=f"sprout:{msg.network}" if msg.network else "sprout",
            text=msg.text,
            sentiment=msg.sentiment,
            sentiment_score=score,
            topics=msg.tags,
            author=msg.author,
            url=msg.url,
            metadata=meta,
        )
        ids.append(fb_id)
    return {"ids": ids, "count": len(ids), "topic": payload.topic}


@router.get("/topics")
def sentiment_topics():
    """Get topic frequency from feedback."""
    items = db.get_feedback(limit=1000)
    topic_counts = {}
    for item in items:
        topics = item.get("topics", "[]")
        if isinstance(topics, str):
            topics = json.loads(topics)
        for t in topics:
            topic_counts[t] = topic_counts.get(t, 0) + 1
    sorted_topics = sorted(topic_counts.items(), key=lambda x: -x[1])
    return [{"topic": t, "count": c} for t, c in sorted_topics]


class SproutCollectRequest(BaseModel):
    customer_id: Optional[str] = None
    days: int = 3
    limit: int = 50
    probe: bool = False


def _run_sprout_collection(customer_id, days, limit):
    """Background task: collect from Sprout Social and store results."""
    from ..collectors.sprout import collect_mentions
    items = collect_mentions(customer_id=customer_id, days=days, limit=limit)
    for item in items:
        topics = item.get("topics", [])
        db.create_feedback(
            source=item["source"],
            text=item["text"],
            sentiment=item.get("sentiment", "neutral"),
            sentiment_score=item.get("sentiment_score", 0.0),
            topics=topics,
            author=item.get("author", ""),
            url=item.get("url", ""),
            metadata=item.get("metadata", {}),
        )
    return items


@router.post("/collect/sprout")
def collect_sprout(req: SproutCollectRequest, background_tasks: BackgroundTasks):
    """Trigger Sprout Social sentiment collection.

    If probe=true, probes the API to discover available endpoints.
    Otherwise, collects mentions and stores them as feedback.
    """
    if not SPROUT_SOCIAL_API_KEY:
        return {"status": "error", "message": "SPROUT_SOCIAL_API_KEY not configured"}

    if req.probe:
        from ..collectors.sprout import probe_api
        result = probe_api()
        return {"status": "ok", "probe": result}

    background_tasks.add_task(
        _run_sprout_collection, req.customer_id, req.days, req.limit,
    )
    return {
        "status": "ok",
        "message": f"Sprout Social collection started (last {req.days} days, limit {req.limit})",
        "source": "sprout",
    }


# --- Collector trigger endpoints ---

def _run_reddit_collector():
    """Run Reddit collector in a background thread."""
    try:
        from ..collectors.reddit import collect_reddit, push_to_hub
        items = collect_reddit()
        if items:
            push_to_hub(items)
    except Exception as e:
        print(f"Reddit collector error: {e}")


def _run_appstore_collector():
    """Run AppStore collector in a background thread."""
    try:
        from ..collectors.appstore import collect_apple_reviews, push_to_hub
        items = collect_apple_reviews()
        if items:
            push_to_hub(items)
    except Exception as e:
        print(f"AppStore collector error: {e}")


@router.post("/collect/reddit")
def trigger_reddit_collection():
    """Trigger Reddit sentiment collection in background."""
    t = threading.Thread(target=_run_reddit_collector, daemon=True)
    t.start()
    return {"status": "started", "collector": "reddit"}


@router.post("/collect/appstore")
def trigger_appstore_collection():
    """Trigger App Store review collection in background."""
    t = threading.Thread(target=_run_appstore_collector, daemon=True)
    t.start()
    return {"status": "started", "collector": "appstore"}


@router.post("/collect/all")
def trigger_all_collection():
    """Trigger all sentiment collectors in background."""
    collectors = []
    for name, func in [("reddit", _run_reddit_collector),
                        ("appstore", _run_appstore_collector)]:
        t = threading.Thread(target=func, daemon=True)
        t.start()
        collectors.append(name)
    return {"status": "started", "collectors": collectors}


# --- Trends endpoint ---

@router.get("/trends")
def sentiment_trends(days: int = 30):
    """Get sentiment score averaged by day for the last N days."""
    with db.get_db() as conn:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """SELECT DATE(collected_at) as day,
                      AVG(sentiment_score) as avg_score,
                      COUNT(*) as count,
                      SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) as positive,
                      SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative,
                      SUM(CASE WHEN sentiment = 'neutral' THEN 1 ELSE 0 END) as neutral
               FROM feedback
               WHERE collected_at >= ?
               GROUP BY DATE(collected_at)
               ORDER BY day ASC""",
            (since,),
        ).fetchall()
        return [
            {
                "day": r["day"],
                "avg_score": round(r["avg_score"], 3) if r["avg_score"] else 0.0,
                "count": r["count"],
                "positive": r["positive"],
                "negative": r["negative"],
                "neutral": r["neutral"],
            }
            for r in rows
        ]
