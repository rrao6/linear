#!/usr/bin/env python3
"""
Parse competitor pages for channel counts using regex extraction.
Faster and more accurate than AI extraction for structured data.

Usage:
    python3 tools/scanner/parse_channels.py           # Parse all sites
    python3 tools/scanner/parse_channels.py --site xumo  # Parse one site
"""

import argparse
import json
import re
import ssl
from datetime import date
from pathlib import Path
from urllib.request import urlopen, Request

ROOT = Path(__file__).resolve().parents[2]


def fetch(url, timeout=20):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None


# Site-specific parsers
def parse_xumo(content):
    """Xumo: channel slugs + category names from JSON."""
    slugs = re.findall(r'"slug":"([^"]+)"', content)
    categories = re.findall(r'"name":"([^"]+)"', content)
    return {
        "channel_count": len(set(slugs)),
        "category_count": len(set(categories)),
        "categories": sorted(set(categories)),
        "method": "slug count from page JSON",
    }


def parse_samsung(content):
    """Samsung: channel count from marketing text."""
    counts = re.findall(r"(\d+)\+?\s*(?:live\s*)?(?:TV\s*)?channels", content, re.IGNORECASE)
    return {
        "channel_count_claimed": max([int(c) for c in counts]) if counts else None,
        "method": "marketing text extraction (no channel list exposed in HTML)",
        "note": "Samsung does not expose channel names in HTML; count is from marketing copy",
    }


def parse_pluto(content):
    """Pluto: extract from JSON-LD or page content."""
    # Look for category slugs
    slugs = re.findall(r'"slug":"([^"]+)"', content)
    categories = re.findall(r'"categoryName":"([^"]+)"', content)
    titles = re.findall(r'"title":"([^"]+)"', content)
    return {
        "channel_count_titles": len(set(titles)),
        "channel_count_slugs": len(set(slugs)),
        "categories": sorted(set(categories))[:30],
        "method": "title/slug count from page (may be incomplete due to dynamic loading)",
    }


def parse_tubi(content):
    """Tubi: extract titles from initial page load."""
    titles = re.findall(r'"title":"([^"]+)"', content)
    unique = set(titles)
    # Filter out obvious non-channel titles
    channels = [t for t in unique if len(t) > 2 and not t.startswith("http")]
    return {
        "initial_load_count": len(channels),
        "note": "Full channel count requires dynamic page rendering. User reports ~340 channels total.",
        "sample_channels": sorted(channels)[:50],
        "method": "title extraction from initial HTML (partial)",
    }


def parse_vizio(content):
    """Vizio WatchFree+."""
    counts = re.findall(r"(\d+)\+?\s*(?:free\s*)?(?:live\s*)?channels", content, re.IGNORECASE)
    titles = re.findall(r'"title":"([^"]+)"', content)
    return {
        "channel_count_claimed": max([int(c) for c in counts]) if counts else None,
        "title_count": len(set(titles)),
        "method": "marketing text + title extraction",
    }


def parse_generic(content):
    """Generic parser for any site."""
    counts = re.findall(r"(\d+)\+?\s*(?:free\s*)?(?:live\s*)?channels", content, re.IGNORECASE)
    titles = re.findall(r'"title":"([^"]+)"', content)
    slugs = re.findall(r'"slug":"([^"]+)"', content)
    return {
        "channel_count_claimed": max([int(c) for c in counts]) if counts else None,
        "title_count": len(set(titles)),
        "slug_count": len(set(slugs)),
        "method": "generic extraction",
    }


SITES = {
    "xumo": {
        "url": "https://play.xumo.com/channels",
        "parser": parse_xumo,
    },
    "samsung": {
        "url": "https://www.samsung.com/us/tvplus/",
        "parser": parse_samsung,
    },
    "pluto": {
        "url": "https://pluto.tv/en/live-tv",
        "parser": parse_pluto,
    },
    "tubi": {
        "url": "https://tubitv.com/live",
        "parser": parse_tubi,
    },
    "vizio": {
        "url": "https://www.vizio.com/en/watchfreeplus",
        "parser": parse_vizio,
    },
}


def run_parse(site_id=None):
    results = {}
    targets = {site_id: SITES[site_id]} if site_id else SITES

    for sid, site in targets.items():
        print(f"Parsing {sid} ({site['url']})...", flush=True)
        content = fetch(site["url"])
        if not content:
            print(f"  FAILED to fetch")
            results[sid] = {"error": "fetch failed"}
            continue

        parser = site.get("parser", parse_generic)
        data = parser(content)
        data["url"] = site["url"]
        data["date"] = date.today().isoformat()
        data["page_size"] = len(content)
        results[sid] = data
        print(f"  {json.dumps({k: v for k, v in data.items() if k != 'sample_channels' and k != 'categories'}, indent=2)}")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=list(SITES.keys()), help="Specific site to parse")
    parser.add_argument("--output", help="Output JSON path")
    args = parser.parse_args()

    results = run_parse(args.site)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved to {out}")
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
