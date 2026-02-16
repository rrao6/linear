#!/usr/bin/env python3
"""
Browser automation for JS-rendered competitor pages.
Uses Playwright for headless Chrome with API interception to capture
channel data from SPAs that load content via XHR/fetch.

Setup:
    pip install playwright
    playwright install chromium

Usage:
    python3 tools/scanner/browser.py                          # All sites
    python3 tools/scanner/browser.py --site pluto              # One site
    python3 tools/scanner/browser.py --site tubi --screenshot  # With screenshot
    python3 tools/scanner/browser.py --output channels.json
"""

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def ensure_playwright():
    """Check if playwright is available."""
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        print("Playwright not installed. Run:")
        print("  pip install playwright && playwright install chromium")
        return False


# ─── API INTERCEPTION SCRAPERS ───

def scrape_pluto(page, screenshot_dir=None):
    """Scrape Pluto TV — intercept API calls for channel data."""
    url = "https://pluto.tv/en/live-tv"
    api_responses = []

    def handle_response(response):
        req_url = response.url
        # Pluto loads channels from their API
        if ("api.pluto.tv" in req_url or "service-channels" in req_url
                or "/channels" in req_url or "boot" in req_url):
            try:
                body = response.text()
                if body and len(body) > 500:
                    api_responses.append({"url": req_url, "body": body})
            except Exception:
                pass

    page.on("response", handle_response)

    print(f"  Loading {url} (intercepting API)...", flush=True)
    page.goto(url, wait_until="networkidle", timeout=45000)
    time.sleep(5)

    # Scroll to trigger lazy loads
    for _ in range(8):
        page.evaluate("window.scrollBy(0, 2000)")
        time.sleep(1)

    if screenshot_dir:
        page.screenshot(path=str(screenshot_dir / "pluto_tv.png"), full_page=False)

    # Parse API responses for channel data
    channels = set()
    categories = set()

    for resp in api_responses:
        body = resp["body"]
        try:
            data = json.loads(body)
            # Handle array of channels
            items = data if isinstance(data, list) else data.get("data", data.get("channels", []))
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("title") or ""
                        if name and len(name) > 1:
                            channels.add(name)
                        cat = item.get("category") or item.get("categoryName") or ""
                        if cat:
                            categories.add(cat)
        except (json.JSONDecodeError, TypeError):
            # Try regex on raw body
            names = re.findall(r'"name"\s*:\s*"([^"]{2,60})"', body)
            channels.update(names)
            cats = re.findall(r'"category(?:Name)?"\s*:\s*"([^"]{2,40})"', body)
            categories.update(cats)

    # Also parse rendered page as fallback
    content = page.content()
    title_matches = re.findall(r'"title"\s*:\s*"([^"]{3,80})"', content)
    name_matches = re.findall(r'"name"\s*:\s*"([^"]{3,60})"', content)

    # Merge but filter noise
    all_names = channels | set(title_matches) | set(name_matches)
    filtered = {
        c for c in all_names
        if not c.startswith("http")
        and "cookie" not in c.lower()
        and "privacy" not in c.lower()
        and "sign in" not in c.lower()
        and "pluto" not in c.lower()
        and len(c) > 2
        and len(c) < 80
    }

    return {
        "service": "pluto_tv",
        "url": url,
        "channel_count": len(filtered),
        "api_responses_captured": len(api_responses),
        "categories": sorted(categories)[:30],
        "sample_channels": sorted(list(filtered))[:150],
        "method": "playwright_api_interception",
        "page_size": len(content),
        "date": date.today().isoformat(),
    }


def scrape_tubi(page, screenshot_dir=None):
    """Scrape Tubi — intercept API calls for channel/content data."""
    url = "https://tubitv.com/live"
    api_responses = []

    def handle_response(response):
        req_url = response.url
        # Tubi loads data from their content API
        if ("tubitv.com/oz/" in req_url or "tubitv.com/api/" in req_url
                or "/cms/" in req_url or "content" in req_url.lower()
                or "/containers" in req_url or "/channels" in req_url
                or "/epg" in req_url):
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct or "javascript" in ct:
                    body = response.text()
                    if body and len(body) > 200:
                        api_responses.append({
                            "url": req_url,
                            "size": len(body),
                            "body": body[:500000],  # Cap at 500KB
                        })
            except Exception:
                pass

    page.on("response", handle_response)

    print(f"  Loading {url} (intercepting API)...", flush=True)
    page.goto(url, wait_until="networkidle", timeout=45000)
    time.sleep(5)

    # Scroll aggressively to load all rows
    for _ in range(20):
        page.evaluate("window.scrollBy(0, 1500)")
        time.sleep(0.8)

    # Scroll back up to ensure all content loaded
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(2)

    if screenshot_dir:
        page.screenshot(path=str(screenshot_dir / "tubi_live.png"), full_page=False)

    content = page.content()

    # Parse intercepted API responses
    channels = set()
    channel_ids = set()
    categories = set()

    for resp in api_responses:
        body = resp["body"]
        try:
            data = json.loads(body)
            # Tubi API responses can be nested
            _extract_tubi_channels(data, channels, channel_ids, categories)
        except (json.JSONDecodeError, TypeError):
            # Regex fallback
            titles = re.findall(r'"title"\s*:\s*"([^"]{3,80})"', body)
            channels.update(t for t in titles if not t.startswith("http"))
            ids = re.findall(r'"id"\s*:\s*"?(\d{4,})"?', body)
            channel_ids.update(ids)

    # Also extract from rendered HTML
    title_matches = re.findall(r'"title"\s*:\s*"([^"]{3,80})"', content)
    slug_matches = re.findall(r'/live/(\d+)', content)
    channel_ids.update(slug_matches)

    # Filter channel names
    all_names = channels | set(
        t for t in title_matches
        if not t.startswith("http") and "Tubi" not in t and len(t) < 60
    )
    filtered = {
        c for c in all_names
        if len(c) > 2
        and not c.startswith("http")
        and "privacy" not in c.lower()
        and "cookie" not in c.lower()
    }

    return {
        "service": "tubi",
        "url": url,
        "channel_count_names": len(filtered),
        "channel_count_ids": len(channel_ids),
        "api_responses_captured": len(api_responses),
        "api_data_bytes": sum(r["size"] for r in api_responses),
        "categories": sorted(categories)[:30],
        "sample_channels": sorted(list(filtered))[:150],
        "method": "playwright_api_interception",
        "page_size": len(content),
        "date": date.today().isoformat(),
    }


def _extract_tubi_channels(data, channels, channel_ids, categories, depth=0):
    """Recursively extract channel info from Tubi API JSON."""
    if depth > 5:
        return
    if isinstance(data, dict):
        # Check if this looks like a channel/content item
        if "title" in data and ("id" in data or "type" in data):
            title = data.get("title", "")
            if title and isinstance(title, str) and len(title) > 2:
                channels.add(title)
            cid = data.get("id")
            if cid:
                channel_ids.add(str(cid))
            cat = data.get("category") or data.get("genre") or data.get("type") or ""
            if cat and isinstance(cat, str):
                categories.add(cat)

        # Recurse into values
        for v in data.values():
            if isinstance(v, (dict, list)):
                _extract_tubi_channels(v, channels, channel_ids, categories, depth + 1)

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                _extract_tubi_channels(item, channels, channel_ids, categories, depth + 1)


def scrape_roku(page, screenshot_dir=None):
    """Scrape Roku Channel — intercept API for channel data."""
    url = "https://therokuchannel.roku.com/live"
    api_responses = []

    def handle_response(response):
        req_url = response.url
        if ("roku.com" in req_url and
                ("/api/" in req_url or "/channels" in req_url
                 or "/guide" in req_url or "/linear" in req_url
                 or "content" in req_url.lower())):
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    body = response.text()
                    if body and len(body) > 200:
                        api_responses.append({"url": req_url, "body": body[:500000]})
            except Exception:
                pass

    page.on("response", handle_response)

    print(f"  Loading {url} (intercepting API)...", flush=True)
    page.goto(url, wait_until="networkidle", timeout=45000)
    time.sleep(5)

    for _ in range(10):
        page.evaluate("window.scrollBy(0, 2000)")
        time.sleep(1)

    if screenshot_dir:
        page.screenshot(path=str(screenshot_dir / "roku_channel.png"), full_page=False)

    content = page.content()
    channels = set()
    categories = set()

    for resp in api_responses:
        body = resp["body"]
        try:
            data = json.loads(body)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get("title") or item.get("name") or ""
                        if name:
                            channels.add(name)
            elif isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict):
                                name = item.get("title") or item.get("name") or ""
                                if name:
                                    channels.add(name)
        except (json.JSONDecodeError, TypeError):
            titles = re.findall(r'"title"\s*:\s*"([^"]{3,80})"', body)
            channels.update(titles)

    # DOM fallback
    title_matches = re.findall(r'"title"\s*:\s*"([^"]{3,80})"', content)
    channels.update(t for t in title_matches if not t.startswith("http"))

    cat_matches = re.findall(r'"category"\s*:\s*"([^"]+)"', content)
    categories.update(cat_matches)

    filtered = {
        c for c in channels
        if len(c) > 2 and not c.startswith("http") and len(c) < 80
    }

    return {
        "service": "roku_channel",
        "url": url,
        "channel_count": len(filtered),
        "api_responses_captured": len(api_responses),
        "categories": sorted(categories)[:30],
        "sample_channels": sorted(list(filtered))[:150],
        "method": "playwright_api_interception",
        "page_size": len(content),
        "date": date.today().isoformat(),
    }


def scrape_samsung(page, screenshot_dir=None):
    """Scrape Samsung TV Plus — intercept API for channel data."""
    url = "https://www.samsung.com/us/tvplus/"
    api_responses = []

    def handle_response(response):
        req_url = response.url
        if "samsung" in req_url and ("channel" in req_url.lower() or "tvplus" in req_url.lower()):
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    body = response.text()
                    if body and len(body) > 200:
                        api_responses.append({"url": req_url, "body": body[:500000]})
            except Exception:
                pass

    page.on("response", handle_response)

    print(f"  Loading {url} (intercepting API)...", flush=True)
    page.goto(url, wait_until="networkidle", timeout=45000)
    time.sleep(5)

    for _ in range(15):
        page.evaluate("window.scrollBy(0, 2000)")
        time.sleep(0.8)

    if screenshot_dir:
        page.screenshot(path=str(screenshot_dir / "samsung_tv_plus.png"), full_page=False)

    content = page.content()
    channels = set()

    for resp in api_responses:
        body = resp["body"]
        try:
            data = json.loads(body)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get("title") or item.get("name") or ""
                        if name:
                            channels.add(name)
        except (json.JSONDecodeError, TypeError):
            titles = re.findall(r'"title"\s*:\s*"([^"]{3,60})"', body)
            channels.update(titles)

    # DOM extraction
    elements = page.query_selector_all('[class*="channel"], [class*="card"], [class*="program"]')
    for el in elements:
        try:
            text = el.inner_text().strip()
            if text and 2 < len(text) < 60:
                channels.add(text.split("\n")[0].strip())
        except Exception:
            pass

    # Marketing claim
    count_claims = re.findall(r"(\d+)\+?\s*(?:live\s*)?(?:TV\s*)?channels", content, re.I)

    filtered = {
        c for c in channels
        if len(c) > 2 and not c.startswith("http") and len(c) < 80
        and "samsung" not in c.lower() and "cookie" not in c.lower()
    }

    return {
        "service": "samsung_tv_plus",
        "url": url,
        "channel_count_claimed": max(int(c) for c in count_claims) if count_claims else None,
        "channel_count_extracted": len(filtered),
        "api_responses_captured": len(api_responses),
        "sample_channels": sorted(list(filtered))[:150],
        "method": "playwright_api_interception",
        "page_size": len(content),
        "date": date.today().isoformat(),
    }


BROWSER_SITES = {
    "pluto": ("Pluto TV", scrape_pluto),
    "tubi": ("Tubi", scrape_tubi),
    "roku": ("Roku Channel", scrape_roku),
    "samsung": ("Samsung TV Plus", scrape_samsung),
}


def run_browser_scrape(site_id=None, screenshot=False):
    """Run headless browser scraping with API interception."""
    if not ensure_playwright():
        return {}

    from playwright.sync_api import sync_playwright

    targets = {site_id: BROWSER_SITES[site_id]} if site_id else BROWSER_SITES
    results = {}

    screenshot_dir = None
    if screenshot:
        screenshot_dir = ROOT / "intel" / "scans" / date.today().isoformat() / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        for sid, (name, scraper) in targets.items():
            print(f"\nScraping {name}...", flush=True)
            # Fresh page per site to avoid state leakage
            page = context.new_page()
            try:
                data = scraper(page, screenshot_dir)
                results[sid] = data
                count = (data.get("channel_count")
                        or data.get("channel_count_names")
                        or data.get("channel_count_extracted")
                        or data.get("channel_count_claimed")
                        or "?")
                apis = data.get("api_responses_captured", 0)
                print(f"  -> {count} channels found ({apis} API responses captured)")
            except Exception as e:
                results[sid] = {"service": sid, "error": str(e)}
                print(f"  -> ERROR: {e}")
            finally:
                page.close()

        browser.close()

    return results


def main():
    parser = argparse.ArgumentParser(description="Browser automation for channel scraping")
    parser.add_argument("--site", choices=list(BROWSER_SITES.keys()),
                       help="Specific site to scrape")
    parser.add_argument("--screenshot", action="store_true",
                       help="Save screenshots")
    parser.add_argument("--output", help="Output JSON path")
    args = parser.parse_args()

    results = run_browser_scrape(args.site, args.screenshot)

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
