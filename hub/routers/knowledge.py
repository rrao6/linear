"""Knowledge engine: PRD review, feature ideation, insight synthesis, weekly digest."""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db
from ..config import OPENAI_API_KEY

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _get_openai_client():
    """Get OpenAI client, raising if not configured."""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")
    try:
        import openai
        return openai.OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        raise HTTPException(status_code=503, detail="openai package not installed")


def _gather_hub_context(keywords: list[str] = None) -> dict:
    """Pull relevant data from all hub tables for AI context."""
    feedback = db.get_feedback(limit=200)
    learnings = db.get_learnings(limit=100)
    experiments = db.get_experiments(limit=50)
    verifications = db.get_verifications(limit=50)
    changelog = db.get_change_log(limit=50)
    sentiment = db.get_sentiment_summary()

    # If keywords provided, filter to relevant items
    if keywords:
        kw_lower = [k.lower() for k in keywords]

        def matches(text: str) -> bool:
            t = text.lower()
            return any(k in t for k in kw_lower)

        feedback = [f for f in feedback if matches(f.get("text", ""))][:50]
        learnings = [l for l in learnings
                     if matches(l.get("title", "")) or matches(l.get("description", ""))][:30]
        experiments = [e for e in experiments
                       if matches(e.get("name", "")) or matches(e.get("hypothesis", ""))][:20]
        changelog = [c for c in changelog
                     if matches(c.get("title", "")) or matches(c.get("description", ""))][:20]

    return {
        "sentiment_summary": sentiment,
        "feedback_samples": [{"text": f["text"], "sentiment": f["sentiment"],
                              "source": f["source"]} for f in feedback[:30]],
        "learnings": [{"category": l["category"], "title": l["title"],
                       "description": l["description"]} for l in learnings[:20]],
        "experiments": [{"name": e["name"], "status": e["status"],
                         "hypothesis": e.get("hypothesis", "")} for e in experiments[:15]],
        "verifications": [{"metric": v["metric_name"], "expected": v["expected_value"],
                           "actual": v["actual_value"], "status": v["match_status"]}
                          for v in verifications[:15]],
        "recent_changes": [{"type": c["type"], "title": c["title"],
                            "description": c.get("description", "")} for c in changelog[:15]],
    }


# --- PRD Review ---

class PRDReviewRequest(BaseModel):
    prd_id: Optional[int] = None
    prd_content: Optional[str] = None


@router.post("/review-prd")
def review_prd(req: PRDReviewRequest):
    """Review a PRD against hub data using AI. Provide prd_id (work item) or raw prd_content."""
    prd_text = req.prd_content or ""

    # If prd_id given, fetch from work_items
    if req.prd_id and not prd_text:
        items = db.get_work_items(type="prd", limit=500)
        match = next((w for w in items if w["id"] == req.prd_id), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"PRD work item {req.prd_id} not found")
        prd_text = f"# {match['title']}\n\n{match['description']}"

    if not prd_text.strip():
        raise HTTPException(status_code=400, detail="Provide prd_id or prd_content")

    client = _get_openai_client()
    context = _gather_hub_context()

    system_prompt = """You are a senior product reviewer at Tubi, a free ad-supported streaming TV service.
You review PRDs against real data from our strategy hub. Be specific and actionable.

Hub context (current data from our systems):
""" + json.dumps(context, indent=2, default=str)

    user_prompt = f"""Review this PRD and return a JSON object with these fields:
- gaps: array of strings — what data or considerations are missing
- risks: array of strings — competitive, user, or technical risks not addressed
- metrics_check: string — are success metrics realistic given current baselines?
- sentiment_alignment: string — does this address what users actually complain about?
- score: integer 1-10 — overall readiness score
- suggestions: array of strings — specific improvements

PRD to review:
{prd_text}

Return ONLY valid JSON, no markdown fences."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()
    # Parse JSON from response, handling potential markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        feedback = json.loads(raw)
    except json.JSONDecodeError:
        feedback = {"raw_response": raw, "score": 0, "gaps": ["Failed to parse AI response"],
                    "risks": [], "metrics_check": "", "sentiment_alignment": "", "suggestions": []}

    score = feedback.get("score", 0)
    review_id = db.create_prd_review(
        prd_id=req.prd_id, prd_content=prd_text, reviewer="ai",
        score=score, feedback_json=feedback,
    )

    return {"id": review_id, "score": score, "feedback": feedback}


@router.get("/reviews")
def list_reviews(prd_id: Optional[int] = None, limit: int = 50):
    """List PRD reviews."""
    reviews = db.get_prd_reviews(prd_id=prd_id, limit=limit)
    for r in reviews:
        if isinstance(r.get("feedback_json"), str):
            r["feedback_json"] = json.loads(r["feedback_json"])
    return reviews


# --- Feature Idea Generator ---

class IdeaGenerateRequest(BaseModel):
    area: str  # epg, discovery, sports, ads, etc.


@router.post("/generate-ideas")
def generate_ideas(req: IdeaGenerateRequest):
    """Generate ranked feature ideas for a product area using hub data."""
    client = _get_openai_client()
    context = _gather_hub_context(keywords=[req.area])

    system_prompt = f"""You are a senior PM at Tubi generating feature ideas for the "{req.area}" area.
Use the hub data below to ground ideas in real user needs and competitive dynamics.

Hub context:
""" + json.dumps(context, indent=2, default=str)

    user_prompt = f"""Generate 5-10 ranked feature ideas for the "{req.area}" area.

For each idea return a JSON object with:
- title: short feature name
- description: 2-3 sentence description
- user_need: what user pain point or desire this addresses (cite sentiment if relevant)
- competitive_advantage: how this differentiates vs competitors
- estimated_impact: expected effect on key metrics
- effort: "S", "M", or "L"

Return a JSON array of ideas ranked by impact. Return ONLY valid JSON, no markdown fences."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=3000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        ideas = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse AI response")

    if not isinstance(ideas, list):
        ideas = [ideas]

    gen_id = uuid.uuid4().hex[:12]
    stored_ids = []
    for idea in ideas:
        idea_id = db.create_feature_idea(
            area=req.area,
            title=idea.get("title", "Untitled"),
            description=idea.get("description", ""),
            user_need=idea.get("user_need", ""),
            competitive_advantage=idea.get("competitive_advantage", ""),
            estimated_impact=idea.get("estimated_impact", ""),
            effort=idea.get("effort", "M"),
            source_generation_id=gen_id,
        )
        stored_ids.append(idea_id)

    return {"generation_id": gen_id, "count": len(stored_ids), "ideas": ideas, "ids": stored_ids}


@router.get("/ideas")
def list_ideas(area: Optional[str] = None, limit: int = 100):
    """List all generated feature ideas."""
    return db.get_feature_ideas(area=area, limit=limit)


@router.put("/ideas/{idea_id}/vote")
def vote_idea(idea_id: int, direction: int = 1):
    """Upvote (+1) or downvote (-1) a feature idea."""
    if direction not in (1, -1):
        raise HTTPException(status_code=400, detail="direction must be 1 or -1")
    new_votes = db.vote_feature_idea(idea_id, direction)
    return {"id": idea_id, "votes": new_votes}


# --- Insight Synthesizer ---

class SynthesizeRequest(BaseModel):
    question: str


@router.post("/synthesize")
def synthesize_insight(req: SynthesizeRequest):
    """Synthesize an answer to a strategic question using all hub data."""
    client = _get_openai_client()

    # Extract keywords from question for targeted context
    keywords = [w for w in req.question.lower().split()
                if len(w) > 3 and w not in {"what", "should", "about", "that", "this",
                                              "with", "from", "have", "been", "does",
                                              "would", "could", "their", "there"}]
    context = _gather_hub_context(keywords=keywords)

    system_prompt = """You are a senior strategist at Tubi synthesizing insights from our data hub.
Ground every claim in the data provided. Cite specific sources (feedback, learnings, experiments, metrics).

Hub context:
""" + json.dumps(context, indent=2, default=str)

    user_prompt = f"""Answer this strategic question with a structured analysis:

Question: {req.question}

Format your response as JSON with:
- answer_md: markdown-formatted answer (use headers, bullets, bold for key points)
- citations: array of objects with {{source: string, detail: string}} citing specific hub data

Return ONLY valid JSON, no markdown fences."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=3000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"answer_md": raw, "citations": []}

    answer_md = result.get("answer_md", "")
    citations = result.get("citations", [])

    insight_id = db.create_insight(
        question=req.question, answer_md=answer_md, citations_json=citations,
    )

    return {"id": insight_id, "question": req.question,
            "answer_md": answer_md, "citations": citations}


@router.get("/insights")
def list_insights(limit: int = 50):
    """List all synthesized insights."""
    insights = db.get_insights(limit=limit)
    for i in insights:
        if isinstance(i.get("citations_json"), str):
            i["citations_json"] = json.loads(i["citations_json"])
    return insights


# --- Weekly Digest ---

@router.get("/digest")
def weekly_digest():
    """Auto-generate a weekly summary of hub activity."""
    client = _get_openai_client()

    # Gather data from the last 7 days
    now = datetime.now()
    week_ago = (now - timedelta(days=7)).isoformat()

    # Pull all recent data
    learnings = db.get_learnings(limit=50)
    feedback = db.get_feedback(limit=100)
    experiments = db.get_experiments(limit=30)
    changelog = db.get_change_log(limit=30)
    sentiment = db.get_sentiment_summary()
    verifications = db.get_verifications(limit=20)
    ideas = db.get_feature_ideas(limit=20)
    insights = db.get_insights(limit=10)

    # Filter to recent items where possible
    def is_recent(item: dict) -> bool:
        created = item.get("created_at", item.get("collected_at", ""))
        return created >= week_ago if created else False

    recent_learnings = [l for l in learnings if is_recent(l)]
    recent_feedback = [f for f in feedback if is_recent(f)]
    recent_changes = [c for c in changelog if is_recent(c)]
    recent_ideas = [i for i in ideas if is_recent(i)]
    recent_insights = [i for i in insights if is_recent(i)]

    digest_context = {
        "period": f"{(now - timedelta(days=7)).strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
        "sentiment_summary": sentiment,
        "new_learnings": [{"title": l["title"], "category": l["category"]}
                          for l in recent_learnings],
        "new_feedback_count": len(recent_feedback),
        "feedback_samples": [{"text": f["text"][:150], "sentiment": f["sentiment"]}
                             for f in recent_feedback[:10]],
        "experiments": [{"name": e["name"], "status": e["status"]}
                        for e in experiments[:10]],
        "recent_changes": [{"type": c["type"], "title": c["title"]}
                           for c in recent_changes],
        "recent_ideas": [{"title": i["title"], "area": i["area"]} for i in recent_ideas],
        "recent_insights": [{"question": i["question"]} for i in recent_insights],
        "data_verifications": [{"metric": v["metric_name"], "status": v["match_status"]}
                               for v in verifications[:10]],
    }

    system_prompt = """You are a PM at Tubi writing a weekly digest for the linear TV strategy team.
Be concise, actionable, and highlight what matters most."""

    user_prompt = f"""Write a 1-page weekly digest based on this hub data.

{json.dumps(digest_context, indent=2, default=str)}

Format as markdown with these sections:
- **TL;DR** (3 bullet max)
- **New Learnings** (what we discovered this week)
- **Sentiment Pulse** (user feedback trends)
- **Competitive Moves** (from changelog/intel)
- **Experiment Status** (what's running, what changed)
- **Open Questions** (what needs investigation)

Keep it brief and scannable. Return markdown only, no JSON wrapping."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
        max_tokens=2000,
    )

    digest_md = response.choices[0].message.content.strip()

    return {
        "period": digest_context["period"],
        "digest_md": digest_md,
        "stats": {
            "new_learnings": len(recent_learnings),
            "new_feedback": len(recent_feedback),
            "recent_changes": len(recent_changes),
            "active_experiments": len([e for e in experiments if e.get("status") == "running"]),
            "new_ideas": len(recent_ideas),
            "new_insights": len(recent_insights),
        },
    }
