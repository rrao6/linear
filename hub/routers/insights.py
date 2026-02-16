"""AI Insights: auto-generated analysis of hub data."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from .. import db
from .. import ai_insights

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/latest")
def get_latest_insights(type: str = None):
    """Get most recent auto-generated insights, optionally filtered by type.

    Types: sentiment_trends, competitive_position, data_anomalies,
           weekly_brief, experiments
    """
    if type:
        insight = db.get_latest_ai_insight(type)
        if not insight:
            return {"status": "no_data", "message": f"No insights of type '{type}' found"}
        return insight
    # Return latest of each type
    types = ["sentiment_trends", "competitive_position", "data_anomalies",
             "weekly_brief", "experiments"]
    results = {}
    for t in types:
        insight = db.get_latest_ai_insight(t)
        if insight:
            results[t] = insight
    if not results:
        return {"status": "no_data", "message": "No insights generated yet. POST /api/insights/analyze to run analysis."}
    return results


@router.post("/analyze")
def trigger_analysis(background_tasks: BackgroundTasks, type: str = None):
    """Trigger fresh analysis. Runs in background.

    If type is specified, runs only that analysis.
    Otherwise runs the full 5-phase analysis cycle.
    """
    valid_types = {
        "sentiment_trends": ai_insights.analyze_sentiment_trends,
        "competitive_position": ai_insights.analyze_competitive_position,
        "data_anomalies": ai_insights.analyze_data_anomalies,
        "weekly_brief": ai_insights.generate_weekly_brief,
        "experiments": ai_insights.suggest_experiments,
    }

    if type:
        if type not in valid_types:
            return {"status": "error", "message": f"Unknown type '{type}'. Valid: {list(valid_types.keys())}"}
        background_tasks.add_task(valid_types[type])
        return {"status": "analysis_started", "type": type}

    background_tasks.add_task(ai_insights.run_full_analysis)
    return {"status": "full_analysis_started", "types": list(valid_types.keys())}


@router.get("/brief")
def get_weekly_brief():
    """Get the latest weekly executive brief."""
    insight = db.get_latest_ai_insight("weekly_brief")
    if not insight:
        return {"status": "no_data", "message": "No weekly brief generated yet. POST /api/insights/analyze?type=weekly_brief"}
    return insight


@router.get("/experiments")
def get_suggested_experiments():
    """Get AI-suggested experiments based on identified problems."""
    insight = db.get_latest_ai_insight("experiments")
    if not insight:
        return {"status": "no_data", "message": "No experiment suggestions yet. POST /api/insights/analyze?type=experiments"}
    return insight


@router.get("/history")
def get_insight_history(type: str = None, limit: int = 20):
    """Get historical insights for trend comparison."""
    return db.get_ai_insights(type=type, limit=limit)
