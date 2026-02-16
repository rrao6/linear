#!/usr/bin/env python3
"""
Deep fetch individual URLs and extract structured competitive intel.
Uses AI-assisted extraction via the existing OpenAI key.

Usage:
    python3 tools/scanner/deep_fetch.py <url> [--prompt "custom extraction prompt"]
    python3 tools/scanner/deep_fetch.py --batch sources.json

This is the "go deeper" tool — for when the basic scanner finds something
interesting and you need to extract structured data from it.
"""

import argparse
import json
import os
import sys
import ssl
from datetime import date
from pathlib import Path
from urllib.request import urlopen, Request

ROOT = Path(__file__).resolve().parents[2]

# Load .env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


def fetch_url(url, timeout=20):
    """Fetch URL content."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERROR: {e}"


def extract_with_ai(content, prompt, url=""):
    """Use OpenAI to extract structured data from page content."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "No OPENAI_API_KEY in .env"}

    model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    # Truncate content to fit context window
    max_chars = 60000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[TRUNCATED]"

    import urllib.request
    import json as j

    system_msg = (
        "You are a competitive intelligence analyst for Tubi (FAST/Linear TV). "
        "Extract structured data from web pages. Be precise with numbers. "
        "Always note what is explicitly stated vs inferred. "
        "Output JSON when possible."
    )

    user_msg = f"URL: {url}\n\nPROMPT: {prompt}\n\nPAGE CONTENT:\n{content}"

    body = j.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,
        "max_tokens": 4000,
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

    try:
        with urlopen(req, timeout=60, context=ctx) as resp:
            result = j.loads(resp.read())
            return {
                "extraction": result["choices"][0]["message"]["content"],
                "model": model,
                "tokens": result.get("usage", {}),
            }
    except Exception as e:
        return {"error": str(e)}


def deep_fetch(url, prompt=None):
    """Fetch a URL and extract structured competitive intel."""
    if not prompt:
        prompt = (
            "Extract ALL competitive intelligence from this page. Include:\n"
            "1. Channel counts (exact numbers if stated)\n"
            "2. Content categories and notable channels\n"
            "3. Platform availability\n"
            "4. Features (DVR, personalization, etc)\n"
            "5. Pricing / ad model\n"
            "6. Any audience/usage stats\n"
            "7. Recent announcements or changes\n"
            "8. Partnerships mentioned\n"
            "Output as structured JSON."
        )

    print(f"Fetching {url}...", flush=True)
    content = fetch_url(url)

    if content.startswith("ERROR:"):
        return {"url": url, "error": content}

    print(f"  Got {len(content):,} bytes. Extracting with AI...", flush=True)
    result = extract_with_ai(content, prompt, url)

    output = {
        "url": url,
        "date": date.today().isoformat(),
        "page_size": len(content),
        "prompt": prompt,
        **result,
    }

    print(f"  Done. Tokens: {result.get('tokens', {})}")
    return output


def main():
    parser = argparse.ArgumentParser(description="Deep fetch competitive intel")
    parser.add_argument("url", nargs="?", help="URL to fetch")
    parser.add_argument("--prompt", help="Custom extraction prompt")
    parser.add_argument("--batch", help="JSON file with URLs to batch fetch")
    parser.add_argument("--output", help="Output file path")
    args = parser.parse_args()

    if args.batch:
        with open(args.batch) as f:
            urls = json.load(f)
        results = []
        for item in urls:
            url = item if isinstance(item, str) else item.get("url")
            prompt = None if isinstance(item, str) else item.get("prompt")
            results.append(deep_fetch(url, prompt))
        output = {"batch_date": date.today().isoformat(), "results": results}
    elif args.url:
        output = deep_fetch(args.url, args.prompt)
    else:
        parser.print_help()
        return

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved to {out_path}")
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
