"""AI Insights Engine — analyzes hub data and produces actionable insights.

Uses OpenAI gpt-4o to analyze sentiment trends, competitive position,
data anomalies, and generate weekly briefs with experiment suggestions.
"""

import json
import logging
from datetime import datetime, timedelta

from openai import OpenAI

from . import db
from .config import OPENAI_API_KEY

log = logging.getLogger(__name__)

MODEL = "gpt-4o"


def _get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured in .env")
    return OpenAI(api_key=OPENAI_API_KEY)


def _chat(system: str, user: str) -> str:
    """Call gpt-4o and return the response text."""
    client = _get_client()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content


def _chat_json(system: str, user: str) -> dict:
    """Call gpt-4o and parse the JSON response."""
    raw = _chat(system, user)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# 1. Sentiment Trend Analysis
# ---------------------------------------------------------------------------

def analyze_sentiment_trends() -> dict:
    """Pull all sentiment from feedback table, group by week, identify trends.

    Returns structured insights: emerging complaints, improving areas,
    new topics, sentiment shifts.
    """
    feedback = db.get_feedback(limit=500)
    if not feedback:
        return {"status": "no_data", "message": "No sentiment data available"}

    # Parse topics from JSON strings
    for item in feedback:
        if isinstance(item.get("topics"), str):
            item["topics"] = json.loads(item["topics"])

    # Group by week
    weekly = {}
    for item in feedback:
        collected = item.get("collected_at", item.get("created_at", ""))
        try:
            dt = datetime.fromisoformat(collected)
            week_key = dt.strftime("%Y-W%W")
        except (ValueError, TypeError):
            week_key = "unknown"
        weekly.setdefault(week_key, []).append(item)

    # Build summary for LLM
    weekly_summaries = {}
    for week, items in sorted(weekly.items()):
        sentiments = [i.get("sentiment", "neutral") for i in items]
        scores = [i.get("sentiment_score", 0) for i in items]
        all_topics = []
        for i in items:
            all_topics.extend(i.get("topics", []))
        sample_texts = [i["text"][:200] for i in items[:10]]

        weekly_summaries[week] = {
            "count": len(items),
            "sentiment_breakdown": {
                "positive": sentiments.count("positive"),
                "negative": sentiments.count("negative"),
                "neutral": sentiments.count("neutral"),
                "mixed": sentiments.count("mixed"),
            },
            "avg_score": round(sum(scores) / max(len(scores), 1), 3),
            "top_topics": _top_n(all_topics, 5),
            "sample_texts": sample_texts,
        }

    system = (
        "You are an analyst for Tubi, a free ad-supported streaming TV service. "
        "Analyze weekly sentiment data and return JSON with these keys:\n"
        "- emerging_complaints: list of {complaint, evidence, severity (high/medium/low)}\n"
        "- improving_areas: list of {area, evidence, trend_direction}\n"
        "- new_topics: list of {topic, first_seen_week, sample_quotes}\n"
        "- sentiment_shifts: list of {shift_description, from_week, to_week, magnitude}\n"
        "- summary: 2-3 sentence executive summary\n"
        "Cite specific data points: quote text, scores, counts. No vague statements."
    )
    user = f"Weekly sentiment data ({len(feedback)} total items):\n{json.dumps(weekly_summaries, default=str)}"

    result = _chat_json(system, user)
    result["data_points"] = len(feedback)
    result["weeks_analyzed"] = len(weekly_summaries)

    db.save_insight("sentiment_trends", result)
    return result


# ---------------------------------------------------------------------------
# 2. Competitive Position Analysis
# ---------------------------------------------------------------------------

def analyze_competitive_position() -> dict:
    """Pull latest intel scan, compare threats/opportunities to our metrics.

    Produces: competitive gaps, areas where we're winning, urgent responses needed.
    """
    # Get latest intel scan data
    from .routers.intel import get_latest

    latest_scan = get_latest()

    if isinstance(latest_scan, dict) and "error" in latest_scan:
        return {"status": "no_data", "message": "No intel scan data available"}

    # Get our known metrics for comparison
    our_metrics = {
        "channel_count": 340,
        "linear_tvt_share": 4.28,
        "linear_tvt_target": 9.0,
        "top_platform_dependency": "Amazon (31.5% of linear TVT)",
        "linear_vod_crossover_multiplier": "2.4x more watch time",
        "known_competitors": {
            "Xumo": {"channels": 411},
            "Pluto TV": {"channels": 378},
            "Samsung TV Plus": {"channels": "300+"},
            "Plex": {"channels": "600+"},
            "Sling Freestream": {"channels": "600+"},
        },
    }

    # Extract threats/opportunities/trends from analysis
    analysis = latest_scan.get("analysis", {})
    threats = analysis.get("threats", [])
    opportunities = analysis.get("opportunities", [])
    trends = analysis.get("trends", [])
    # Ensure these are lists
    if not isinstance(threats, list):
        threats = []
    if not isinstance(opportunities, list):
        opportunities = []
    if not isinstance(trends, list):
        trends = []

    # Build analysis payload
    scan_summary = {
        "scan_date": latest_scan.get("scan_date"),
        "threats": threats[:20],
        "opportunities": opportunities[:20],
        "trends": trends[:20],
        "classified_count": len(latest_scan.get("classified", {}).get("intel", [])),
    }

    system = (
        "You are a competitive intelligence analyst for Tubi (free ad-supported streaming TV). "
        "Compare our metrics against competitive intel and return JSON with:\n"
        "- competitive_gaps: list of {gap, competitor, their_metric, our_metric, severity (critical/high/medium/low)}\n"
        "- winning_areas: list of {area, evidence, advantage_description}\n"
        "- urgent_responses: list of {threat, competitor, recommended_action, timeline (immediate/this_quarter/next_quarter)}\n"
        "- market_position_summary: 2-3 sentence assessment\n"
        "Cite specific competitor names, channel counts, and metric values."
    )
    user = (
        f"Our metrics:\n{json.dumps(our_metrics, default=str)}\n\n"
        f"Latest intel scan:\n{json.dumps(scan_summary, default=str)}"
    )

    result = _chat_json(system, user)
    result["scan_date"] = latest_scan.get("scan_date")
    result["threats_analyzed"] = len(threats)
    result["opportunities_analyzed"] = len(opportunities)

    db.save_insight("competitive_position", result)
    return result


# ---------------------------------------------------------------------------
# 3. Data Anomaly Detection
# ---------------------------------------------------------------------------

def analyze_data_anomalies() -> dict:
    """Pull dashboard KPIs and trend data, flag unusual patterns.

    Looks for: sudden drops/spikes in TVT, channels gaining/losing share,
    platform shifts.
    """
    from .routers.dashboard import get_overview

    overview = get_overview()
    kpis = overview.get("kpis", {})
    daily_trend = overview.get("daily_trend", [])
    top_channels = overview.get("top_channels", [])
    platform_breakdown = overview.get("platform_breakdown", [])
    sentiment = overview.get("sentiment", {})

    # Compute basic stats on trend data for anomaly context
    trend_stats = {}
    if daily_trend and len(daily_trend) > 7:
        linear_hours = [d.get("linear_tvt_hours", 0) or 0 for d in daily_trend]
        total_hours = [d.get("total_tvt_hours", 0) or 0 for d in daily_trend]

        recent_7 = linear_hours[-7:]
        previous_7 = linear_hours[-14:-7] if len(linear_hours) >= 14 else linear_hours[:7]

        trend_stats = {
            "linear_tvt_recent_7d_avg": round(sum(recent_7) / max(len(recent_7), 1), 1),
            "linear_tvt_previous_7d_avg": round(sum(previous_7) / max(len(previous_7), 1), 1),
            "total_tvt_latest": total_hours[-1] if total_hours else None,
            "total_tvt_7d_avg": round(sum(total_hours[-7:]) / max(len(total_hours[-7:]), 1), 1),
            "data_points": len(daily_trend),
        }

    # Known discrepancies to check against
    known_issues = {
        "tvt_share_discrepancy": "Linear TVT share 4.28% vs strategy doc 6.5%",
        "attribution_gap": "49.8% of linear sessions have empty page_source",
        "segment_discrepancy": "Linear+VOD users 16.64% vs strategy doc 12%",
    }

    analysis_payload = {
        "kpis": kpis,
        "trend_stats": trend_stats,
        "top_channels": top_channels,
        "platform_breakdown": platform_breakdown,
        "sentiment_summary": sentiment,
        "known_discrepancies": known_issues,
        "daily_trend_sample": daily_trend[-14:] if daily_trend else [],
    }

    system = (
        "You are a data analyst for Tubi (free ad-supported streaming TV). "
        "Analyze dashboard KPIs and trend data for anomalies. Return JSON with:\n"
        "- anomalies: list of {metric, description, current_value, expected_range, severity (critical/warning/info)}\n"
        "- channel_shifts: list of {channel, direction (up/down), evidence}\n"
        "- platform_shifts: list of {platform, direction, evidence}\n"
        "- data_quality_flags: list of {issue, impact, recommended_action}\n"
        "- summary: 2-3 sentence overview of data health\n"
        "Cite specific metric values and dates. Flag anything that deviates from expected patterns."
    )
    user = f"Dashboard data:\n{json.dumps(analysis_payload, default=str)}"

    result = _chat_json(system, user)
    result["kpi_source"] = kpis.get("source", "unknown")
    result["trend_data_points"] = len(daily_trend)

    db.save_insight("data_anomalies", result)
    return result


# ---------------------------------------------------------------------------
# 4. Weekly Executive Brief
# ---------------------------------------------------------------------------

def generate_weekly_brief() -> dict:
    """Combine sentiment, competitive, and anomaly analyses into one brief.

    'Here's what happened this week, here's what matters, here's what to do.'
    """
    # Pull latest of each analysis type (from DB if available, else run fresh)
    sentiment = db.get_latest_insight("sentiment_trends")
    competitive = db.get_latest_insight("competitive_position")
    anomalies = db.get_latest_insight("data_anomalies")

    # Run any missing analyses
    if not sentiment:
        sentiment_data = analyze_sentiment_trends()
    else:
        sentiment_data = sentiment["content_json"]

    if not competitive:
        competitive_data = analyze_competitive_position()
    else:
        competitive_data = competitive["content_json"]

    if not anomalies:
        anomalies_data = analyze_data_anomalies()
    else:
        anomalies_data = anomalies["content_json"]

    # Get current work items and experiments for context
    work_items = db.get_work_items(status="in_progress", limit=10)
    experiments = db.get_experiments(status="running", limit=10)

    context = {
        "sentiment_analysis": sentiment_data,
        "competitive_analysis": competitive_data,
        "data_anomalies": anomalies_data,
        "active_work_items": [{"title": w["title"], "status": w["status"], "priority": w["priority"]} for w in work_items],
        "running_experiments": [{"name": e["name"], "status": e["status"], "hypothesis": e.get("hypothesis", "")} for e in experiments],
        "date": datetime.now().strftime("%Y-%m-%d"),
    }

    system = (
        "You are the strategic advisor for Tubi's Linear TV team. "
        "Combine all analyses into a weekly executive brief. Return JSON with:\n"
        "- week_of: date string\n"
        "- whats_happening: list of {headline, detail, source (sentiment/competitive/data)}\n"
        "- whats_important: list of {item, why_it_matters, urgency (immediate/this_week/this_month)}\n"
        "- recommended_actions: list of {action, rationale, owner_suggestion, priority (P0/P1/P2)}\n"
        "- risks: list of {risk, likelihood (high/medium/low), impact, mitigation}\n"
        "- executive_summary: 3-5 sentence brief a VP can read in 30 seconds\n"
        "Be specific. Cite data points, competitor names, sentiment quotes, metric values. "
        "No generic platitudes — every recommendation should be grounded in the data provided."
    )
    user = f"Analysis data for weekly brief:\n{json.dumps(context, default=str)}"

    result = _chat_json(system, user)

    db.save_insight("weekly_brief", result)
    return result


# ---------------------------------------------------------------------------
# 5. Experiment Suggestions
# ---------------------------------------------------------------------------

def suggest_experiments() -> dict:
    """Based on identified problems, suggest A/B experiments with hypotheses.

    Uses negative sentiment themes, competitive gaps, and declining metrics
    to propose experiments with success criteria.
    """
    sentiment = db.get_latest_insight("sentiment_trends")
    competitive = db.get_latest_insight("competitive_position")
    anomalies = db.get_latest_insight("data_anomalies")

    # Also pull existing experiments to avoid duplicates
    existing = db.get_experiments(limit=50)
    existing_names = [e["name"] for e in existing]

    problems = {
        "sentiment_issues": sentiment["content_json"] if sentiment else {},
        "competitive_gaps": competitive["content_json"] if competitive else {},
        "data_anomalies": anomalies["content_json"] if anomalies else {},
        "existing_experiments": existing_names,
        "known_context": {
            "on_now_row_unpinned": "Sep 2024, caused ~70% traffic loss to linear",
            "amazon_dependency": "31.5% of linear TVT from Amazon Live tab deeplinks",
            "linear_vod_crossover": "Linear+VOD users watch 2.4x more than VOD-only",
            "tvt_share_gap": "Current 4.28% vs target 9.0%",
        },
    }

    system = (
        "You are an experimentation lead for Tubi's Linear TV team. "
        "Based on identified problems (sentiment complaints, competitive gaps, data anomalies), "
        "suggest A/B experiments. Return JSON with:\n"
        "- experiments: list of {\n"
        "    name: short experiment name,\n"
        "    problem_source: which analysis identified this (sentiment/competitive/data),\n"
        "    problem_statement: specific problem being addressed (cite data),\n"
        "    hypothesis: 'If we [change], then [metric] will [improve] because [reason]',\n"
        "    variant_description: what the test variant looks like,\n"
        "    primary_metric: what to measure,\n"
        "    success_criteria: specific threshold (e.g. '+5% TVT per session'),\n"
        "    guardrail_metrics: list of metrics that must not regress,\n"
        "    estimated_duration_weeks: integer,\n"
        "    priority: P0/P1/P2\n"
        "  }\n"
        "- rationale: brief explanation of prioritization\n"
        "Do NOT suggest experiments that duplicate existing ones. "
        "Each experiment must cite the specific data point that motivated it."
    )
    user = f"Problem data and context:\n{json.dumps(problems, default=str)}"

    result = _chat_json(system, user)

    db.save_insight("experiments", result)
    return result


# ---------------------------------------------------------------------------
# Full analysis cycle
# ---------------------------------------------------------------------------

def run_full_analysis() -> dict:
    """Run all 5 analyses in sequence. Returns combined results."""
    results = {}
    for name, fn in [
        ("sentiment_trends", analyze_sentiment_trends),
        ("competitive_position", analyze_competitive_position),
        ("data_anomalies", analyze_data_anomalies),
        ("weekly_brief", generate_weekly_brief),
        ("experiments", suggest_experiments),
    ]:
        try:
            results[name] = fn()
        except Exception as e:
            log.error("Analysis %s failed: %s", name, e)
            results[name] = {"status": "error", "error": str(e)}

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _top_n(items: list, n: int) -> list:
    """Return top N items by frequency."""
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return [{"item": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])[:n]]
