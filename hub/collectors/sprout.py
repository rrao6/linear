"""Sprout Social collector for brand mention sentiment.

Collects mentions and messages from Sprout Social's API for sentiment analysis.

Usage:
    python3 -m hub.collectors.sprout                    # Collect recent mentions
    python3 -m hub.collectors.sprout --probe            # Discover available endpoints
    python3 -m hub.collectors.sprout --days 7           # Last 7 days
    python3 -m hub.collectors.sprout --dry-run          # Preview without pushing
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from hub.config import SPROUT_SOCIAL_API_KEY

HUB_URL = os.environ.get("HUB_URL", "http://localhost:8888")
BASE_URL = "https://api.sproutsocial.com"

# Keywords relevant to Tubi linear TV monitoring
KEYWORDS = ["tubi", "linear", "live tv", "fast channel", "free streaming",
            "epg", "program guide", "free tv", "cord cutting"]


def _api_request(method, path, data=None, timeout=15):
    """Make an authenticated request to the Sprout Social API."""
    if not SPROUT_SOCIAL_API_KEY:
        raise RuntimeError("SPROUT_SOCIAL_API_KEY not set in environment")

    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {SPROUT_SOCIAL_API_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return {
            "status": resp.status,
            "data": json.loads(resp.read().decode()),
        }
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()
        except Exception:
            pass
        return {
            "status": e.code,
            "error": str(e),
            "body": body_text,
        }
    except Exception as e:
        return {"status": 0, "error": str(e)}


def probe_api():
    """Probe the Sprout Social API to discover available endpoints and customer ID.

    Tests multiple endpoint patterns to find what works with the current API key.
    """
    print("Probing Sprout Social API...")
    print(f"  Base URL: {BASE_URL}")
    print(f"  API Key: {'set (' + SPROUT_SOCIAL_API_KEY[:8] + '...)' if SPROUT_SOCIAL_API_KEY else 'NOT SET'}")
    print()

    if not SPROUT_SOCIAL_API_KEY:
        print("ERROR: SPROUT_SOCIAL_API_KEY not set. Add it to .env")
        return None

    results = {}

    # Step 1: Get customer metadata to discover customer ID
    print("--- Step 1: Discover customer ID ---")
    for path in [
        "/v1/metadata/client",
        "/v1/metadata",
    ]:
        resp = _api_request("GET", path)
        status = resp.get("status", 0)
        print(f"  GET {path} -> {status}")
        if status == 200:
            results["metadata"] = resp["data"]
            print(f"    Response: {json.dumps(resp['data'])[:300]}")
        else:
            print(f"    Error: {resp.get('error', resp.get('body', 'unknown'))[:200]}")

    # Extract customer_id from metadata
    customer_id = None
    meta = results.get("metadata", {})
    if isinstance(meta, dict):
        data = meta.get("data", [])
        if isinstance(data, list) and data:
            customer_id = data[0].get("customer_id")
        elif "customer_id" in meta:
            customer_id = meta["customer_id"]

    if customer_id:
        print(f"\n  Found customer_id: {customer_id}")
    else:
        print("\n  Could not extract customer_id from metadata.")
        print("  Trying common paths without customer_id...")

    # Step 2: Probe message/mention endpoints
    print("\n--- Step 2: Probe message endpoints ---")

    # Build list of paths to try
    message_paths = []
    if customer_id:
        message_paths.extend([
            ("POST", f"/v1/{customer_id}/messages", {"filters": ["inbox"]}),
            ("POST", f"/v1/{customer_id}/messages", None),
            ("GET", f"/v1/{customer_id}/messages", None),
        ])
    # Also try without customer_id for certain API versions
    message_paths.extend([
        ("GET", "/v1/messages", None),
        ("GET", "/v2/messages", None),
    ])

    for method, path, body in message_paths:
        resp = _api_request(method, path, data=body)
        status = resp.get("status", 0)
        print(f"  {method} {path} -> {status}")
        if status == 200:
            results["messages_endpoint"] = path
            results["messages_method"] = method
            preview = json.dumps(resp["data"])[:300]
            print(f"    Response: {preview}")
            break
        else:
            err = resp.get("error", resp.get("body", "unknown"))
            print(f"    Error: {str(err)[:200]}")

    # Step 3: Probe listening endpoints
    print("\n--- Step 3: Probe listening/analytics endpoints ---")
    analytics_paths = []
    if customer_id:
        analytics_paths.extend([
            ("POST", f"/v1/{customer_id}/analytics/profiles", {
                "fields": ["lifetime_snapshot.followers_count"],
                "filters": [],
            }),
            ("POST", f"/v1/{customer_id}/analytics/posts", {
                "fields": ["post_data.lifetime.impressions"],
                "filters": [],
            }),
            ("GET", f"/v1/{customer_id}/listening/topics", None),
        ])
    analytics_paths.extend([
        ("GET", "/v1/listening/topics", None),
    ])

    for method, path, body in analytics_paths:
        resp = _api_request(method, path, data=body)
        status = resp.get("status", 0)
        print(f"  {method} {path} -> {status}")
        if status == 200:
            results[f"analytics_{path.split('/')[-1]}"] = {
                "endpoint": path,
                "method": method,
            }
            preview = json.dumps(resp["data"])[:300]
            print(f"    Response: {preview}")
        else:
            err = resp.get("error", resp.get("body", "unknown"))
            print(f"    Error: {str(err)[:200]}")

    # Summary
    print("\n--- Probe Summary ---")
    print(f"  Customer ID: {customer_id or 'not found'}")
    print(f"  Messages endpoint: {results.get('messages_endpoint', 'not found')}")
    print(f"  Working endpoints: {len([k for k in results if k not in ('metadata',)])}")

    return {
        "customer_id": customer_id,
        "endpoints": results,
    }


def collect_mentions(customer_id=None, days=3, limit=50):
    """Collect brand mentions from Sprout Social.

    Tries the messages endpoint first, then falls back to analytics/posts.
    """
    if not SPROUT_SOCIAL_API_KEY:
        print("ERROR: SPROUT_SOCIAL_API_KEY not set. Add it to .env")
        return []

    # Discover customer_id if not provided
    if not customer_id:
        resp = _api_request("GET", "/v1/metadata/client")
        if resp.get("status") == 200:
            data = resp["data"].get("data", [])
            if data:
                customer_id = data[0].get("customer_id")
        if not customer_id:
            print("  Could not discover customer_id. Use --probe first.")
            return []

    print(f"  Collecting from Sprout Social (customer: {customer_id}, last {days} days)...")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    items = []

    # Try messages endpoint
    resp = _api_request("POST", f"/v1/{customer_id}/messages", {
        "filters": ["inbox"],
        "since": since_iso,
        "limit": limit,
    })

    if resp.get("status") == 200:
        messages = resp["data"].get("data", [])
        print(f"  Messages endpoint returned {len(messages)} items")
        for msg in messages:
            text = msg.get("text", "") or msg.get("content", "")
            if not text:
                continue
            # Filter for relevance
            text_lower = text.lower()
            if not any(kw in text_lower for kw in KEYWORDS):
                continue
            sentiment = _classify_sentiment(text)
            items.append({
                "source": "sprout",
                "text": text[:500],
                "sentiment": sentiment.get("sentiment", "neutral"),
                "sentiment_score": sentiment.get("score", 0.0),
                "topics": sentiment.get("topics", ["general"]),
                "author": msg.get("from", {}).get("name", "") if isinstance(msg.get("from"), dict) else str(msg.get("from", "")),
                "url": msg.get("permalink", ""),
                "metadata": {
                    "sprout_id": msg.get("id", ""),
                    "network": msg.get("network", ""),
                    "created_time": msg.get("created_time", ""),
                    "customer_id": customer_id,
                },
            })
    else:
        print(f"  Messages endpoint failed ({resp.get('status')}), trying analytics/posts...")

        # Fallback: analytics/posts
        resp = _api_request("POST", f"/v1/{customer_id}/analytics/posts", {
            "fields": [
                "post_data.lifetime.impressions",
                "post_data.lifetime.engagements",
            ],
            "filters": [],
            "metrics": ["lifetime.impressions"],
        })

        if resp.get("status") == 200:
            posts = resp["data"].get("data", [])
            print(f"  Analytics/posts returned {len(posts)} items")
            for post in posts:
                text = post.get("text", "") or post.get("perma_link", "")
                if not text:
                    continue
                text_lower = text.lower()
                if not any(kw in text_lower for kw in KEYWORDS):
                    continue
                sentiment = _classify_sentiment(text)
                items.append({
                    "source": "sprout",
                    "text": text[:500],
                    "sentiment": sentiment.get("sentiment", "neutral"),
                    "sentiment_score": sentiment.get("score", 0.0),
                    "topics": sentiment.get("topics", ["general"]),
                    "author": "",
                    "url": post.get("perma_link", ""),
                    "metadata": {
                        "sprout_id": post.get("id", ""),
                        "network": post.get("network", ""),
                        "customer_id": customer_id,
                    },
                })
        else:
            print(f"  Analytics/posts also failed ({resp.get('status')})")
            print(f"  Error: {resp.get('error', resp.get('body', 'unknown'))[:200]}")

    print(f"  Collected {len(items)} relevant items from Sprout Social")
    return items


def _classify_sentiment(text):
    """Classify sentiment — reuses the reddit collector's classifier."""
    try:
        from hub.collectors.reddit import classify_sentiment
        return classify_sentiment(text)
    except Exception:
        # Inline fallback
        text_lower = text.lower()
        neg = ["bad", "terrible", "awful", "hate", "worst", "broken", "crash", "annoying", "frustrating"]
        pos = ["great", "love", "amazing", "good", "best", "enjoy", "recommend", "awesome"]
        n = sum(1 for w in neg if w in text_lower)
        p = sum(1 for w in pos if w in text_lower)
        if n > p:
            return {"sentiment": "negative", "score": -0.5, "topics": ["general"]}
        elif p > n:
            return {"sentiment": "positive", "score": 0.5, "topics": ["general"]}
        return {"sentiment": "neutral", "score": 0.0, "topics": ["general"]}


KNOWN_ENDPOINTS = [
    ("GET",  "/metadata/client",                    "Account metadata (customer_id, users)"),
    ("GET",  "/metadata/client/groups",             "Social profile groups"),
    ("GET",  "/{cid}/messages/",                    "Smart Inbox messages"),
    ("POST", "/{cid}/analytics/profiles",           "Profile analytics (followers, engagement)"),
    ("POST", "/{cid}/analytics/posts",              "Post analytics (impressions, clicks)"),
    ("GET",  "/{cid}/listening/topics",             "Listening topics"),
    ("POST", "/{cid}/listening/topics/{tid}/metrics","Listening sentiment metrics"),
    ("GET",  "/{cid}/metadata/tags",                "Message tags"),
]


def probe_api():
    """Discover available Sprout Social API endpoints."""
    print("=" * 60)
    print("Sprout Social API Endpoint Discovery")
    print("=" * 60)

    if not SPROUT_API_KEY:
        print("\n  No SPROUT_SOCIAL_API_KEY set.")
        print("  Set via: export SPROUT_SOCIAL_API_KEY=your_token")
        print("  Obtain from: Sprout Social → Settings → API & Integrations")
        print("\n  Probing without auth (protected endpoints will show errors)...\n")

    # Step 1: metadata to get client ID
    print("[1] Probing metadata endpoint...")
    client_id = get_client_id()
    meta = _get("/metadata/client")
    if meta:
        cid_from_meta = None
        for item in meta.get("data", []):
            cid_from_meta = item.get("customer_id")
            if cid_from_meta:
                break
        if cid_from_meta:
            client_id = cid_from_meta
        print(f"  OK — customer_id: {client_id}")
    else:
        print(f"  FAILED — decoded client_id guess: {client_id}")

    # Step 2: probe each endpoint
    print("\n[2] Probing all known endpoints...\n")
    results = {}
    for method, path, desc in KNOWN_ENDPOINTS:
        display_path = path
        actual_path = path.replace("{cid}", str(client_id) if client_id else "0")
        actual_path = actual_path.replace("{tid}", "0")  # placeholder topic

        if "{cid}" in path and not client_id:
            results[path] = "SKIP (no customer_id)"
            print(f"  SKIP  {method:4s} {display_path}")
            print(f"        {desc}")
            continue

        if method == "GET":
            resp = _get(actual_path)
        else:
            resp = _post(actual_path, {"filters": {}})

        if resp is not None:
            results[path] = "OK"
            detail = ""
            if isinstance(resp, dict) and "data" in resp:
                detail = f" ({len(resp['data'])} items)"
            print(f"  OK    {method:4s} {display_path}{detail}")
        else:
            results[path] = "FAIL"
            print(f"  FAIL  {method:4s} {display_path}")
        print(f"        {desc}")

    # Summary
    ok = sum(1 for v in results.values() if v == "OK")
    print(f"\n{'=' * 60}")
    print(f"Accessible: {ok}/{len(results)} endpoints")
    if client_id:
        print(f"Customer ID: {client_id}")
    print(f"Base URL: {SPROUT_BASE_URL}")
    print()


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
    parser = argparse.ArgumentParser(description="Sprout Social sentiment collector")
    parser.add_argument("--probe", action="store_true", help="Probe API to discover endpoints")
    parser.add_argument("--customer-id", help="Sprout Social customer ID (auto-discovered if omitted)")
    parser.add_argument("--days", type=int, default=3, help="Lookback period in days")
    parser.add_argument("--limit", type=int, default=50, help="Max items to collect")
    parser.add_argument("--dry-run", action="store_true", help="Don't push to hub")
    args = parser.parse_args()

    if args.probe:
        result = probe_api()
        if result:
            print(f"\nProbe complete. Use discovered customer_id: {result.get('customer_id')}")
        return

    print(f"Collecting from Sprout Social (last {args.days} days)...")
    items = collect_mentions(
        customer_id=args.customer_id,
        days=args.days,
        limit=args.limit,
    )
    print(f"Found {len(items)} relevant items")

    if items and not args.dry_run:
        push_to_hub(items)
    elif items:
        for item in items[:5]:
            print(f"  [{item['sentiment']}] {item['text'][:80]}...")


if __name__ == "__main__":
    main()
