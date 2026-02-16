"""Sentiment tracker: user feedback aggregation and trends."""

from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from .. import db

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
