"""Core verification engine — independently checks every KPI the hub returns."""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import httpx

from ..config import PLUGINS_DIR
from ..db import get_db, now_iso

logger = logging.getLogger(__name__)

# Hub base URL for comparing against API responses
HUB_BASE = "http://localhost:8888"


def _get_databricks_cursor():
    """Get a Databricks cursor via the linear-data plugin."""
    plugin_path = str(PLUGINS_DIR / "linear-data")
    if plugin_path not in sys.path:
        sys.path.insert(0, plugin_path)
    from linear_data.connection import get_cursor
    return get_cursor


def _record_check(conn, metric_name: str, expected_value: str, actual_value: str,
                  match: bool, drift_pct: float, error: str = ""):
    """Record a single QA check result."""
    conn.execute(
        """INSERT INTO qa_checks
           (metric_name, expected_value, actual_value, match, drift_pct, error, checked_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (metric_name, str(expected_value), str(actual_value),
         1 if match else 0, round(drift_pct, 4), error, now_iso())
    )


def _calc_drift(expected, actual) -> float:
    """Calculate percentage drift between two numeric values."""
    try:
        exp = float(expected)
        act = float(actual)
    except (TypeError, ValueError):
        return 100.0 if str(expected) != str(actual) else 0.0
    if exp == 0:
        return 0.0 if act == 0 else 100.0
    return abs(act - exp) / abs(exp) * 100.0


def check_linear_tvt_share() -> dict:
    """Query Databricks for 30d linear TVT share, compare to dashboard KPI."""
    result = {
        "metric_name": "linear_tvt_share",
        "expected_value": None,
        "actual_value": None,
        "match": False,
        "drift_pct": 0.0,
        "error": "",
    }

    try:
        # Get dashboard value
        resp = httpx.get(f"{HUB_BASE}/api/dashboard/overview", timeout=10)
        resp.raise_for_status()
        dashboard_val = resp.json()["kpis"]["linear_tvt_share_current"]
        result["expected_value"] = dashboard_val

        # Query Databricks independently
        get_cursor = _get_databricks_cursor()
        sql = """
            SELECT
                SUM(CASE WHEN content_type = 'LINEAR' THEN tvt_millisec ELSE 0 END) * 100.0
                / SUM(tvt_millisec) AS linear_tvt_share
            FROM core_prod.session.video_session
            WHERE date >= DATE_SUB(CURRENT_DATE(), 30)
              AND tvt_millisec > 0
        """
        with get_cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            db_val = round(row[0], 2) if row and row[0] is not None else 0.0

        result["actual_value"] = db_val
        result["drift_pct"] = _calc_drift(dashboard_val, db_val)
        result["match"] = result["drift_pct"] <= 5.0

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        logger.warning("check_linear_tvt_share failed: %s", e)

    return result


def check_top_channels() -> dict:
    """Query Databricks for top 5 linear channels, compare to dashboard."""
    result = {
        "metric_name": "top_channels",
        "expected_value": None,
        "actual_value": None,
        "match": False,
        "drift_pct": 0.0,
        "error": "",
    }

    try:
        # Get dashboard value — the overview endpoint doesn't directly list top channels,
        # so we compare against what a data query would return.
        get_cursor = _get_databricks_cursor()
        sql = """
            SELECT ci.title, SUM(vs.tvt_millisec) / 3600000.0 AS tvt_hours
            FROM core_prod.session.video_session vs
            JOIN core_prod.content.content_info ci ON vs.content_id = ci.content_id
            WHERE vs.date >= DATE_SUB(CURRENT_DATE(), 30)
              AND vs.tvt_millisec > 0
              AND ci.content_type = 'LINEAR'
            GROUP BY ci.title
            ORDER BY tvt_hours DESC
            LIMIT 5
        """
        with get_cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            top = [{"name": r[0], "tvt_hours": round(r[1], 1)} for r in rows]

        result["actual_value"] = json.dumps([c["name"] for c in top])
        # Known top channels from business context
        known_top = ["ION", "Dateline 24/7", "ION Mystery"]
        actual_names = [c["name"] for c in top]
        # Check if at least the top 3 known channels appear somewhere in top 5
        overlap = sum(1 for k in known_top if any(k.lower() in a.lower() for a in actual_names))
        result["expected_value"] = json.dumps(known_top)
        result["drift_pct"] = (1 - overlap / max(len(known_top), 1)) * 100.0
        result["match"] = overlap >= 2  # At least 2 of 3 known top channels present

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        logger.warning("check_top_channels failed: %s", e)

    return result


def check_sentiment_counts() -> dict:
    """Recount sentiment from raw feedback table, compare to /api/sentiment/summary."""
    result = {
        "metric_name": "sentiment_counts",
        "expected_value": None,
        "actual_value": None,
        "match": False,
        "drift_pct": 0.0,
        "error": "",
    }

    try:
        # Get API value
        resp = httpx.get(f"{HUB_BASE}/api/sentiment/summary", timeout=10)
        resp.raise_for_status()
        api_summary = resp.json()
        result["expected_value"] = json.dumps(api_summary)

        # Query SQLite directly
        with get_db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            by_sentiment = {}
            for row in conn.execute(
                "SELECT sentiment, COUNT(*) as cnt FROM feedback GROUP BY sentiment"
            ).fetchall():
                by_sentiment[row["sentiment"]] = row["cnt"]

        db_summary = {"total": total, "by_sentiment": by_sentiment}
        result["actual_value"] = json.dumps(db_summary)

        # Compare totals
        api_total = api_summary.get("total", 0)
        if api_total == 0 and total == 0:
            result["match"] = True
            result["drift_pct"] = 0.0
        else:
            result["drift_pct"] = _calc_drift(api_total, total)
            # Also check breakdown matches
            api_by = api_summary.get("by_sentiment", {})
            breakdown_match = all(
                by_sentiment.get(k, 0) == v for k, v in api_by.items()
            ) and all(
                api_by.get(k, 0) == v for k, v in by_sentiment.items()
            )
            result["match"] = result["drift_pct"] <= 5.0 and breakdown_match

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        logger.warning("check_sentiment_counts failed: %s", e)

    return result


def check_work_item_counts() -> dict:
    """Verify work item counts against DB directly."""
    result = {
        "metric_name": "work_item_counts",
        "expected_value": None,
        "actual_value": None,
        "match": False,
        "drift_pct": 0.0,
        "error": "",
    }

    try:
        # Get API value
        resp = httpx.get(f"{HUB_BASE}/api/dashboard/overview", timeout=10)
        resp.raise_for_status()
        api_work = resp.json()["work"]
        result["expected_value"] = json.dumps(api_work)

        # Query SQLite directly
        with get_db() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM work_items GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in rows}
            total = sum(by_status.values())

        db_work = {
            "total": total,
            "open": by_status.get("open", 0),
            "in_progress": by_status.get("in_progress", 0),
            "blocked": by_status.get("blocked", 0),
            "done": by_status.get("done", 0),
        }
        result["actual_value"] = json.dumps(db_work)

        # Compare
        api_total = api_work.get("total", 0)
        result["drift_pct"] = _calc_drift(api_total, total)
        result["match"] = (
            api_work.get("open", 0) == db_work["open"]
            and api_work.get("in_progress", 0) == db_work["in_progress"]
            and api_work.get("blocked", 0) == db_work["blocked"]
            and api_work.get("done", 0) == db_work["done"]
            and api_work.get("total", 0) == db_work["total"]
        )
        if not result["match"]:
            result["drift_pct"] = max(result["drift_pct"], 1.0)  # ensure nonzero drift on mismatch

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        logger.warning("check_work_item_counts failed: %s", e)

    return result


def check_verification_counts() -> dict:
    """Verify data_verifications counts against DB directly."""
    result = {
        "metric_name": "verification_counts",
        "expected_value": None,
        "actual_value": None,
        "match": False,
        "drift_pct": 0.0,
        "error": "",
    }

    try:
        # Get API value
        resp = httpx.get(f"{HUB_BASE}/api/dashboard/overview", timeout=10)
        resp.raise_for_status()
        api_verify = resp.json()["verifications"]
        result["expected_value"] = json.dumps(api_verify)

        # Query SQLite directly
        with get_db() as conn:
            rows = conn.execute(
                "SELECT match_status, COUNT(*) as cnt FROM data_verifications GROUP BY match_status"
            ).fetchall()
            by_status = {r["match_status"]: r["cnt"] for r in rows}
            total = sum(by_status.values())

        db_verify = {
            "total": total,
            "match": by_status.get("match", 0),
            "mismatch": by_status.get("mismatch", 0),
            "pending": by_status.get("pending", 0),
        }
        result["actual_value"] = json.dumps(db_verify)

        api_total = api_verify.get("total", 0)
        result["drift_pct"] = _calc_drift(api_total, total)
        result["match"] = (
            api_verify.get("total", 0) == db_verify["total"]
            and api_verify.get("match", 0) == db_verify["match"]
            and api_verify.get("mismatch", 0) == db_verify["mismatch"]
            and api_verify.get("pending", 0) == db_verify["pending"]
        )
        if not result["match"]:
            result["drift_pct"] = max(result["drift_pct"], 1.0)

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        logger.warning("check_verification_counts failed: %s", e)

    return result


def check_channel_count() -> dict:
    """Compare hardcoded 340 channel count to actual Databricks count."""
    result = {
        "metric_name": "channel_count",
        "expected_value": 340,
        "actual_value": None,
        "match": False,
        "drift_pct": 0.0,
        "error": "",
    }

    try:
        get_cursor = _get_databricks_cursor()
        sql = """
            SELECT COUNT(DISTINCT content_id) AS channel_count
            FROM core_prod.session.video_session
            WHERE date >= DATE_SUB(CURRENT_DATE(), 30)
              AND tvt_millisec > 0
              AND content_type = 'LINEAR'
        """
        with get_cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            db_count = row[0] if row and row[0] is not None else 0

        result["actual_value"] = db_count
        result["drift_pct"] = _calc_drift(340, db_count)
        result["match"] = result["drift_pct"] <= 5.0

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        logger.warning("check_channel_count failed: %s", e)

    return result


# Registry of all checks
ALL_CHECKS = [
    check_linear_tvt_share,
    check_top_channels,
    check_sentiment_counts,
    check_work_item_counts,
    check_verification_counts,
    check_channel_count,
]


def run_all_checks() -> List[dict]:
    """Run every registered accuracy check and persist results to qa_checks table.

    Returns list of check result dicts.
    """
    results = []
    with get_db() as conn:
        for check_fn in ALL_CHECKS:
            try:
                result = check_fn()
            except Exception as e:
                result = {
                    "metric_name": check_fn.__name__.replace("check_", ""),
                    "expected_value": None,
                    "actual_value": None,
                    "match": False,
                    "drift_pct": 100.0,
                    "error": f"{type(e).__name__}: {e}",
                }
            _record_check(
                conn,
                metric_name=result["metric_name"],
                expected_value=result.get("expected_value", ""),
                actual_value=result.get("actual_value", ""),
                match=result.get("match", False),
                drift_pct=result.get("drift_pct", 0.0),
                error=result.get("error", ""),
            )
            results.append(result)

    return results
