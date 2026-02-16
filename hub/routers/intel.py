"""Intel monitor: competitive intelligence pipeline results."""

import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Query

from ..config import SCANS_DIR, SCANNER_DIR

router = APIRouter(prefix="/api/intel", tags=["intel"])


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
    return _load_run_data(scan_date, run_id)


@router.get("/latest")
def get_latest():
    """Get the latest scan run data."""
    if not SCANS_DIR.exists():
        return {"error": "No scan data found"}
    for date_dir in sorted(SCANS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for run_dir in sorted(date_dir.iterdir(), reverse=True):
            if run_dir.is_dir() and (run_dir / "run.json").exists():
                return _load_run_data(date_dir.name, run_dir.name)
    return {"error": "No scan data found"}


@router.get("/threats")
def get_threats():
    """Get all threats from latest analysis."""
    data = get_latest()
    analysis = data.get("analysis", {})
    return analysis.get("threats", [])


@router.get("/opportunities")
def get_opportunities():
    """Get all opportunities from latest analysis."""
    data = get_latest()
    analysis = data.get("analysis", {})
    return analysis.get("opportunities", [])


@router.get("/trends")
def get_trends():
    """Get all trends from latest analysis."""
    data = get_latest()
    analysis = data.get("analysis", {})
    return analysis.get("trends", [])


@router.get("/competitors")
def get_competitors():
    """Get competitor profiles from latest analysis."""
    data = get_latest()
    analysis = data.get("analysis", {})
    return analysis.get("profiles", [])


def _run_scan(args: list):
    """Run the scanner pipeline (background task)."""
    subprocess.run(
        [sys.executable, str(SCANNER_DIR / "orchestrator.py")] + args,
        cwd=str(SCANNER_DIR.parent.parent),
        capture_output=True,
    )


@router.post("/scan")
def trigger_scan(background_tasks: BackgroundTasks,
                 skip_memory: bool = False,
                 skip_analysis: bool = False,
                 competitor: str = None):
    """Trigger a new competitive intelligence scan."""
    args = []
    if skip_memory:
        args.append("--skip-memory")
    if skip_analysis:
        args.append("--skip-analysis")
    if competitor:
        args.extend(["--competitor", competitor])
    background_tasks.add_task(_run_scan, args)
    return {"status": "scan_started", "args": args}
