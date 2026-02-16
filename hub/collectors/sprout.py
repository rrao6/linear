"""Sprout Social collector — pulls social listening data into the hub.

Usage:
    python3 -m hub.collectors.sprout                    # Collect mentions
    python3 -m hub.collectors.sprout --profile 12345    # Specific profile
    python3 -m hub.collectors.sprout --dry-run           # Preview only
"""

import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from hub.collectors.reddit import classify_sentiment

HUB_URL = os.environ.get("HUB_URL", "http://localhost:8888")
SPROUT_API_KEY = os.environ.get("SPROUT_SOCIAL_API_KEY", "")
SPROUT_BASE_URL = "https://api.sproutsocial.com/v1"


def _headers():
    return {
        "Authorization": f"Bearer {SPROUT_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _get(path, params=None):
    """GET request to Sprout Social API."""
    url = f"{SPROUT_BASE_URL}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  Sprout API error {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"  Sprout API error: {e}")
        return None


def _post(path, body):
    """POST request to Sprout Social API."""
    url = f"{SPROUT_BASE_URL}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        print(f"  Sprout API error {e.code}: {body_text[:200]}")
        return None
    except Exception as e:
        print(f"  Sprout API error: {e}")
        return None


def get_client_id():
    """Extract client ID from the base64-encoded API key."""
    try:
        decoded = base64.b64decode(SPROUT_API_KEY).decode()
        parts = decoded.split("|")
        return parts[0] if parts else None
    except Exception:
        return None


def list_profiles():
    """List available social profiles/customers."""
    client_id = get_client_id()
    # Try metadata endpoint
    data = _get(f"/{client_id}/metadata/client")
    if data:
        return data
    # Try alternate
    data = _get("/metadata/client")
    return data


def collect_messages(profile_id=None, days=7, limit=100):
    """Collect messages/mentions from Sprout Social."""
    if not SPROUT_API_KEY:
        print("No SPROUT_SOCIAL_API_KEY set. Skipping.")
        return []

    client_id = get_client_id()
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Try analytics endpoint for listening data
    filters = {
        "since": since,
        "limit": limit,
    }
    if profile_id:
        filters["profile_id"] = profile_id

    items = []

    # Try messages endpoint
    data = _post(f"/{client_id}/messages", {"filters": filters})
    if not data:
        # Try alternate endpoints
        data = _get(f"/{client_id}/messages", {"since": since, "limit": str(limit)})

    if data and isinstance(data, dict):
        messages = data.get("data", data.get("messages", []))
        if isinstance(messages, list):
            for msg in messages:
                text = msg.get("text", msg.get("content", msg.get("message", "")))
                if not text:
                    continue
                sentiment = classify_sentiment(text)
                items.append({
                    "source": "sprout_social",
                    "text": text[:500],
                    "sentiment": sentiment.get("sentiment", "neutral"),
                    "sentiment_score": sentiment.get("score", 0.0),
                    "topics": sentiment.get("topics", []),
                    "author": msg.get("author", {}).get("name", msg.get("from", "")),
                    "url": msg.get("permalink", msg.get("url", "")),
                    "metadata": {
                        "platform": msg.get("network", msg.get("platform", "unknown")),
                        "sprout_id": msg.get("id", ""),
                        "created": msg.get("created_time", msg.get("created_at", "")),
                    },
                })

    print(f"  Sprout Social: {len(items)} messages collected")
    return items


def collect_listening(topic_id=None, days=7):
    """Collect from Sprout Social Listening (if available)."""
    if not SPROUT_API_KEY:
        return []

    client_id = get_client_id()
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Try listening topics endpoint
    data = _get(f"/{client_id}/listening/topics")
    if not data:
        print("  Sprout Listening: no topics endpoint available")
        return []

    topics = data.get("data", [])
    print(f"  Sprout Listening: {len(topics)} topics found")

    items = []
    for topic in topics:
        tid = topic.get("id", "")
        if topic_id and str(tid) != str(topic_id):
            continue
        mentions = _get(f"/{client_id}/listening/topics/{tid}/mentions", {"since": since})
        if mentions and isinstance(mentions, dict):
            for m in mentions.get("data", []):
                text = m.get("text", "")
                if not text:
                    continue
                sentiment = classify_sentiment(text)
                items.append({
                    "source": "sprout_listening",
                    "text": text[:500],
                    "sentiment": sentiment.get("sentiment", "neutral"),
                    "sentiment_score": sentiment.get("score", 0.0),
                    "topics": sentiment.get("topics", []) + [topic.get("name", "")],
                    "author": m.get("author", ""),
                    "url": m.get("url", ""),
                    "metadata": {
                        "platform": m.get("network", ""),
                        "topic": topic.get("name", ""),
                        "sprout_id": m.get("id", ""),
                    },
                })

    print(f"  Sprout Listening: {len(items)} mentions collected")
    return items


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
    parser = argparse.ArgumentParser(description="Sprout Social collector")
    parser.add_argument("--profile", help="Specific profile ID")
    parser.add_argument("--topic", help="Listening topic ID")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probe", action="store_true", help="Probe API to discover endpoints")
    args = parser.parse_args()

    if args.probe:
        print("Probing Sprout Social API...")
        client_id = get_client_id()
        print(f"  Client ID: {client_id}")
        print("\nTrying metadata...")
        meta = list_profiles()
        if meta:
            print(f"  Metadata: {json.dumps(meta, indent=2)[:500]}")
        else:
            print("  No metadata response")
        return

    print(f"Collecting from Sprout Social (last {args.days} days)...")
    items = collect_messages(args.profile, args.days, args.limit)
    items.extend(collect_listening(args.topic, args.days))
    print(f"Total: {len(items)} items")

    if items and not args.dry_run:
        push_to_hub(items)
    elif items:
        for item in items[:5]:
            print(f"  [{item['sentiment']}] ({item['metadata'].get('platform', '?')}) {item['text'][:80]}...")


if __name__ == "__main__":
    main()
