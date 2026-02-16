"""App Store review collector for Tubi.

Scrapes reviews from Apple App Store and Google Play Store RSS feeds.

Usage:
    python3 -m hub.collectors.appstore             # Both stores
    python3 -m hub.collectors.appstore --store apple
    python3 -m hub.collectors.appstore --store google
"""

import json
import os
import sys
import urllib.request
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from hub.collectors.reddit import classify_sentiment

HUB_URL = os.environ.get("HUB_URL", "http://localhost:8888")

# Tubi App IDs
APPLE_APP_ID = "886445756"  # Tubi on iOS
GOOGLE_PACKAGE = "com.tubitv"


def collect_apple_reviews(limit=50):
    """Collect reviews from Apple App Store RSS feed."""
    url = f"https://itunes.apple.com/us/rss/customerreviews/id={APPLE_APP_ID}/sortBy=mostRecent/json"

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "linear-hub/1.0"})
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        data = json.loads(resp.read().decode())
        entries = data.get("feed", {}).get("entry", [])

        for entry in entries[:limit]:
            if isinstance(entry.get("title"), dict):
                title = entry["title"].get("label", "")
            else:
                title = str(entry.get("title", ""))
            if isinstance(entry.get("content"), dict):
                content = entry["content"].get("label", "")
            else:
                content = str(entry.get("content", ""))

            rating = 0
            if isinstance(entry.get("im:rating"), dict):
                rating = int(entry["im:rating"].get("label", 0))

            author = ""
            if isinstance(entry.get("author"), dict):
                author_name = entry["author"].get("name", {})
                author = author_name.get("label", "") if isinstance(author_name, dict) else str(author_name)

            full_text = f"{title}\n{content}"

            # Always classify with AI for proper sentiment + topic extraction
            classified = classify_sentiment(full_text)
            sentiment_label = classified.get("sentiment", "neutral")
            score = classified.get("score", 0.0)
            topics = classified.get("topics", [])

            # Fallback: use rating if classification returned neutral and rating is strong
            if sentiment_label == "neutral" and rating >= 4:
                sentiment_label = "positive"
                score = max(score, (rating - 3) / 2.0)
            elif sentiment_label == "neutral" and rating <= 2:
                sentiment_label = "negative"
                score = min(score, -(3 - rating) / 2.0)

            if not topics or topics == ["general"]:
                text_lower = full_text.lower()
                extracted = []
                if "ad" in text_lower or "commercial" in text_lower:
                    extracted.append("ads")
                if "buffer" in text_lower or "load" in text_lower or "slow" in text_lower:
                    extracted.append("buffering")
                if "content" in text_lower or "movie" in text_lower or "show" in text_lower:
                    extracted.append("content")
                if "crash" in text_lower or "freeze" in text_lower or "bug" in text_lower:
                    extracted.append("crashes")
                if "channel" in text_lower or "linear" in text_lower or "live" in text_lower:
                    extracted.append("channels")
                if "epg" in text_lower or "guide" in text_lower or "schedule" in text_lower:
                    extracted.append("epg")
                if "ui" in text_lower or "interface" in text_lower or "navigate" in text_lower or "menu" in text_lower:
                    extracted.append("ui")
                if "search" in text_lower or "find" in text_lower:
                    extracted.append("search")
                if "subtitle" in text_lower or "caption" in text_lower:
                    extracted.append("subtitles")
                topics = extracted if extracted else ["general"]

            items.append({
                "source": "appstore",
                "text": full_text[:500],
                "sentiment": sentiment_label,
                "sentiment_score": score,
                "topics": topics,
                "author": author,
                "url": f"https://apps.apple.com/us/app/tubi/id{APPLE_APP_ID}",
                "metadata": {"store": "apple", "rating": rating},
            })

        print(f"  Apple App Store: {len(items)} reviews collected")
    except Exception as e:
        print(f"  Apple App Store error: {e}")

    return items


def collect_google_reviews():
    """Note: Google Play doesn't have a public RSS feed for reviews.
    This is a placeholder that can be enhanced with the google-play-scraper package."""
    print("  Google Play: No public RSS feed. Install google-play-scraper for full access.")
    print("  pip3 install google-play-scraper")
    return []


def push_to_hub(items):
    """Push collected items to the hub API."""
    for item in items:
        try:
            data = json.dumps(item).encode()
            req = urllib.request.Request(
                f"{HUB_URL}/api/sentiment/feedback",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"  Push error: {e}")
    print(f"Pushed {len(items)} items to hub")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="App Store review collector")
    parser.add_argument("--store", choices=["apple", "google", "both"], default="both")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    items = []
    if args.store in ("apple", "both"):
        items.extend(collect_apple_reviews(args.limit))
    if args.store in ("google", "both"):
        items.extend(collect_google_reviews())

    print(f"Total: {len(items)} reviews collected")

    if items and not args.dry_run:
        push_to_hub(items)
    elif items:
        for item in items[:5]:
            print(f"  [{item['sentiment']}] ({item['metadata'].get('rating', '?')}/5) {item['text'][:80]}...")


if __name__ == "__main__":
    main()
