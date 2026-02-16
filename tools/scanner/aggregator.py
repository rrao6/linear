#!/usr/bin/env python3
"""
Parallel RSS/Atom feed aggregator using feedparser.
Adapted from Tubi Radar multi-agent architecture.

Usage:
    python3 tools/scanner/aggregator.py                    # Fetch all feeds
    python3 tools/scanner/aggregator.py --competitor pluto_tv  # One competitor
    python3 tools/scanner/aggregator.py --output results.json
"""

import argparse
import json
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import feedparser
import yaml

from models import ArticleCandidate

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "tools" / "scanner" / "config.yaml"

# feedparser timeout
socket.setdefaulttimeout(15)


def load_config():
    """Load YAML config."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def fetch_feed(feed_config, competitor_id, lookback_hours=72):
    """Fetch a single RSS/Atom feed and return ArticleCandidates."""
    label = feed_config["label"]
    url = feed_config["url"]
    articles = []

    try:
        parsed = feedparser.parse(url)
        if parsed.bozo and not parsed.entries:
            return label, articles, f"Parse error: {parsed.bozo_exception}"

        cutoff = datetime.now() - timedelta(hours=lookback_hours)

        for entry in parsed.entries[:25]:  # Cap per feed
            # Parse publication date
            pub_date = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_dt = datetime(*entry.published_parsed[:6])
                pub_date = pub_dt.isoformat()
                if pub_dt < cutoff:
                    continue  # Skip old articles
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                pub_dt = datetime(*entry.updated_parsed[:6])
                pub_date = pub_dt.isoformat()
                if pub_dt < cutoff:
                    continue

            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()

            if not title or not link:
                continue

            # Clean HTML from summary
            import re
            summary = re.sub(r"<[^>]+>", "", summary)[:500]

            articles.append(ArticleCandidate(
                competitor_id=competitor_id,
                source_label=label,
                title=title,
                url=link,
                published_at=pub_date,
                snippet=summary,
            ))

        return label, articles, None

    except Exception as e:
        return label, articles, str(e)


def fetch_all_feeds(config, competitor_id=None, max_workers=10):
    """Fetch all feeds in parallel using ThreadPoolExecutor."""
    global_cfg = config.get("global", {})
    lookback = global_cfg.get("lookback_hours", 72)
    max_workers = min(max_workers, global_cfg.get("max_concurrent_feeds", 10))

    # Build feed tasks: (feed_config, competitor_id)
    tasks = []

    # Tubi's own feeds
    tubi_cfg = config.get("tubi", {})
    if not competitor_id or competitor_id == "tubi":
        for feed in tubi_cfg.get("feeds", []):
            tasks.append((feed, "tubi"))

    # Competitor feeds
    for comp in config.get("competitors", []):
        cid = comp["id"]
        if competitor_id and cid != competitor_id:
            continue
        for feed in comp.get("feeds", []):
            tasks.append((feed, cid))

    # Industry feeds (no specific competitor)
    if not competitor_id:
        for feed in config.get("industry_feeds", []):
            tasks.append((feed, "industry"))
        for feed in config.get("publication_feeds", []):
            tasks.append((feed, "industry"))

    all_articles = []
    seen_hashes = set()
    errors = []

    print(f"Fetching {len(tasks)} feeds with {max_workers} workers...", flush=True)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_feed, feed_cfg, cid, lookback): (feed_cfg["label"], cid)
            for feed_cfg, cid in tasks
        }

        for future in as_completed(futures):
            label, cid = futures[future]
            try:
                feed_label, articles, error = future.result()
                if error:
                    errors.append({"feed": feed_label, "error": error})
                    print(f"  [{feed_label}] ERROR: {error}")
                else:
                    # Deduplicate
                    new = 0
                    for a in articles:
                        if a.hash not in seen_hashes:
                            seen_hashes.add(a.hash)
                            all_articles.append(a)
                            new += 1
                    print(f"  [{feed_label}] {new} new / {len(articles)} total")
            except Exception as e:
                errors.append({"feed": label, "error": str(e)})
                print(f"  [{label}] EXCEPTION: {e}")

    # Sort by publication date (newest first)
    all_articles.sort(key=lambda a: a.published_at or "", reverse=True)

    print(f"\nTotal: {len(all_articles)} unique articles from {len(tasks)} feeds "
          f"({len(errors)} errors)")

    return all_articles, errors


def main():
    parser = argparse.ArgumentParser(description="Parallel RSS aggregator")
    parser.add_argument("--competitor", help="Fetch feeds for one competitor only")
    parser.add_argument("--output", help="Output JSON path")
    parser.add_argument("--lookback", type=int, default=72, help="Lookback hours")
    args = parser.parse_args()

    config = load_config()
    if args.lookback != 72:
        config.setdefault("global", {})["lookback_hours"] = args.lookback

    articles, errors = fetch_all_feeds(config, args.competitor)

    output = {
        "scan_date": datetime.now().isoformat(),
        "total_articles": len(articles),
        "total_errors": len(errors),
        "articles": [a.to_dict() for a in articles],
        "errors": errors,
    }

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved to {out}")
    else:
        # Print summary
        by_competitor = {}
        for a in articles:
            by_competitor.setdefault(a.competitor_id, []).append(a)
        print("\nBy competitor:")
        for cid, arts in sorted(by_competitor.items(), key=lambda x: -len(x[1])):
            print(f"  {cid}: {len(arts)} articles")
            for a in arts[:3]:
                print(f"    - {a.title[:80]}")


if __name__ == "__main__":
    main()
