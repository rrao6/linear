#!/usr/bin/env python3
"""
AI-powered article classifier using OpenAI.
Classifies articles by category, relevance, and impact.

Usage:
    python3 tools/scanner/classifier.py --input articles.json --output classified.json
"""

import argparse
import json
import os
import ssl
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

from models import ArticleCandidate, ClassifiedIntel

ROOT = Path(__file__).resolve().parents[2]

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

CATEGORIES = [
    "strategic",     # M&A, major partnerships, market positioning
    "product",       # Feature launches, UX changes, platform updates
    "content",       # Channel additions, content deals, programming
    "marketing",     # Ad campaigns, brand moves, audience targeting
    "pricing",       # Price changes, ad model shifts, CPM data
    "partnership",   # Distribution deals, tech partnerships
    "earnings",      # Financial results, subscriber/user numbers
    "sports",        # Sports rights, live events, sports features
    "technology",    # AI/ML, ad tech, streaming tech
    "general",       # Catch-all
]

CLASSIFIER_PROMPT = """You are a competitive intelligence classifier for Tubi, a free ad-supported streaming TV (FAST) service owned by Fox Corp with ~340 linear channels.

Classify each article. For EACH article output ONE line in this exact format:
INDEX|CATEGORY|RELEVANCE|IMPACT|SUMMARY|ENTITIES

Where:
- INDEX: the article number (0-based)
- CATEGORY: one of: strategic, product, content, marketing, pricing, partnership, earnings, sports, technology, general
- RELEVANCE: 1-10 score (10 = directly about Tubi or a direct competitor's linear/FAST offering)
- IMPACT: 1-10 score (10 = could fundamentally change Tubi's competitive position)
- SUMMARY: 1-2 sentence factual summary. State ONLY facts from the article. No speculation or "suggesting" or "highlighting".
- ENTITIES: comma-separated list of companies/products/people mentioned

SCORING GUIDE:
- Relevance 8-10: Directly about Tubi, Pluto TV, Roku Channel, Samsung TV Plus, or FAST market
- Relevance 5-7: About streaming/CTV/cord-cutting broadly, vMVPDs like YouTube TV
- Relevance 1-4: Tangentially related entertainment/tech news
- Impact 8-10: Major M&A, exclusive sports rights, platform launches, regulation changes
- Impact 5-7: New channel launches, feature updates, pricing changes
- Impact 1-4: Minor updates, opinion pieces, rumors

ARTICLES TO CLASSIFY:
{articles}
"""


def call_openai(prompt, model="gpt-4o-mini", temperature=0.1, max_tokens=4000):
    """Call OpenAI API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("No OPENAI_API_KEY in environment")

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()

    req = Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with urlopen(req, timeout=60, context=ctx) as resp:
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"], result.get("usage", {})


def classify_batch(articles, model="gpt-4o-mini"):
    """Classify a batch of articles."""
    # Format articles for the prompt
    formatted = []
    for i, a in enumerate(articles):
        text = f"[{i}] COMPETITOR: {a.competitor_id} | TITLE: {a.title}"
        if a.snippet:
            text += f" | SNIPPET: {a.snippet[:200]}"
        formatted.append(text)

    prompt = CLASSIFIER_PROMPT.format(articles="\n".join(formatted))
    response, usage = call_openai(prompt, model=model)

    # Parse pipe-delimited output
    classified = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|", 5)
        if len(parts) < 6:
            continue

        try:
            idx = int(parts[0].strip())
            if idx >= len(articles):
                continue
            a = articles[idx]

            classified.append(ClassifiedIntel(
                article_hash=a.hash,
                competitor_id=a.competitor_id,
                title=a.title,
                url=a.url,
                summary=parts[4].strip(),
                category=parts[1].strip().lower(),
                relevance_score=float(parts[2].strip()),
                impact_score=float(parts[3].strip()),
                entities=[e.strip() for e in parts[5].split(",") if e.strip()],
                published_at=a.published_at,
            ))
        except (ValueError, IndexError):
            continue

    return classified, usage


def classify_all(articles, batch_size=40, max_workers=4, model="gpt-4o-mini"):
    """Classify all articles in parallel batches."""
    if not articles:
        return [], {}

    # Split into batches
    batches = [articles[i:i + batch_size] for i in range(0, len(articles), batch_size)]
    all_classified = []
    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    print(f"Classifying {len(articles)} articles in {len(batches)} batches "
          f"({max_workers} workers)...", flush=True)

    if len(batches) == 1:
        # Single batch, no threading needed
        classified, usage = classify_batch(batches[0], model)
        all_classified.extend(classified)
        for k in total_tokens:
            total_tokens[k] += usage.get(k, 0)
        print(f"  Batch 1: {len(classified)} classified")
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(classify_batch, batch, model): i
                for i, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    classified, usage = future.result()
                    all_classified.extend(classified)
                    for k in total_tokens:
                        total_tokens[k] += usage.get(k, 0)
                    print(f"  Batch {batch_idx + 1}: {len(classified)} classified")
                except Exception as e:
                    print(f"  Batch {batch_idx + 1}: ERROR: {e}")

    # Sort by impact * relevance
    all_classified.sort(
        key=lambda x: x.impact_score * x.relevance_score, reverse=True
    )

    print(f"\nClassified {len(all_classified)}/{len(articles)} articles. "
          f"Tokens: {total_tokens.get('total_tokens', 0)}")

    return all_classified, total_tokens


def group_similar(intel_items, similarity_threshold=0.6):
    """Group similar intel items (same story from multiple sources)."""
    groups = []
    used = set()

    for i, item in enumerate(intel_items):
        if i in used:
            continue

        group = [item]
        words_i = set(item.title.lower().split())

        for j, other in enumerate(intel_items[i + 1:], i + 1):
            if j in used:
                continue
            words_j = set(other.title.lower().split())

            # Jaccard similarity
            intersection = words_i & words_j
            union = words_i | words_j
            if union and len(intersection) / len(union) > similarity_threshold:
                group.append(other)
                used.add(j)

        # Merge group into primary item
        if len(group) > 1:
            item.source_count = len(group)
            # Keep highest scores
            item.relevance_score = max(g.relevance_score for g in group)
            item.impact_score = max(g.impact_score for g in group)

        groups.append(item)
        used.add(i)

    return groups


def main():
    parser = argparse.ArgumentParser(description="AI article classifier")
    parser.add_argument("--input", required=True, help="Input JSON with articles")
    parser.add_argument("--output", help="Output JSON path")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--min-relevance", type=float, default=3.0)
    parser.add_argument("--min-impact", type=float, default=3.0)
    args = parser.parse_args()

    # Load articles
    with open(args.input) as f:
        data = json.load(f)

    raw_articles = data.get("articles", [])
    articles = [ArticleCandidate(**a) for a in raw_articles]
    print(f"Loaded {len(articles)} articles")

    # Classify
    classified, tokens = classify_all(articles, model=args.model)

    # Group similar
    grouped = group_similar(classified)

    # Filter by minimum scores
    filtered = [
        c for c in grouped
        if c.relevance_score >= args.min_relevance
        and c.impact_score >= args.min_impact
    ]

    print(f"\nAfter grouping: {len(grouped)} unique stories")
    print(f"After filtering (rel>={args.min_relevance}, imp>={args.min_impact}): "
          f"{len(filtered)} actionable items")

    output = {
        "classified_date": datetime.now().isoformat(),
        "total_input": len(articles),
        "total_classified": len(classified),
        "total_grouped": len(grouped),
        "total_filtered": len(filtered),
        "tokens": tokens,
        "intel": [c.to_dict() for c in filtered],
    }

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved to {out}")
    else:
        for item in filtered[:10]:
            print(f"\n[{item.category}] ({item.relevance_score}/{item.impact_score}) "
                  f"{item.title}")
            print(f"  {item.summary}")


if __name__ == "__main__":
    main()
