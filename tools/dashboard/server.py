#!/usr/bin/env python3
"""
Competitive Intelligence Dashboard Server.
Serves the latest pipeline scan data as an interactive web dashboard.

Usage:
    python3 tools/dashboard/server.py                  # Start on port 8080
    python3 tools/dashboard/server.py --port 3000      # Custom port
    python3 tools/dashboard/server.py --run-id 20260215_150544  # Specific run
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[2]
SCANS_DIR = ROOT / "intel" / "scans"
DASHBOARD_DIR = Path(__file__).parent


def find_latest_run():
    """Find the most recent scan run with the richest data (prefers runs with analysis)."""
    if not SCANS_DIR.exists():
        return None, None

    # Collect all runs
    all_runs = []
    for date_dir in sorted(SCANS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for run_dir in sorted(date_dir.iterdir(), reverse=True):
            if not run_dir.is_dir() or not (run_dir / "run.json").exists():
                continue
            has_analysis = (run_dir / "analysis.json").exists()
            all_runs.append((date_dir.name, run_dir.name, has_analysis))

    if not all_runs:
        return None, None

    # Prefer runs with analysis, then most recent
    runs_with_analysis = [r for r in all_runs if r[2]]
    if runs_with_analysis:
        return runs_with_analysis[0][0], runs_with_analysis[0][1]

    return all_runs[0][0], all_runs[0][1]


def load_run_data(scan_date=None, run_id=None):
    """Load all data from a scan run."""
    if not scan_date or not run_id:
        scan_date, run_id = find_latest_run()

    if not scan_date or not run_id:
        return {"error": "No scan data found. Run the pipeline first."}

    run_dir = SCANS_DIR / scan_date / run_id
    data = {"scan_date": scan_date, "run_id": run_id}

    # Load each data file
    for name in ["run", "classified", "analysis", "channels", "articles"]:
        path = run_dir / f"{name}.json"
        if path.exists():
            with open(path) as f:
                data[name] = json.load(f)

    # Normalize classified data — pipeline stores as "filtered", dashboard expects "intel"
    if "classified" in data and "intel" not in data["classified"]:
        data["classified"]["intel"] = data["classified"].get("filtered", [])

    # Load report markdown
    report_path = run_dir / "report.md"
    if report_path.exists():
        with open(report_path) as f:
            data["report_md"] = f.read()

    # Load browser scrape data if available
    deep_dir = SCANS_DIR / scan_date / "deep"
    if deep_dir.exists():
        browser_data = {}
        for f in deep_dir.glob("*_browser*.json"):
            with open(f) as fh:
                browser_data[f.stem] = json.load(fh)
        if browser_data:
            data["browser_scrapes"] = browser_data

    # Memory stats
    chroma_dir = ROOT / "data" / "chroma"
    if chroma_dir.exists():
        data["memory_available"] = True

    return data


class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom handler for the dashboard."""

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_path = DASHBOARD_DIR / "index.html"
            with open(html_path, "rb") as f:
                self.wfile.write(f.read())

        elif parsed.path == "/api/data":
            params = parse_qs(parsed.query)
            scan_date = params.get("date", [None])[0]
            run_id = params.get("run_id", [None])[0]
            data = load_run_data(scan_date, run_id)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, default=str).encode())

        elif parsed.path == "/api/runs":
            runs = []
            if SCANS_DIR.exists():
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
                            runs.append({
                                "date": date_dir.name,
                                "run_id": run_dir.name,
                                **run_data,
                            })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(runs).encode())

        elif parsed.path == "/api/memory/search":
            params = parse_qs(parsed.query)
            query = params.get("q", [""])[0]
            if query:
                try:
                    sys.path.insert(0, str(ROOT / "tools" / "scanner"))
                    from memory import VectorMemory
                    mem = VectorMemory()
                    results = mem.search(query, n_results=10)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(results, default=str).encode())
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
            else:
                self.send_response(400)
                self.end_headers()

        elif parsed.path == "/api/memory/stats":
            try:
                sys.path.insert(0, str(ROOT / "tools" / "scanner"))
                from memory import VectorMemory
                mem = VectorMemory()
                stats = mem.stats()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(stats).encode())
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        else:
            # Serve static files from dashboard dir
            self.directory = str(DASHBOARD_DIR)
            super().do_GET()

    def log_message(self, format, *args):
        # Quieter logging
        if "/api/" not in str(args[0]):
            return
        super().log_message(format, *args)


def main():
    parser = argparse.ArgumentParser(description="CI Dashboard Server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--run-id", help="Specific run ID to display")
    args = parser.parse_args()

    # Verify we have data
    scan_date, run_id = find_latest_run()
    if scan_date:
        print(f"Latest scan: {scan_date}/{run_id}")
    else:
        print("WARNING: No scan data found. Run the pipeline first:")
        print("  python3 tools/scanner/orchestrator.py")

    server = HTTPServer(("localhost", args.port), DashboardHandler)
    print(f"\nDashboard running at http://localhost:{args.port}")
    print("Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
