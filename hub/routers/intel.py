"""Intel monitor: competitive intelligence pipeline results."""

import json
import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks

from ..config import SCANS_DIR, SCANNER_DIR
from .. import db

router = APIRouter(prefix="/api/intel", tags=["intel"])
logger = logging.getLogger(__name__)


def _load_run_data(scan_date: str, run_id: str) -> dict:
    """Load all data from a scan run."""
    run_dir = SCANS_DIR / scan_date / run_id
    data = {"scan_date": scan_date, "run_id": run_id}
    for name in ["run", "classified", "analysis", "channels", "articles"]:
        path = run_dir / f"{name}.json"
        if path.exists():
            with open(path) as f:
                data[name] = json.load(f)
    if "classified" in data and "intel" not in data.get("classified", {}):
        data["classified"]["intel"] = data["classified"].get("filtered", [])
    # Normalize articles — may be {articles: [...]} or [...]
    if "articles" in data and isinstance(data["articles"], dict):
        data["articles"] = data["articles"].get("articles", [])
    report_path = run_dir / "report.md"
    if report_path.exists():
        data["report_md"] = report_path.read_text()
    return data


@router.get("/runs")
def list_runs():
    """List all scan runs."""
    runs = []
    if not SCANS_DIR.exists():
        return runs
    for date_dir in sorted(SCANS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for run_dir in sorted(date_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            run_file = run_dir / "run.json"
            if run_file.exists():
                with open(run_file) as f:
                    run_data = json.load(f)
                runs.append({"date": date_dir.name, "run_id": run_dir.name, **run_data})
    return runs


@router.get("/run/{scan_date}/{run_id}")
def get_run(scan_date: str, run_id: str):
    """Get full data for a specific run."""
    run_dir = SCANS_DIR / scan_date / run_id
    if not run_dir.is_dir():
        return {"error": f"Run not found: {scan_date}/{run_id}"}
    return _load_run_data(scan_date, run_id)


def _find_best_run() -> "dict | None":
    """Find the best run by merging data across recent runs.

    The latest run may not have all data (e.g. classified intel or analysis).
    This finds the most recent run with analysis data and merges classified
    data from the best available source.
    """
    if not SCANS_DIR.exists():
        return None

    all_runs = []
    for date_dir in sorted(SCANS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for run_dir in sorted(date_dir.iterdir(), reverse=True):
            if run_dir.is_dir() and (run_dir / "run.json").exists():
                all_runs.append((date_dir.name, run_dir.name))
    if not all_runs:
        return None

    # Find the best run with analysis
    best_analysis_run = None
    best_classified_run = None
    best_articles_run = None

    for scan_date, run_id in all_runs:
        run_dir = SCANS_DIR / scan_date / run_id
        if not best_analysis_run and (run_dir / "analysis.json").exists():
            best_analysis_run = (scan_date, run_id)
        if not best_classified_run:
            cp = run_dir / "classified.json"
            if cp.exists():
                with open(cp) as f:
                    cd = json.load(f)
                if cd.get("filtered") or cd.get("all_classified"):
                    best_classified_run = (scan_date, run_id)
        if not best_articles_run:
            ap = run_dir / "articles.json"
            if ap.exists():
                best_articles_run = (scan_date, run_id)
        if best_analysis_run and best_classified_run and best_articles_run:
            break

    # Use the most recent run as base, then enrich
    base_date, base_id = all_runs[0]
    data = _load_run_data(base_date, base_id)

    # Merge analysis from best source if base doesn't have it
    if "analysis" not in data and best_analysis_run:
        ad = SCANS_DIR / best_analysis_run[0] / best_analysis_run[1] / "analysis.json"
        with open(ad) as f:
            data["analysis"] = json.load(f)
        data["analysis_source_run"] = best_analysis_run[1]

    # Merge classified from best source if base doesn't have it
    classified = data.get("classified", {})
    if not classified.get("filtered") and not classified.get("intel") and best_classified_run:
        cp = SCANS_DIR / best_classified_run[0] / best_classified_run[1] / "classified.json"
        with open(cp) as f:
            data["classified"] = json.load(f)
        data["classified"]["intel"] = data["classified"].get("filtered", [])
        data["classified_source_run"] = best_classified_run[1]

    return data


@router.get("/latest")
def get_latest():
    """Get the latest scan run data, merging from best available sources."""
    data = _find_best_run()
    if not data:
        return {"error": "No scan data found"}
    return data


@router.get("/threats")
def get_threats():
    """Get all threats from latest analysis."""
    data = get_latest()
    analysis = data.get("analysis", {})
    threats_data = analysis.get("threats", {})
    if isinstance(threats_data, dict):
        return threats_data.get("threats", [])
    return threats_data


@router.get("/opportunities")
def get_opportunities():
    """Get all opportunities from latest analysis."""
    data = get_latest()
    analysis = data.get("analysis", {})
    opps_data = analysis.get("opportunities", {})
    if isinstance(opps_data, dict):
        return opps_data.get("opportunities", [])
    return opps_data


@router.get("/trends")
def get_trends():
    """Get all trends from latest analysis."""
    data = get_latest()
    analysis = data.get("analysis", {})
    trends_data = analysis.get("trends", {})
    if isinstance(trends_data, dict):
        return trends_data.get("trends", [])
    return trends_data


@router.get("/competitors")
def get_competitors():
    """Get competitor profiles from latest analysis."""
    data = get_latest()
    analysis = data.get("analysis", {})
    profiles_data = analysis.get("profiles", {})
    if isinstance(profiles_data, dict):
        return profiles_data.get("profiles", [])
    return profiles_data


def _get_sorted_runs() -> list[dict]:
    """Return all scan runs sorted newest-first, each with date and run_id."""
    runs = []
    if not SCANS_DIR.exists():
        return runs
    for date_dir in sorted(SCANS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for run_dir in sorted(date_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            run_file = run_dir / "run.json"
            if run_file.exists():
                with open(run_file) as f:
                    run_data = json.load(f)
                runs.append({"date": date_dir.name, "run_id": run_dir.name, **run_data})
    return runs


def _ingest_scan_results(scan_date: str, run_id: str) -> dict:
    """Parse scan output and push threats/opportunities as work items.

    Returns summary of what was ingested.
    """
    run_dir = SCANS_DIR / scan_date / run_id
    ingested = {"threats": 0, "opportunities": 0, "work_item_ids": []}

    # Load analysis.json for threats and opportunities
    analysis_path = run_dir / "analysis.json"
    if not analysis_path.exists():
        return ingested

    with open(analysis_path) as f:
        analysis = json.load(f)

    # Ingest threats as work items
    threats_data = analysis.get("threats", {})
    threats_list = threats_data.get("threats", []) if isinstance(threats_data, dict) else []
    for threat in threats_list:
        title = threat.get("title") or threat.get("description", "")[:80]
        description = threat.get("description", "")
        if threat.get("defensive_action"):
            description += f"\n\nDefensive action: {threat['defensive_action']}"
        metadata = {
            "source": "ci_scan",
            "scan_date": scan_date,
            "run_id": run_id,
            "threat_type": threat.get("threat_type", ""),
            "severity": threat.get("severity", 0),
            "timeframe": threat.get("timeframe", ""),
            "source_competitor": threat.get("source_competitor", ""),
        }
        wid = db.create_work_item(
            type="threat",
            title=title,
            description=description,
            priority="high",
            tags=["ci_scan", "threat", scan_date],
            metadata=metadata,
        )
        ingested["threats"] += 1
        ingested["work_item_ids"].append(wid)

    # Ingest opportunities as work items
    opps_data = analysis.get("opportunities", {})
    opps_list = opps_data.get("opportunities", []) if isinstance(opps_data, dict) else []
    for opp in opps_list:
        title = opp.get("title") or opp.get("description", "")[:80]
        description = opp.get("description", "")
        if opp.get("action_items"):
            description += "\n\nAction items:\n" + "\n".join(
                f"- {a}" for a in opp["action_items"]
            )
        potential = opp.get("potential_value", 0)
        feasibility = opp.get("feasibility", 0)
        # High priority if value*feasibility score is above 40
        priority = "high" if (potential * feasibility) > 40 else "medium"
        metadata = {
            "source": "ci_scan",
            "scan_date": scan_date,
            "run_id": run_id,
            "opportunity_type": opp.get("opportunity_type", ""),
            "potential_value": potential,
            "feasibility": feasibility,
            "competitor_gap": opp.get("competitor_gap", ""),
        }
        wid = db.create_work_item(
            type="opportunity",
            title=title,
            description=description,
            priority=priority,
            tags=["ci_scan", "opportunity", scan_date],
            metadata=metadata,
        )
        ingested["opportunities"] += 1
        ingested["work_item_ids"].append(wid)

    return ingested


def _run_scan(args: list):
    """Run the scanner pipeline (background task), then ingest results."""
    subprocess.run(
        [sys.executable, str(SCANNER_DIR / "orchestrator.py")] + args,
        cwd=str(SCANNER_DIR.parent.parent),
        capture_output=True,
    )
    # After scan completes, find the newest run and ingest
    runs = _get_sorted_runs()
    if runs:
        latest = runs[0]
        try:
            _ingest_scan_results(latest["date"], latest["run_id"])
        except Exception:
            logger.exception("Failed to ingest scan results")


@router.post("/scan")
def trigger_scan(background_tasks: BackgroundTasks,
                 skip_memory: bool = False,
                 skip_analysis: bool = False,
                 competitor: str = None):
    """Trigger a new competitive intelligence scan.

    After the scan completes, threats and opportunities are auto-ingested
    as work items in the hub database.
    """
    args = []
    if skip_memory:
        args.append("--skip-memory")
    if skip_analysis:
        args.append("--skip-analysis")
    if competitor:
        args.extend(["--competitor", competitor])
    background_tasks.add_task(_run_scan, args)
    return {"status": "scan_started", "args": args}


@router.post("/ingest/{scan_date}/{run_id}")
def ingest_run(scan_date: str, run_id: str):
    """Manually ingest a scan run's threats/opportunities into the work queue."""
    run_dir = SCANS_DIR / scan_date / run_id
    if not run_dir.exists():
        return {"error": f"Run not found: {scan_date}/{run_id}"}
    result = _ingest_scan_results(scan_date, run_id)
    return {"status": "ingested", **result}


@router.post("/ensure-work-items")
def ensure_work_items():
    """Ensure latest threats/opportunities exist as work items.

    Checks if work items already exist for the latest scan's threats and
    opportunities. Creates any that are missing. Idempotent.
    """
    data = _find_best_run()
    if not data or "analysis" not in data:
        return {"status": "no_analysis", "created": 0}

    analysis = data["analysis"]
    created = 0

    # Get existing work item titles to avoid duplicates
    existing = db.get_work_items(limit=500)
    existing_titles = {w["title"] for w in existing}

    # Threats
    threats_data = analysis.get("threats", {})
    threats = threats_data.get("threats", []) if isinstance(threats_data, dict) else []
    for threat in threats:
        title = threat.get("title") or threat.get("description", "")[:80]
        if title in existing_titles:
            continue
        description = threat.get("description", "")
        if threat.get("defensive_action"):
            description += f"\n\nDefensive action: {threat['defensive_action']}"
        metadata = {
            "source": "ci_scan",
            "scan_date": data.get("scan_date", ""),
            "threat_type": threat.get("threat_type", ""),
            "severity": threat.get("severity", 0),
            "timeframe": threat.get("timeframe", ""),
            "source_competitor": threat.get("source_competitor", ""),
        }
        db.create_work_item(
            type="threat",
            title=title,
            description=description,
            priority="high",
            tags=["ci_scan", "threat"],
            metadata=metadata,
        )
        existing_titles.add(title)
        created += 1

    # Opportunities
    opps_data = analysis.get("opportunities", {})
    opps = opps_data.get("opportunities", []) if isinstance(opps_data, dict) else []
    for opp in opps:
        title = opp.get("title") or opp.get("description", "")[:80]
        if title in existing_titles:
            continue
        description = opp.get("description", "")
        if opp.get("action_items"):
            description += "\n\nAction items:\n" + "\n".join(f"- {a}" for a in opp["action_items"])
        potential = opp.get("potential_value", 0)
        feasibility = opp.get("feasibility", 0)
        priority = "high" if (potential * feasibility) > 40 else "medium"
        metadata = {
            "source": "ci_scan",
            "scan_date": data.get("scan_date", ""),
            "opportunity_type": opp.get("opportunity_type", ""),
            "potential_value": potential,
            "feasibility": feasibility,
            "competitor_gap": opp.get("competitor_gap", ""),
        }
        db.create_work_item(
            type="opportunity",
            title=title,
            description=description,
            priority=priority,
            tags=["ci_scan", "opportunity"],
            metadata=metadata,
        )
        existing_titles.add(title)
        created += 1

    return {"status": "ok", "created": created, "threats": len(threats), "opportunities": len(opps)}


@router.get("/history")
def scan_history():
    """List all past scan runs with article count, threat count, and date.

    Reads actual file contents to get accurate counts since run.json
    metadata may not always be updated.
    """
    history = []
    for run in _get_sorted_runs():
        run_dir = SCANS_DIR / run["date"] / run["run_id"]

        # Get counts from actual files when run.json shows 0
        article_count = run.get("articles_collected", 0)
        classified_count = run.get("articles_classified", 0)
        threat_count = run.get("threats_found", 0)
        opp_count = run.get("opportunities_found", 0)
        trend_count = run.get("trends_identified", 0)

        # Read articles file for accurate count
        if article_count == 0:
            articles_path = run_dir / "articles.json"
            if articles_path.exists():
                try:
                    with open(articles_path) as f:
                        articles = json.load(f)
                    if isinstance(articles, list):
                        article_count = len(articles)
                    elif isinstance(articles, dict):
                        article_count = len(articles.get("articles", []))
                except Exception:
                    pass

        # Read classified file for count
        if classified_count == 0:
            classified_path = run_dir / "classified.json"
            if classified_path.exists():
                try:
                    with open(classified_path) as f:
                        classified = json.load(f)
                    classified_count = len(classified.get("filtered", [])) or len(classified.get("all_classified", []))
                except Exception:
                    pass

        # Read analysis for threat/opp/trend counts
        if threat_count == 0 or opp_count == 0 or trend_count == 0:
            analysis_path = run_dir / "analysis.json"
            if analysis_path.exists():
                try:
                    with open(analysis_path) as f:
                        analysis = json.load(f)
                    threats_data = analysis.get("threats", {})
                    if isinstance(threats_data, dict):
                        threat_count = len(threats_data.get("threats", []))
                    opps_data = analysis.get("opportunities", {})
                    if isinstance(opps_data, dict):
                        opp_count = len(opps_data.get("opportunities", []))
                    trends_data = analysis.get("trends", {})
                    if isinstance(trends_data, dict):
                        trend_count = len(trends_data.get("trends", []))
                except Exception:
                    pass

        has_analysis = (run_dir / "analysis.json").exists()
        has_classified = classified_count > 0

        entry = {
            "date": run["date"],
            "run_id": run["run_id"],
            "started_at": run.get("started_at", ""),
            "finished_at": run.get("finished_at", ""),
            "status": run.get("status", "unknown"),
            "article_count": article_count,
            "classified_count": classified_count,
            "threat_count": threat_count,
            "opportunity_count": opp_count,
            "trend_count": trend_count,
            "has_analysis": has_analysis,
            "has_classified": has_classified,
        }
        history.append(entry)
    return history


@router.get("/diff")
def scan_diff():
    """Compare the latest two scans and return new/changed items.

    Compares classified intel titles and analysis items between the two
    most recent runs.
    """
    runs = _get_sorted_runs()
    if len(runs) < 2:
        return {"error": "Need at least 2 scan runs to diff", "runs_available": len(runs)}

    latest = _load_run_data(runs[0]["date"], runs[0]["run_id"])
    previous = _load_run_data(runs[1]["date"], runs[1]["run_id"])

    def _extract_titles(data: dict, path: str) -> set:
        """Extract a set of titles/names from nested scan data."""
        parts = path.split(".")
        obj = data
        for p in parts:
            if isinstance(obj, dict):
                obj = obj.get(p, {})
            else:
                return set()
        if isinstance(obj, list):
            return {item.get("title") or item.get("name", "") for item in obj if isinstance(item, dict)}
        return set()

    # Compare classified intel
    latest_classified = _extract_titles(latest, "classified.filtered")
    if not latest_classified:
        latest_classified = _extract_titles(latest, "classified.intel")
    prev_classified = _extract_titles(previous, "classified.filtered")
    if not prev_classified:
        prev_classified = _extract_titles(previous, "classified.intel")

    # Compare threats
    latest_threats = _extract_titles(latest, "analysis.threats.threats")
    prev_threats = _extract_titles(previous, "analysis.threats.threats")

    # Compare opportunities
    latest_opps = _extract_titles(latest, "analysis.opportunities.opportunities")
    prev_opps = _extract_titles(previous, "analysis.opportunities.opportunities")

    # Compare trends
    latest_trends = _extract_titles(latest, "analysis.trends.trends")
    prev_trends = _extract_titles(previous, "analysis.trends.trends")

    return {
        "latest": {"date": runs[0]["date"], "run_id": runs[0]["run_id"]},
        "previous": {"date": runs[1]["date"], "run_id": runs[1]["run_id"]},
        "new_intel": sorted(latest_classified - prev_classified),
        "removed_intel": sorted(prev_classified - latest_classified),
        "new_threats": sorted(latest_threats - prev_threats),
        "removed_threats": sorted(prev_threats - latest_threats),
        "new_opportunities": sorted(latest_opps - prev_opps),
        "removed_opportunities": sorted(prev_opps - latest_opps),
        "new_trends": sorted(latest_trends - prev_trends),
        "removed_trends": sorted(prev_trends - latest_trends),
        "summary": {
            "new_intel_count": len(latest_classified - prev_classified),
            "removed_intel_count": len(prev_classified - latest_classified),
            "new_threats_count": len(latest_threats - prev_threats),
            "new_opportunities_count": len(latest_opps - prev_opps),
            "new_trends_count": len(latest_trends - prev_trends),
        },
    }
