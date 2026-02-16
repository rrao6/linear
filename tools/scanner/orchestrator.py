#!/usr/bin/env python3
"""
Competitive Intelligence Pipeline Orchestrator.
6-phase swarm pipeline adapted from Tubi Radar architecture.

Phases:
  1. COLLECT  — Parallel RSS aggregation + channel count scraping
  2. CLASSIFY — AI classification (relevance, impact, category)
  3. ANALYZE  — Specialist agents (threats, opportunities, trends, profiles)
  4. MEMORY   — Store to vector DB, check duplicates, build context
  5. SYNTHESIZE — Generate executive brief
  6. REPORT   — Save all outputs

Usage:
    python3 tools/scanner/orchestrator.py                          # Full pipeline
    python3 tools/scanner/orchestrator.py --phase collect          # One phase
    python3 tools/scanner/orchestrator.py --competitor pluto_tv    # One competitor
    python3 tools/scanner/orchestrator.py --lookback 168           # 7 days back
    python3 tools/scanner/orchestrator.py --skip-memory            # No vector DB
    python3 tools/scanner/orchestrator.py --skip-analysis          # Collect+classify only
"""

import argparse
import json
import os
import ssl
import sys
from datetime import datetime, date
from pathlib import Path
from urllib.request import urlopen, Request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import yaml
from aggregator import fetch_all_feeds, load_config
from classifier import classify_all, group_similar
from analysts import run_all_agents
from parse_channels import run_parse
from models import ScanRun


def ensure_output_dir(run_id):
    """Create output directory for this run."""
    out_dir = ROOT / "intel" / "scans" / date.today().isoformat() / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


# ─── PHASE 1: COLLECT ───

def phase_collect(config, competitor_id=None):
    """Collect articles from RSS feeds and scrape channel counts."""
    print("\n" + "=" * 60)
    print("PHASE 1: COLLECT")
    print("=" * 60)

    # 1a. RSS aggregation
    print("\n--- RSS Aggregation ---")
    articles, feed_errors = fetch_all_feeds(config, competitor_id)

    # 1b. Channel count scraping (only if no specific competitor filter)
    channel_data = {}
    if not competitor_id:
        print("\n--- Channel Count Scraping ---")
        try:
            channel_data = run_parse()
        except Exception as e:
            print(f"  Channel scraping failed: {e}")

    return {
        "articles": articles,
        "feed_errors": feed_errors,
        "channel_data": channel_data,
    }


# ─── PHASE 2: CLASSIFY ───

def phase_classify(articles, config):
    """Classify articles by relevance and impact."""
    print("\n" + "=" * 60)
    print("PHASE 2: CLASSIFY")
    print("=" * 60)

    global_cfg = config.get("global", {})
    model = global_cfg.get("models", {}).get("fast", "gpt-4o-mini")
    min_rel = global_cfg.get("min_relevance_score", 4.0)
    min_imp = global_cfg.get("min_impact_score", 4.0)

    classified, tokens = classify_all(articles, model=model)
    grouped = group_similar(classified)

    # Filter
    filtered = [
        c for c in grouped
        if c.relevance_score >= min_rel and c.impact_score >= min_imp
    ]

    print(f"\nPipeline: {len(articles)} collected -> {len(classified)} classified "
          f"-> {len(grouped)} grouped -> {len(filtered)} filtered")

    return {
        "all_classified": [c.to_dict() for c in classified],
        "filtered": [c.to_dict() for c in filtered],
        "tokens": tokens,
    }


# ─── PHASE 3: ANALYZE ───

def phase_analyze(filtered_intel):
    """Run specialist analysis agents."""
    print("\n" + "=" * 60)
    print("PHASE 3: ANALYZE")
    print("=" * 60)

    if not filtered_intel:
        print("  No intel to analyze.")
        return {}

    results = run_all_agents(filtered_intel)
    return results


# ─── PHASE 4: MEMORY ───

def phase_memory(classified_data, analysis_data, skip=False):
    """Store to vector memory and check for duplicates."""
    print("\n" + "=" * 60)
    print("PHASE 4: MEMORY")
    print("=" * 60)

    if skip:
        print("  Skipped (--skip-memory)")
        return {"skipped": True}

    try:
        from memory import VectorMemory
        mem = VectorMemory()

        # Store intel
        intel = classified_data.get("filtered", [])
        intel_count = mem.store_intel(intel)
        print(f"  Stored {intel_count} intel items")

        # Store profiles
        profiles = analysis_data.get("profiles", {}).get("profiles", [])
        profile_count = mem.store_profiles(profiles)
        print(f"  Stored {profile_count} profiles")

        # Store trends
        trends = analysis_data.get("trends", {}).get("trends", [])
        trend_count = mem.store_trends(trends)
        print(f"  Stored {trend_count} trends")

        stats = mem.stats()
        print(f"  Memory stats: {json.dumps(stats)}")

        return {
            "stored_intel": intel_count,
            "stored_profiles": profile_count,
            "stored_trends": trend_count,
            "stats": stats,
        }

    except Exception as e:
        print(f"  Memory phase failed: {e}")
        return {"error": str(e)}


# ─── PHASE 5: SYNTHESIZE ───

SYNTHESIS_PROMPT = """You are generating an executive competitive intelligence brief for Tubi's leadership team.

Tubi is a free ad-supported streaming TV (FAST) service owned by Fox Corp with ~340 linear channels.

Based on the analysis below, write a concise executive brief (600-800 words) with these sections:

## Executive Summary
2-3 sentences on the most important developments this scan cycle.

## Critical Threats
Top 3-5 threats ranked by severity. For each: what it is, why it matters to Tubi, recommended action.

## Key Opportunities
Top 3-5 opportunities ranked by priority (value x feasibility). For each: what it is, what Tubi should do.

## Market Trends
Top 3-5 trends affecting FAST/streaming. For each: direction, strength, Tubi implication.

## Competitor Moves
Notable actions by specific competitors. Group by tier.

## Recommended Actions
Prioritized list of 5-7 specific actions Tubi should take based on this intel.

ANALYSIS DATA:
{analysis}

CLASSIFIED INTEL (top items by impact):
{intel}

CHANNEL COUNT DATA:
{channels}
"""


def phase_synthesize(classified_data, analysis_data, channel_data, config):
    """Generate executive brief."""
    print("\n" + "=" * 60)
    print("PHASE 5: SYNTHESIZE")
    print("=" * 60)

    global_cfg = config.get("global", {})
    model = global_cfg.get("models", {}).get("reasoning", "gpt-4o")

    # Prepare inputs
    intel = classified_data.get("filtered", [])[:20]  # Top 20
    analysis_json = json.dumps({
        k: v for k, v in analysis_data.items()
        if k != "tokens"
    }, indent=2)[:8000]
    channels_json = json.dumps(channel_data, indent=2)[:2000]

    prompt = SYNTHESIS_PROMPT.format(
        analysis=analysis_json,
        intel=json.dumps(intel, indent=2)[:6000],
        channels=channels_json,
    )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  No OPENAI_API_KEY — skipping synthesis")
        return {"error": "No API key"}

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 3000,
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
        with urlopen(req, timeout=120, context=ctx) as resp:
            result = json.loads(resp.read())
            brief = result["choices"][0]["message"]["content"]
            tokens = result.get("usage", {})
            print(f"  Generated brief ({len(brief)} chars, {tokens.get('total_tokens', 0)} tokens)")
            return {"brief": brief, "tokens": tokens}
    except Exception as e:
        print(f"  Synthesis failed: {e}")
        return {"error": str(e)}


# ─── PHASE 6: REPORT ───

def phase_report(run, collect_data, classified_data, analysis_data,
                 memory_data, synthesis_data, out_dir):
    """Save all outputs and generate final report."""
    print("\n" + "=" * 60)
    print("PHASE 6: REPORT")
    print("=" * 60)

    # Save raw data
    with open(out_dir / "articles.json", "w") as f:
        json.dump({
            "articles": [a.to_dict() for a in collect_data["articles"]],
            "errors": collect_data["feed_errors"],
        }, f, indent=2)

    with open(out_dir / "classified.json", "w") as f:
        json.dump(classified_data, f, indent=2)

    if analysis_data:
        with open(out_dir / "analysis.json", "w") as f:
            json.dump(analysis_data, f, indent=2, default=str)

    if collect_data.get("channel_data"):
        with open(out_dir / "channels.json", "w") as f:
            json.dump(collect_data["channel_data"], f, indent=2)

    # Save run metadata
    run.finished_at = datetime.now().isoformat()
    run.status = "completed"
    run.articles_collected = len(collect_data["articles"])
    run.articles_classified = len(classified_data.get("filtered", []))
    run.threats_found = len(analysis_data.get("threats", {}).get("threats", []))
    run.opportunities_found = len(analysis_data.get("opportunities", {}).get("opportunities", []))
    run.trends_identified = len(analysis_data.get("trends", {}).get("trends", []))

    with open(out_dir / "run.json", "w") as f:
        json.dump(run.to_dict(), f, indent=2)

    # Generate markdown report
    report_path = out_dir / "report.md"
    with open(report_path, "w") as f:
        f.write(f"# Competitive Intelligence Report — {date.today().isoformat()}\n\n")
        f.write(f"> Run ID: {run.run_id}\n")
        f.write(f"> Started: {run.started_at}\n")
        f.write(f"> Completed: {run.finished_at}\n")
        f.write(f"> Articles: {run.articles_collected} collected, "
                f"{run.articles_classified} classified\n")
        f.write(f"> Threats: {run.threats_found} | Opportunities: {run.opportunities_found} "
                f"| Trends: {run.trends_identified}\n\n")
        f.write("---\n\n")

        # Executive brief
        brief = synthesis_data.get("brief", "")
        if brief:
            f.write(brief)
            f.write("\n\n---\n\n")

        # Top classified intel
        f.write("## All Classified Intel\n\n")
        f.write("| # | Category | Rel | Imp | Competitor | Title |\n")
        f.write("|---|---|---|---|---|---|\n")
        for i, item in enumerate(classified_data.get("filtered", [])[:30]):
            f.write(f"| {i+1} | {item['category']} | {item['relevance_score']} "
                    f"| {item['impact_score']} | {item['competitor_id']} "
                    f"| {item['title'][:60]} |\n")
        f.write("\n")

        # Channel counts
        channels = collect_data.get("channel_data", {})
        if channels:
            f.write("## Channel Count Snapshot\n\n")
            f.write("| Service | Count | Method | Date |\n")
            f.write("|---|---|---|---|\n")
            for sid, data in channels.items():
                count = (data.get("channel_count")
                        or data.get("channel_count_claimed")
                        or data.get("initial_load_count")
                        or "?")
                method = data.get("method", "")[:40]
                d = data.get("date", "")
                f.write(f"| {sid} | {count} | {method} | {d} |\n")
            f.write("\n")

        # Detailed analysis sections
        threats = analysis_data.get("threats", {}).get("threats", [])
        if threats:
            f.write("## Threat Analysis\n\n")
            for t in threats:
                sev = t.get("severity", 0)
                f.write(f"### [{t.get('threat_type', '').upper()}] "
                        f"{t.get('title', '')} (Severity: {sev}/10)\n\n")
                f.write(f"{t.get('description', '')}\n\n")
                f.write(f"**Defensive action**: {t.get('defensive_action', '')}\n\n")

        opps = analysis_data.get("opportunities", {}).get("opportunities", [])
        if opps:
            f.write("## Opportunity Analysis\n\n")
            for o in opps:
                val = o.get("potential_value", 0)
                feas = o.get("feasibility", 0)
                f.write(f"### {o.get('title', '')} "
                        f"(Value: {val}/10, Feasibility: {feas}/10)\n\n")
                f.write(f"{o.get('description', '')}\n\n")
                actions = o.get("action_items", [])
                if actions:
                    for a in actions:
                        f.write(f"- {a}\n")
                    f.write("\n")

        trends = analysis_data.get("trends", {}).get("trends", [])
        if trends:
            f.write("## Trend Analysis\n\n")
            for t in trends:
                f.write(f"### {t.get('name', '')} "
                        f"({t.get('direction', '')} | Strength: {t.get('strength', 0)}/10)\n\n")
                f.write(f"{t.get('description', '')}\n\n")
                f.write(f"**Tubi implication**: {t.get('tubi_implication', '')}\n\n")

        profiles = analysis_data.get("profiles", {}).get("profiles", [])
        if profiles:
            f.write("## Competitor Profiles\n\n")
            for p in profiles:
                f.write(f"### {p.get('name', p.get('competitor_id', ''))}"
                        f" (Threat: {p.get('threat_level', 0)}/10)\n\n")
                f.write(f"**Strategy**: {p.get('strategy_focus', '')}\n\n")
                moves = p.get("recent_moves", [])
                if moves:
                    f.write("**Recent moves**:\n")
                    for m in moves:
                        f.write(f"- {m}\n")
                    f.write("\n")

    run.report_path = str(report_path)
    print(f"\n  Report saved to {report_path}")
    print(f"  All data saved to {out_dir}/")

    return report_path


# ─── MAIN PIPELINE ───

def run_pipeline(competitor_id=None, lookback=None, skip_memory=False,
                 skip_analysis=False, phase=None):
    """Run the full 6-phase pipeline."""
    config = load_config()
    if lookback:
        config.setdefault("global", {})["lookback_hours"] = lookback

    run = ScanRun()
    run.status = "running"
    out_dir = ensure_output_dir(run.run_id)

    print(f"\n{'#' * 60}")
    print(f"# COMPETITIVE INTELLIGENCE PIPELINE")
    print(f"# Run: {run.run_id}")
    print(f"# Time: {run.started_at}")
    if competitor_id:
        print(f"# Focus: {competitor_id}")
    print(f"# Output: {out_dir}")
    print(f"{'#' * 60}")

    collect_data = {"articles": [], "feed_errors": [], "channel_data": {}}
    classified_data = {"filtered": [], "all_classified": []}
    analysis_data = {}
    memory_data = {}
    synthesis_data = {}

    try:
        # Phase 1
        if not phase or phase == "collect":
            collect_data = phase_collect(config, competitor_id)

        # Phase 2
        if not phase or phase in ("classify", None):
            if collect_data["articles"]:
                classified_data = phase_classify(collect_data["articles"], config)
            else:
                print("\nNo articles collected — skipping classification.")

        # Phase 3
        if not phase or phase in ("analyze", None):
            if not skip_analysis and classified_data.get("filtered"):
                analysis_data = phase_analyze(classified_data["filtered"])
            elif skip_analysis:
                print("\nAnalysis skipped (--skip-analysis)")
            else:
                print("\nNo classified intel — skipping analysis.")

        # Phase 4
        if not phase or phase in ("memory", None):
            memory_data = phase_memory(classified_data, analysis_data, skip=skip_memory)

        # Phase 5
        if not phase or phase in ("synthesize", None):
            if classified_data.get("filtered") or analysis_data:
                synthesis_data = phase_synthesize(
                    classified_data, analysis_data,
                    collect_data.get("channel_data", {}), config
                )

        # Phase 6
        report_path = phase_report(
            run, collect_data, classified_data, analysis_data,
            memory_data, synthesis_data, out_dir
        )

        print(f"\n{'#' * 60}")
        print(f"# PIPELINE COMPLETE")
        print(f"# Articles: {len(collect_data['articles'])} collected")
        print(f"# Classified: {len(classified_data.get('filtered', []))} actionable")
        print(f"# Report: {report_path}")
        print(f"{'#' * 60}\n")

        return out_dir

    except Exception as e:
        run.status = "failed"
        run.finished_at = datetime.now().isoformat()
        print(f"\nPIPELINE FAILED: {e}")
        import traceback
        traceback.print_exc()

        # Save what we have
        with open(out_dir / "run.json", "w") as f:
            json.dump(run.to_dict(), f, indent=2)

        return out_dir


def main():
    parser = argparse.ArgumentParser(
        description="Competitive Intelligence Pipeline Orchestrator"
    )
    parser.add_argument("--competitor", help="Focus on one competitor")
    parser.add_argument("--lookback", type=int, help="Lookback hours (default: 72)")
    parser.add_argument("--skip-memory", action="store_true",
                       help="Skip vector memory phase")
    parser.add_argument("--skip-analysis", action="store_true",
                       help="Skip specialist analysis (collect+classify only)")
    parser.add_argument("--phase",
                       choices=["collect", "classify", "analyze", "memory",
                               "synthesize"],
                       help="Run specific phase only")
    args = parser.parse_args()

    run_pipeline(
        competitor_id=args.competitor,
        lookback=args.lookback,
        skip_memory=args.skip_memory,
        skip_analysis=args.skip_analysis,
        phase=args.phase,
    )


if __name__ == "__main__":
    main()
