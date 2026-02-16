#!/usr/bin/env python3
"""
Competitive Intelligence Scanner for Linear/FAST TV.

Usage:
    python3 tools/scanner/scan.py --mode news       # Scan RSS feeds for relevant articles
    python3 tools/scanner/scan.py --mode sites       # Scrape competitor sites for channel data
    python3 tools/scanner/scan.py --mode search      # Run web searches for market intel
    python3 tools/scanner/scan.py --mode full        # Run all scans
    python3 tools/scanner/scan.py --mode report      # Generate summary report from latest scan data

Outputs saved to: intel/scans/YYYY-MM-DD/
"""

import argparse
import json
import os
import sys
import re
from datetime import datetime, date
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from xml.etree import ElementTree
import ssl
import time

# Project root
ROOT = Path(__file__).resolve().parents[2]
SCAN_DIR = ROOT / "intel" / "scans"
TODAY = date.today().isoformat()

# Import sources
sys.path.insert(0, str(Path(__file__).parent))
from sources import COMPETITOR_SITES, NEWS_FEEDS, SEARCH_QUERIES, TRACKING_DIMENSIONS


def ensure_dirs():
    """Create scan output directories."""
    scan_dir = SCAN_DIR / TODAY
    for sub in ["news", "sites", "search", "reports"]:
        (scan_dir / sub).mkdir(parents=True, exist_ok=True)
    return scan_dir


def fetch_url(url, timeout=15):
    """Fetch a URL with a browser-like user agent."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERROR: {e}"


def fetch_rss(url, timeout=15):
    """Fetch and parse an RSS/Atom feed."""
    content = fetch_url(url, timeout)
    if content.startswith("ERROR:"):
        return {"error": content, "items": []}

    items = []
    try:
        root = ElementTree.fromstring(content)
        # Handle RSS 2.0
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            desc = item.findtext("description", "")
            items.append({
                "title": title.strip(),
                "link": link.strip(),
                "date": pub_date.strip(),
                "description": desc[:500].strip(),
            })
        # Handle Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", ns):
            title = entry.findtext("atom:title", "", ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            pub = entry.findtext("atom:published", "", ns) or entry.findtext("atom:updated", "", ns)
            summary = entry.findtext("atom:summary", "", ns) or entry.findtext("atom:content", "", ns)
            items.append({
                "title": title.strip(),
                "link": link.strip(),
                "date": pub.strip(),
                "description": (summary or "")[:500].strip(),
            })
    except ElementTree.ParseError:
        return {"error": "Failed to parse feed XML", "items": []}

    return {"items": items[:50]}  # Cap at 50 most recent


def is_relevant(text, topics):
    """Check if text contains any of the topic keywords (case-insensitive)."""
    text_lower = text.lower()
    keywords = [
        "fast", "free ad-supported", "linear tv", "live tv",
        "tubi", "pluto tv", "roku channel", "samsung tv plus",
        "amazon fire tv", "xumo", "watchfree", "lg channels",
        "youtube tv", "vmvpd", "cord cut", "ctv", "avod",
        "streaming tv", "live channels", "channel lineup",
        "nfl", "sports streaming", "epg", "tv guide",
    ]
    keywords.extend([t.lower() for t in topics])
    return any(kw in text_lower for kw in keywords)


def scan_news(scan_dir):
    """Scan RSS feeds for relevant competitive intel articles."""
    print("\n=== SCANNING NEWS FEEDS ===\n")
    all_relevant = []

    for feed_id, feed in NEWS_FEEDS.items():
        print(f"  Fetching {feed['name']}... ", end="", flush=True)
        result = fetch_rss(feed.get("rss", ""), timeout=20)

        if "error" in result and result["error"]:
            print(f"ERROR: {result['error']}")
            continue

        relevant = []
        for item in result["items"]:
            combined = f"{item['title']} {item['description']}"
            if is_relevant(combined, feed.get("topics", [])):
                item["source"] = feed["name"]
                item["source_id"] = feed_id
                relevant.append(item)

        print(f"{len(relevant)} relevant / {len(result['items'])} total")
        all_relevant.extend(relevant)

    # Save results
    output_path = scan_dir / "news" / "feed_scan.json"
    with open(output_path, "w") as f:
        json.dump({
            "scan_date": TODAY,
            "total_relevant": len(all_relevant),
            "articles": all_relevant,
        }, f, indent=2)

    # Also save a readable markdown summary
    md_path = scan_dir / "news" / "feed_scan.md"
    with open(md_path, "w") as f:
        f.write(f"# News Feed Scan — {TODAY}\n\n")
        f.write(f"**{len(all_relevant)} relevant articles found**\n\n")
        for item in all_relevant[:30]:  # Top 30
            f.write(f"### {item['title']}\n")
            f.write(f"- **Source**: {item['source']}\n")
            f.write(f"- **Date**: {item['date']}\n")
            f.write(f"- **Link**: {item['link']}\n")
            if item["description"]:
                # Strip HTML tags
                desc = re.sub(r'<[^>]+>', '', item["description"])[:200]
                f.write(f"- **Preview**: {desc}\n")
            f.write("\n")

    print(f"\n  Saved {len(all_relevant)} articles to {output_path}")
    return all_relevant


def scan_sites(scan_dir):
    """Scrape competitor sites for channel data."""
    print("\n=== SCANNING COMPETITOR SITES ===\n")
    results = {}

    for site_id, site in COMPETITOR_SITES.items():
        print(f"  Fetching {site['name']} ({site['url']})... ", end="", flush=True)
        content = fetch_url(site["url"], timeout=20)

        if content.startswith("ERROR:"):
            print(f"FAILED: {content}")
            results[site_id] = {
                "name": site["name"],
                "url": site["url"],
                "status": "error",
                "error": content,
            }
            continue

        # Extract basic stats from the page
        page_size = len(content)
        # Try to count channel-like patterns
        # Look for numbers near "channel" mentions
        channel_mentions = len(re.findall(r'channel', content, re.IGNORECASE))

        results[site_id] = {
            "name": site["name"],
            "url": site["url"],
            "status": "fetched",
            "page_size_bytes": page_size,
            "channel_mentions": channel_mentions,
            "notes": site.get("notes", ""),
            "raw_snippet": content[:2000],  # First 2KB for analysis
        }
        print(f"OK ({page_size:,} bytes, {channel_mentions} channel mentions)")
        time.sleep(0.5)  # Be polite

    # Save results
    output_path = scan_dir / "sites" / "site_scan.json"
    with open(output_path, "w") as f:
        json.dump({
            "scan_date": TODAY,
            "sites_scanned": len(results),
            "results": results,
        }, f, indent=2)

    # Save readable summary
    md_path = scan_dir / "sites" / "site_scan.md"
    with open(md_path, "w") as f:
        f.write(f"# Competitor Site Scan — {TODAY}\n\n")
        f.write(f"**{len(results)} sites scanned**\n\n")
        f.write("| Service | Status | Page Size | Channel Mentions | Notes |\n")
        f.write("|---|---|---|---|---|\n")
        for site_id, r in results.items():
            status = r["status"]
            size = f"{r.get('page_size_bytes', 0):,}" if status == "fetched" else "—"
            mentions = r.get("channel_mentions", "—")
            notes = r.get("notes", "")
            f.write(f"| {r['name']} | {status} | {size} | {mentions} | {notes} |\n")

    print(f"\n  Saved scan results to {output_path}")
    return results


def generate_report(scan_dir):
    """Generate a combined report from all scan data."""
    print("\n=== GENERATING REPORT ===\n")

    report_path = scan_dir / "reports" / "scan_report.md"

    # Load news data if exists
    news_path = scan_dir / "news" / "feed_scan.json"
    news_data = None
    if news_path.exists():
        with open(news_path) as f:
            news_data = json.load(f)

    # Load site data if exists
    sites_path = scan_dir / "sites" / "site_scan.json"
    sites_data = None
    if sites_path.exists():
        with open(sites_path) as f:
            sites_data = json.load(f)

    with open(report_path, "w") as f:
        f.write(f"# Competitive Intelligence Scan Report — {TODAY}\n\n")
        f.write(f"> Generated: {datetime.now().isoformat()}\n")
        f.write("> Run: `python3 tools/scanner/scan.py --mode full`\n\n")

        # News summary
        if news_data:
            articles = news_data.get("articles", [])
            f.write(f"## News Scan\n\n")
            f.write(f"**{len(articles)} relevant articles** found across {len(NEWS_FEEDS)} feeds.\n\n")

            # Group by source
            by_source = {}
            for a in articles:
                src = a.get("source", "Unknown")
                by_source.setdefault(src, []).append(a)

            for src, items in sorted(by_source.items()):
                f.write(f"### {src} ({len(items)} articles)\n\n")
                for item in items[:5]:
                    title = item.get("title", "Untitled")
                    link = item.get("link", "")
                    f.write(f"- [{title}]({link})\n")
                if len(items) > 5:
                    f.write(f"- ... and {len(items) - 5} more\n")
                f.write("\n")
        else:
            f.write("## News Scan\n\nNo news data available. Run `--mode news` first.\n\n")

        # Site scan summary
        if sites_data:
            results = sites_data.get("results", {})
            f.write(f"## Competitor Site Scan\n\n")
            f.write(f"**{len(results)} sites** scanned.\n\n")
            f.write("| Service | Status | Size | Notes |\n")
            f.write("|---|---|---|---|\n")
            for sid, r in results.items():
                status = r["status"]
                size = f"{r.get('page_size_bytes', 0):,}b" if status == "fetched" else "error"
                notes = r.get("notes", "")
                f.write(f"| {r['name']} | {status} | {size} | {notes} |\n")
            f.write("\n")
        else:
            f.write("## Competitor Site Scan\n\nNo site data available. Run `--mode sites` first.\n\n")

        # Search queries for manual/AI follow-up
        f.write("## Recommended Search Queries\n\n")
        f.write("Run these via web search or AI agent for deeper intel:\n\n")
        for category, queries in SEARCH_QUERIES.items():
            f.write(f"### {category.replace('_', ' ').title()}\n")
            for q in queries:
                f.write(f"- `{q}`\n")
            f.write("\n")

        # Tracking dimensions checklist
        f.write("## Tracking Dimensions Checklist\n\n")
        f.write("For each competitor, verify these dimensions:\n\n")
        for dim in TRACKING_DIMENSIONS:
            f.write(f"- [ ] {dim.replace('_', ' ').title()}\n")

    print(f"  Report saved to {report_path}")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Competitive Intelligence Scanner")
    parser.add_argument(
        "--mode",
        choices=["news", "sites", "search", "full", "report"],
        default="full",
        help="Scan mode",
    )
    args = parser.parse_args()

    scan_dir = ensure_dirs()
    print(f"Scan output: {scan_dir}")

    if args.mode in ("news", "full"):
        scan_news(scan_dir)

    if args.mode in ("sites", "full"):
        scan_sites(scan_dir)

    if args.mode in ("report", "full"):
        generate_report(scan_dir)

    print(f"\n✓ Scan complete. Results in {scan_dir}")


if __name__ == "__main__":
    main()
