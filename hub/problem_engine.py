"""Problem detection and clustering engine.

Takes raw feedback (sentiment, support tickets, app reviews, reddit posts, competitive moves)
and automatically identifies, groups, and ranks real user problems.

This is not sentiment analysis — it extracts *what is broken/missing/frustrating*,
clusters by semantic similarity, and ranks by business impact.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from openai import OpenAI

from .config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

JOURNEY_STAGES = ["discovery", "browsing", "channel_switching", "playback", "returning"]
SEVERITIES = ["blocking", "degraded", "annoying", "cosmetic"]
PRODUCT_AREAS = ["epg", "on_now", "search", "ads", "content", "deeplinks", "metadata"]
FREQUENCY_SIGNALS = ["always", "sometimes", "once", "unknown"]

EXTRACTION_PROMPT = """You are a product problem extractor for Tubi, a free ad-supported streaming TV service with ~340 linear channels.

Given user feedback text, extract the specific product problem described. Focus on WHAT IS BROKEN/MISSING/FRUSTRATING, not just sentiment.

Respond with a JSON object (no markdown, no code fences):
{
  "problem": "Brief, specific description of the problem (e.g., 'EPG guide shows wrong times for scheduled programs')",
  "journey_stage": one of ["discovery", "browsing", "channel_switching", "playback", "returning"],
  "platforms": ["list of platforms mentioned or implied, e.g. 'fire_tv', 'roku', 'samsung', 'lg', 'vizio', 'ios', 'android', 'web', 'all'"],
  "severity": one of ["blocking", "degraded", "annoying", "cosmetic"],
  "frequency": one of ["always", "sometimes", "once", "unknown"],
  "product_area": one of ["epg", "on_now", "search", "ads", "content", "deeplinks", "metadata"],
  "confidence": 0.0-1.0 how confident you are this is a real product problem (vs. content preference, general complaint, etc.)
}

Rules:
- "blocking" = can't use the feature at all
- "degraded" = feature works but poorly
- "annoying" = minor friction
- "cosmetic" = visual/polish issue
- If the feedback is about content preference (e.g., "I wish you had X show"), set confidence < 0.3
- If the feedback is too vague to identify a specific problem, set confidence < 0.3
- Platform should be "all" if no specific platform is mentioned
- Be specific in the problem description — "ads are too long during live sports" not "ad problems"
"""


def _get_client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


def extract_problem(text: str, source: str = "") -> Optional[dict]:
    """Extract a structured problem from raw feedback text using GPT-4o.

    Returns None if confidence is too low or extraction fails.
    """
    if not OPENAI_API_KEY:
        logger.warning("No OPENAI_API_KEY set, skipping problem extraction")
        return None

    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"Source: {source}\nFeedback: {text}"},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        content = resp.choices[0].message.content.strip()
        # Strip markdown fences if model adds them
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        result = json.loads(content)

        # Validate fields
        if result.get("confidence", 0) < 0.3:
            return None
        result.setdefault("platforms", ["all"])
        result.setdefault("severity", "annoying")
        result.setdefault("frequency", "unknown")
        result.setdefault("journey_stage", "browsing")
        result.setdefault("product_area", "content")

        # Normalize
        if isinstance(result["platforms"], str):
            result["platforms"] = [result["platforms"]]
        if result["severity"] not in SEVERITIES:
            result["severity"] = "annoying"
        if result["journey_stage"] not in JOURNEY_STAGES:
            result["journey_stage"] = "browsing"
        if result["product_area"] not in PRODUCT_AREAS:
            result["product_area"] = "content"
        if result["frequency"] not in FREQUENCY_SIGNALS:
            result["frequency"] = "unknown"

        return result
    except Exception as e:
        logger.error(f"Problem extraction failed: {e}")
        return None


def get_embedding(text: str) -> Optional[list[float]]:
    """Get OpenAI embedding for a text string."""
    if not OPENAI_API_KEY:
        return None
    client = _get_client()
    try:
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return resp.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


CLUSTER_THRESHOLD = 0.85


def cluster_problems(problems: list[dict]) -> list[dict]:
    """Cluster extracted problems by semantic similarity.

    Each problem dict must have 'problem' (text) and optionally 'embedding' (precomputed).
    Returns a list of problem groups.
    """
    if not problems:
        return []

    # Ensure embeddings
    for p in problems:
        if not p.get("embedding"):
            p["embedding"] = get_embedding(p["problem"])

    # Greedy clustering: assign each problem to the first cluster it's similar enough to
    clusters: list[dict] = []

    for p in problems:
        if not p.get("embedding"):
            continue  # skip if we couldn't get an embedding

        matched = False
        for cluster in clusters:
            sim = cosine_similarity(p["embedding"], cluster["centroid"])
            if sim >= CLUSTER_THRESHOLD:
                cluster["members"].append(p)
                # Update centroid as running average
                n = len(cluster["members"])
                cluster["centroid"] = [
                    (c * (n - 1) + e) / n
                    for c, e in zip(cluster["centroid"], p["embedding"])
                ]
                matched = True
                break

        if not matched:
            clusters.append({
                "centroid": p["embedding"][:],
                "members": [p],
            })

    # Convert clusters to problem groups
    groups = []
    for cluster in clusters:
        members = cluster["members"]
        # Aggregate metadata
        all_platforms = set()
        severity_dist = {}
        for m in members:
            for plat in m.get("platforms", ["all"]):
                all_platforms.add(plat)
            sev = m.get("severity", "annoying")
            severity_dist[sev] = severity_dist.get(sev, 0) + 1

        dates = [m.get("collected_at") or m.get("created_at") or "" for m in members]
        dates = [d for d in dates if d]
        first_seen = min(dates) if dates else datetime.now().isoformat()
        last_seen = max(dates) if dates else datetime.now().isoformat()

        # Determine trend based on temporal distribution
        trend = _compute_trend(dates)

        # Use first member's problem as representative, with the most common area/stage
        areas = [m.get("product_area", "content") for m in members]
        stages = [m.get("journey_stage", "browsing") for m in members]
        most_common_area = max(set(areas), key=areas.count)
        most_common_stage = max(set(stages), key=stages.count)
        # Most severe severity in group
        sev_order = {s: i for i, s in enumerate(SEVERITIES)}
        worst_severity = min(
            [m.get("severity", "annoying") for m in members],
            key=lambda s: sev_order.get(s, 3),
        )

        groups.append({
            "title": members[0]["problem"],
            "description": members[0]["problem"],
            "area": most_common_area,
            "journey_stage": most_common_stage,
            "severity": worst_severity,
            "count": len(members),
            "platforms": sorted(all_platforms),
            "severity_distribution": severity_dist,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "trend": trend,
            "example_quotes": [m.get("quote_text", m.get("problem", "")) for m in members[:5]],
            "embedding": cluster["centroid"],
            "members": members,
        })

    return groups


def _compute_trend(dates: list[str]) -> str:
    """Determine if a problem is growing, stable, or declining based on report dates."""
    if len(dates) < 3:
        return "stable"

    try:
        parsed = sorted(datetime.fromisoformat(d) for d in dates)
    except (ValueError, TypeError):
        return "stable"

    now = datetime.now()
    cutoff = now - timedelta(days=14)

    recent = sum(1 for d in parsed if d >= cutoff)
    older = len(parsed) - recent

    if older == 0:
        return "growing"  # all reports are recent

    recent_rate = recent / 14.0
    total_span = max((parsed[-1] - parsed[0]).days, 1)
    older_rate = older / total_span

    if recent_rate > older_rate * 1.5:
        return "growing"
    elif recent_rate < older_rate * 0.5:
        return "declining"
    return "stable"


def score_problem_group(group: dict) -> float:
    """Score a problem group by volume, recency, severity, breadth, and competitive gap.

    Returns a 0-100 score.
    """
    # Volume: log scale, max out around 50 reports
    import math
    volume_score = min(math.log(group["count"] + 1) / math.log(51), 1.0) * 25

    # Recency: days since last_seen, decay over 30 days
    try:
        last_seen = datetime.fromisoformat(group["last_seen"])
        days_ago = (datetime.now() - last_seen).days
    except (ValueError, TypeError):
        days_ago = 30
    recency_score = max(0, 1 - days_ago / 30) * 25

    # Severity
    severity_weights = {"blocking": 25, "degraded": 18, "annoying": 10, "cosmetic": 4}
    severity_score = severity_weights.get(group.get("severity", "annoying"), 10)

    # Breadth: more platforms = worse
    platforms = group.get("platforms", [])
    if "all" in platforms:
        breadth_score = 15
    else:
        breadth_score = min(len(platforms) / 5, 1.0) * 15

    # Trend bonus
    trend_bonus = {"growing": 10, "stable": 0, "declining": -5}.get(group.get("trend", "stable"), 0)

    return round(volume_score + recency_score + severity_score + breadth_score + trend_bonus, 1)


def detect_and_cluster(feedback_rows: list[dict]) -> list[dict]:
    """Full pipeline: extract problems from feedback, cluster, and rank.

    Takes raw feedback rows (from db.get_feedback()) and returns ranked problem groups.
    """
    # Step 1: Extract problems from each feedback item
    extracted = []
    for row in feedback_rows:
        result = extract_problem(row.get("text", ""), source=row.get("source", ""))
        if result:
            result["feedback_id"] = row.get("id")
            result["quote_text"] = row.get("text", "")
            result["source"] = row.get("source", "")
            result["collected_at"] = row.get("collected_at", "")
            result["created_at"] = row.get("created_at", "")
            extracted.append(result)

    if not extracted:
        return []

    # Step 2: Cluster
    groups = cluster_problems(extracted)

    # Step 3: Score and rank
    for g in groups:
        g["score"] = score_problem_group(g)

    groups.sort(key=lambda g: g["score"], reverse=True)

    return groups
