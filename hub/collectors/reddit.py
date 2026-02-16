"""Reddit sentiment collector for Linear TV feedback.

Collects posts and comments from r/Tubi, r/cordcutters, r/FAST, and other relevant subreddits.

Usage:
    python3 -m hub.collectors.reddit              # Collect from all subreddits
    python3 -m hub.collectors.reddit --sub Tubi    # Specific subreddit
    python3 -m hub.collectors.reddit --days 7      # Last 7 days
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from hub.config import OPENAI_API_KEY

HUB_URL = os.environ.get("HUB_URL", "http://localhost:8888")

SUBREDDITS = ["Tubi", "cordcutters", "FAST", "FreeStreaming", "StreamingBestOf"]
KEYWORDS = ["tubi", "linear", "live tv", "fast channel", "free streaming", "epg", "program guide"]


def classify_sentiment(text: str) -> dict:
    """Use OpenAI to classify sentiment of text."""
    if not OPENAI_API_KEY:
        # Fallback: simple keyword-based
        text_lower = text.lower()
        negative_words = ["bad", "terrible", "awful", "hate", "worst", "broken", "bug", "crash", "annoying", "frustrating", "ads"]
        positive_words = ["great", "love", "amazing", "good", "best", "enjoy", "recommend", "nice", "awesome"]
        neg = sum(1 for w in negative_words if w in text_lower)
        pos = sum(1 for w in positive_words if w in text_lower)
        if neg > pos:
            return {"sentiment": "negative", "score": -0.5, "topics": ["general"]}
        elif pos > neg:
            return {"sentiment": "positive", "score": 0.5, "topics": ["general"]}
        return {"sentiment": "neutral", "score": 0.0, "topics": ["general"]}

    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": "Classify the sentiment of this user feedback about Tubi or streaming TV. Return JSON: {\"sentiment\": \"positive|negative|neutral|mixed\", \"score\": float from -1 to 1, \"topics\": [list of topics like 'ads', 'content', 'epg', 'buffering', 'channels', 'ui', 'pricing', 'search']}"
            }, {
                "role": "user",
                "content": text[:500]
            }],
            response_format={"type": "json_object"},
            max_tokens=100,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"  Classification error: {e}")
        return {"sentiment": "neutral", "score": 0.0, "topics": ["general"]}


def collect_reddit(subreddits=None, days=3, limit=50):
    """Collect relevant posts from Reddit."""
    try:
        import praw
    except ImportError:
        print("Install praw: pip3 install praw")
        print("Falling back to RSS-based collection...")
        return collect_reddit_rss(subreddits or SUBREDDITS, days, limit)

    reddit_id = os.environ.get("REDDIT_CLIENT_ID", "")
    reddit_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")

    if not reddit_id or not reddit_secret:
        print("No REDDIT_CLIENT_ID/SECRET set. Falling back to RSS collection...")
        return collect_reddit_rss(subreddits or SUBREDDITS, days, limit)

    reddit = praw.Reddit(
        client_id=reddit_id,
        client_secret=reddit_secret,
        user_agent="linear-hub-sentiment/1.0",
    )

    cutoff = datetime.now() - timedelta(days=days)
    items = []

    for sub_name in (subreddits or SUBREDDITS):
        try:
            subreddit = reddit.subreddit(sub_name)
            for post in subreddit.new(limit=limit):
                post_time = datetime.fromtimestamp(post.created_utc)
                if post_time < cutoff:
                    continue
                # Check relevance
                text = f"{post.title} {post.selftext}".lower()
                if not any(kw in text for kw in KEYWORDS):
                    continue
                full_text = f"{post.title}\n{post.selftext}"
                sentiment = classify_sentiment(full_text)
                items.append({
                    "source": "reddit",
                    "text": full_text[:500],
                    "sentiment": sentiment.get("sentiment", "neutral"),
                    "sentiment_score": sentiment.get("score", 0.0),
                    "topics": sentiment.get("topics", []),
                    "author": str(post.author) if post.author else "",
                    "url": f"https://reddit.com{post.permalink}",
                    "metadata": {"subreddit": sub_name, "score": post.score, "comments": post.num_comments},
                })
            print(f"  r/{sub_name}: collected {len(items)} relevant posts")
        except Exception as e:
            print(f"  r/{sub_name}: error - {e}")

    return items


def collect_reddit_rss(subreddits, days, limit):
    """Fallback: collect via Reddit RSS (no auth needed)."""
    import urllib.request
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    items = []
    for sub_name in subreddits:
        url = f"https://www.reddit.com/r/{sub_name}/new.json?limit={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "linear-hub/1.0"})
            resp = urllib.request.urlopen(req, context=ctx, timeout=10)
            data = json.loads(resp.read().decode())
            posts = data.get("data", {}).get("children", [])

            for post_data in posts:
                post = post_data.get("data", {})
                text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
                if not any(kw in text for kw in KEYWORDS):
                    continue
                full_text = f"{post.get('title', '')}\n{post.get('selftext', '')}"
                sentiment = classify_sentiment(full_text)
                items.append({
                    "source": "reddit",
                    "text": full_text[:500],
                    "sentiment": sentiment.get("sentiment", "neutral"),
                    "sentiment_score": sentiment.get("score", 0.0),
                    "topics": sentiment.get("topics", []),
                    "author": post.get("author", ""),
                    "url": f"https://reddit.com{post.get('permalink', '')}",
                    "metadata": {"subreddit": sub_name, "score": post.get("score", 0)},
                })
            print(f"  r/{sub_name}: {len(posts)} posts, {len(items)} relevant")
        except Exception as e:
            print(f"  r/{sub_name}: error - {e}")

    return items


def push_to_hub(items):
    """Push collected items to the hub API."""
    import urllib.request

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
    parser = argparse.ArgumentParser(description="Reddit sentiment collector")
    parser.add_argument("--sub", help="Specific subreddit")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true", help="Don't push to hub")
    args = parser.parse_args()

    subs = [args.sub] if args.sub else None
    print(f"Collecting from Reddit (last {args.days} days)...")
    items = collect_reddit(subs, args.days, args.limit)
    print(f"Found {len(items)} relevant items")

    if items and not args.dry_run:
        push_to_hub(items)
    elif items:
        for item in items[:5]:
            print(f"  [{item['sentiment']}] {item['text'][:80]}...")


if __name__ == "__main__":
    main()
