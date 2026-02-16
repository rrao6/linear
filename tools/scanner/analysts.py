#!/usr/bin/env python3
"""
Specialist analysis agents: Threat, Opportunity, Trend, Profiler.
Each runs independently and can be parallelized.

Usage:
    python3 tools/scanner/analysts.py --input classified.json --output analysis.json
    python3 tools/scanner/analysts.py --input classified.json --agent threats
"""

import argparse
import json
import os
import ssl
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

ROOT = Path(__file__).resolve().parents[2]

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def call_openai(prompt, model="gpt-4o", temperature=0.2, max_tokens=4000):
    """Call OpenAI API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("No OPENAI_API_KEY in environment")

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
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

    with urlopen(req, timeout=90, context=ctx) as resp:
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"], result.get("usage", {})


# ─── THREAT ANALYST ───

THREAT_PROMPT = """You are a Threat Analyst for Tubi, a free ad-supported streaming TV (FAST) service owned by Fox Corp.

Tubi has ~340 linear channels, is a pure-app FAST (no OEM integration), gets 31.5% of linear TVT from Amazon Fire TV deeplinks, and competes across 4 tiers:
- Tier 1: Platform-Integrated FAST (Samsung TV Plus, Roku Channel, Amazon Fire TV, LG, Vizio, Google TV, TCL+)
- Tier 2: Pure-App FAST (Pluto TV, Xumo, Sling Freestream, Plex)
- Tier 3: vMVPD (YouTube TV, Hulu Live, Fubo)
- Tier 4: SVOD with linear (Netflix, Peacock, ESPN standalone)

Analyze these classified intel items and identify the TOP threats to Tubi.

For each threat, output valid JSON:
{{
  "threats": [
    {{
      "threat_type": "direct|indirect|potential|existential",
      "severity": 1-10,
      "source_competitor": "competitor_id",
      "title": "short threat title",
      "description": "what is happening and why it threatens Tubi",
      "defensive_action": "what Tubi should consider doing",
      "timeframe": "immediate|short_term|medium_term|long_term",
      "supporting_intel": ["article hashes"]
    }}
  ]
}}

INTEL ITEMS:
{intel}
"""


def analyze_threats(intel_items):
    """Run threat analysis on classified intel."""
    formatted = json.dumps([i if isinstance(i, dict) else i.to_dict()
                           for i in intel_items], indent=2)
    prompt = THREAT_PROMPT.format(intel=formatted)
    response, usage = call_openai(prompt)

    # Extract JSON from response
    try:
        # Handle markdown code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        result = json.loads(response)
    except json.JSONDecodeError:
        result = {"threats": [], "parse_error": response[:500]}

    return result, usage


# ─── OPPORTUNITY FINDER ───

OPPORTUNITY_PROMPT = """You are an Opportunity Finder for Tubi, a free ad-supported streaming TV (FAST) service owned by Fox Corp.

Tubi strengths: Fox Sports pipeline (Super Bowl, NFL, World Cup), VOD+Linear hybrid (2.4x engagement), True Crime cluster (30%+ entertainment TVT), 340 channels, free price point.
Tubi weaknesses: No OEM integration, Amazon dependency (31.5% TVT), linear TVT declining (-18% since Sep 2024), lower ad fill on linear.

Analyze these classified intel items and identify the TOP opportunities for Tubi.

For each opportunity, output valid JSON:
{{
  "opportunities": [
    {{
      "opportunity_type": "content|feature|market|partnership|technology",
      "potential_value": 1-10,
      "feasibility": 1-10,
      "title": "short opportunity title",
      "description": "what the opportunity is",
      "action_items": ["specific actions Tubi could take"],
      "competitor_gap": "what gap this exploits in competitor offerings",
      "supporting_intel": ["article hashes"]
    }}
  ]
}}

INTEL ITEMS:
{intel}
"""


def analyze_opportunities(intel_items):
    """Run opportunity analysis on classified intel."""
    formatted = json.dumps([i if isinstance(i, dict) else i.to_dict()
                           for i in intel_items], indent=2)
    prompt = OPPORTUNITY_PROMPT.format(intel=formatted)
    response, usage = call_openai(prompt)

    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        result = json.loads(response)
    except json.JSONDecodeError:
        result = {"opportunities": [], "parse_error": response[:500]}

    return result, usage


# ─── TREND TRACKER ───

TREND_PROMPT = """You are a Trend Tracker for the FAST/streaming TV industry, analyzing for Tubi.

Analyze these classified intel items and identify the KEY TRENDS in the FAST/streaming market.

For each trend, output valid JSON:
{{
  "trends": [
    {{
      "name": "short trend name",
      "category": "technology|content|distribution|monetization|audience|regulation",
      "direction": "accelerating|stable|declining|emerging",
      "strength": 1-10,
      "description": "what is this trend",
      "tubi_implication": "what this means for Tubi specifically",
      "prediction": "where this is heading in 6-12 months",
      "timeframe": "immediate|short_term|medium_term|long_term",
      "supporting_intel": ["article hashes"]
    }}
  ]
}}

INTEL ITEMS:
{intel}
"""


def analyze_trends(intel_items):
    """Run trend analysis on classified intel."""
    formatted = json.dumps([i if isinstance(i, dict) else i.to_dict()
                           for i in intel_items], indent=2)
    prompt = TREND_PROMPT.format(intel=formatted)
    response, usage = call_openai(prompt)

    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        result = json.loads(response)
    except json.JSONDecodeError:
        result = {"trends": [], "parse_error": response[:500]}

    return result, usage


# ─── COMPETITOR PROFILER ───

PROFILER_PROMPT = """You are a Competitor Profiler for Tubi's competitive intelligence team.

Based on these classified intel items, build/update profiles for each competitor mentioned.

For each competitor, output valid JSON:
{{
  "profiles": [
    {{
      "competitor_id": "id from intel",
      "name": "display name",
      "recent_moves": ["list of recent actions from the intel"],
      "strategy_focus": "what they seem to be focused on",
      "threat_level": 1-10,
      "strengths_observed": ["from this intel batch"],
      "weaknesses_observed": ["from this intel batch"],
      "tubi_comparison": "how they compare to Tubi on the dimensions mentioned"
    }}
  ]
}}

INTEL ITEMS:
{intel}
"""


def analyze_profiles(intel_items):
    """Run competitor profiling on classified intel."""
    formatted = json.dumps([i if isinstance(i, dict) else i.to_dict()
                           for i in intel_items], indent=2)
    prompt = PROFILER_PROMPT.format(intel=formatted)
    response, usage = call_openai(prompt)

    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        result = json.loads(response)
    except json.JSONDecodeError:
        result = {"profiles": [], "parse_error": response[:500]}

    return result, usage


# ─── RUN ALL AGENTS ───

AGENT_MAP = {
    "threats": ("Threat Analyst", analyze_threats),
    "opportunities": ("Opportunity Finder", analyze_opportunities),
    "trends": ("Trend Tracker", analyze_trends),
    "profiles": ("Competitor Profiler", analyze_profiles),
}


def run_all_agents(intel_items, agents=None, max_workers=4):
    """Run all specialist agents in parallel."""
    if not intel_items:
        return {"error": "No intel items to analyze"}

    agents = agents or list(AGENT_MAP.keys())
    results = {}
    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    print(f"\nRunning {len(agents)} specialist agents on {len(intel_items)} intel items...",
          flush=True)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for agent_name in agents:
            if agent_name not in AGENT_MAP:
                continue
            display_name, func = AGENT_MAP[agent_name]
            futures[executor.submit(func, intel_items)] = (agent_name, display_name)

        for future in as_completed(futures):
            agent_name, display_name = futures[future]
            try:
                result, usage = future.result()
                results[agent_name] = result
                for k in total_tokens:
                    total_tokens[k] += usage.get(k, 0)
                # Count items in result
                count = 0
                for v in result.values():
                    if isinstance(v, list):
                        count = len(v)
                        break
                print(f"  [{display_name}] {count} items found")
            except Exception as e:
                results[agent_name] = {"error": str(e)}
                print(f"  [{display_name}] ERROR: {e}")

    results["tokens"] = total_tokens
    return results


def main():
    parser = argparse.ArgumentParser(description="Specialist analysis agents")
    parser.add_argument("--input", required=True, help="Classified intel JSON")
    parser.add_argument("--output", help="Output JSON path")
    parser.add_argument("--agent", choices=list(AGENT_MAP.keys()),
                       help="Run specific agent only")
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    intel_items = data.get("intel", [])
    print(f"Loaded {len(intel_items)} intel items")

    agents = [args.agent] if args.agent else None
    results = run_all_agents(intel_items, agents)

    output = {
        "analysis_date": datetime.now().isoformat(),
        "intel_count": len(intel_items),
        **results,
    }

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved to {out}")
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
