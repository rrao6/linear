"""Manual feedback entry — for adding feedback from Slack, email, meetings, or user research.

Usage:
    python3 -m hub.collectors.manual --text "Users complain about EPG navigation" --sentiment negative --topics epg,navigation
    python3 -m hub.collectors.manual --file feedback.json
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

HUB_URL = os.environ.get("HUB_URL", "http://localhost:8888")


def push_feedback(source, text, sentiment="neutral", score=0.0, topics=None, author="", url=""):
    """Push a single feedback item to the hub."""
    item = {
        "source": source,
        "text": text,
        "sentiment": sentiment,
        "sentiment_score": score,
        "topics": topics or [],
        "author": author,
        "url": url,
    }
    data = json.dumps(item).encode()
    req = urllib.request.Request(
        f"{HUB_URL}/api/sentiment/feedback",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=5)
    result = json.loads(resp.read().decode())
    print(f"Created feedback #{result.get('id')}")
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Manual feedback entry")
    parser.add_argument("--text", help="Feedback text")
    parser.add_argument("--source", default="manual", help="Source (manual, slack, email, meeting, uxr)")
    parser.add_argument("--sentiment", default="neutral", choices=["positive", "negative", "neutral", "mixed"])
    parser.add_argument("--score", type=float, default=0.0, help="Sentiment score (-1 to 1)")
    parser.add_argument("--topics", default="", help="Comma-separated topics")
    parser.add_argument("--author", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--file", help="JSON file with array of feedback items")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            items = json.load(f)
        for item in items:
            push_feedback(**item)
        print(f"Pushed {len(items)} items from {args.file}")
    elif args.text:
        topics = [t.strip() for t in args.topics.split(",") if t.strip()] if args.topics else []
        push_feedback(args.source, args.text, args.sentiment, args.score, topics, args.author, args.url)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
