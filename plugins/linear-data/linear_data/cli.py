"""CLI for querying Databricks and running canonical linear analyses."""

import argparse
import json
import sys
import time

from tabulate import tabulate


def run_query(sql: str, format: str = "table", limit: int = 100) -> str:
    """Execute SQL against Databricks, return formatted results."""
    from .connection import get_cursor

    start = time.time()
    with get_cursor() as cursor:
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchmany(limit)
    elapsed = time.time() - start

    if format == "json":
        data = [dict(zip(columns, row)) for row in rows]
        output = json.dumps(data, indent=2, default=str)
    elif format == "csv":
        lines = [",".join(columns)]
        for row in rows:
            lines.append(",".join(str(v) for v in row))
        output = "\n".join(lines)
    else:  # table
        output = tabulate(rows, headers=columns, tablefmt="github", floatfmt=".2f")

    row_count = len(rows)
    footer = f"\n\n--- {row_count} rows | {elapsed:.1f}s ---"
    return output + footer


def run_named_query(name: str, **kwargs) -> str:
    """Run a named canonical query."""
    queries = get_canonical_queries()
    if name not in queries:
        available = "\n".join(f"  - {k}: {v['description']}" for k, v in queries.items())
        return f"Unknown query: {name}\n\nAvailable queries:\n{available}"

    q = queries[name]
    sql = q["sql"].format(**kwargs)
    return run_query(sql, format=kwargs.get("format", "table"))


def get_canonical_queries() -> dict:
    """Return all canonical query definitions."""
    return {
        "linear_tvt_by_platform": {
            "description": "Linear TVT breakdown by platform (last N days)",
            "sql": """
SELECT
    platform,
    COUNT(DISTINCT device_id) AS unique_viewers,
    COUNT(*) AS sessions,
    SUM(tvt_millisec) / 3600000.0 AS total_hours,
    AVG(tvt_millisec) / 60000.0 AS avg_session_min
FROM core_prod.session.video_session
WHERE content_type = 'LINEAR'
  AND country = 'US'
  AND date >= CURRENT_DATE - INTERVAL {days} DAYS
  AND tvt_millisec > 0
GROUP BY platform
ORDER BY total_hours DESC
""",
        },
        "linear_tvt_share": {
            "description": "Linear TVT as % of total TVT (last N days)",
            "sql": """
SELECT
    SUM(CASE WHEN content_type = 'LINEAR' THEN tvt_millisec ELSE 0 END) / 3600000.0 AS linear_hours,
    SUM(tvt_millisec) / 3600000.0 AS total_hours,
    ROUND(
        SUM(CASE WHEN content_type = 'LINEAR' THEN tvt_millisec ELSE 0 END) * 100.0
        / SUM(tvt_millisec), 2
    ) AS linear_share_pct
FROM core_prod.session.video_session
WHERE country = 'US'
  AND date >= CURRENT_DATE - INTERVAL {days} DAYS
  AND tvt_millisec > 0
""",
        },
        "linear_entry_points": {
            "description": "How users discover linear content (entry path attribution)",
            "sql": """
SELECT
    page_source,
    container_slug,
    COUNT(*) AS sessions,
    COUNT(DISTINCT device_id) AS unique_users,
    SUM(tvt_millisec) / 3600000.0 AS total_hours,
    AVG(tvt_millisec) / 60000.0 AS avg_watch_min
FROM core_prod.session.video_session
WHERE content_type = 'LINEAR'
  AND country = 'US'
  AND date >= CURRENT_DATE - INTERVAL {days} DAYS
  AND tvt_millisec > 0
GROUP BY page_source, container_slug
ORDER BY total_hours DESC
""",
        },
        "top_linear_channels": {
            "description": "Top linear channels by TVT",
            "sql": """
SELECT
    ci.content_name AS channel_name,
    COUNT(DISTINCT vs.device_id) AS unique_viewers,
    COUNT(*) AS sessions,
    SUM(vs.tvt_millisec) / 3600000.0 AS total_hours,
    AVG(vs.tvt_millisec) / 60000.0 AS avg_session_min
FROM core_prod.session.video_session vs
JOIN core_prod.tubidw.content_info ci ON vs.content_id = ci.content_id
WHERE vs.content_type = 'LINEAR'
  AND vs.country = 'US'
  AND vs.date >= CURRENT_DATE - INTERVAL {days} DAYS
  AND vs.tvt_millisec > 0
GROUP BY ci.content_name
ORDER BY total_hours DESC
LIMIT {limit}
""",
        },
        "linear_user_segments": {
            "description": "User segmentation: linear-only vs linear+VOD vs VOD-only",
            "sql": """
WITH user_types AS (
    SELECT
        device_id,
        MAX(CASE WHEN content_type = 'LINEAR' THEN 1 ELSE 0 END) AS has_linear,
        MAX(CASE WHEN content_type IN ('MOVIE', 'SERIES') THEN 1 ELSE 0 END) AS has_vod,
        SUM(tvt_millisec) / 3600000.0 AS total_hours
    FROM core_prod.session.video_session
    WHERE country = 'US'
      AND date >= CURRENT_DATE - INTERVAL {days} DAYS
      AND tvt_millisec > 0
    GROUP BY device_id
)
SELECT
    CASE
        WHEN has_linear = 1 AND has_vod = 1 THEN 'Linear+VOD'
        WHEN has_linear = 1 AND has_vod = 0 THEN 'Linear Only'
        WHEN has_linear = 0 AND has_vod = 1 THEN 'VOD Only'
        ELSE 'Other'
    END AS segment,
    COUNT(*) AS users,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct_users,
    AVG(total_hours) AS avg_hours_per_user,
    SUM(total_hours) AS total_hours
FROM user_types
GROUP BY 1
ORDER BY users DESC
""",
        },
        "linear_tvt_trend": {
            "description": "Daily linear TVT trend (last N days)",
            "sql": """
SELECT
    date AS dt,
    COUNT(DISTINCT device_id) AS unique_viewers,
    COUNT(*) AS sessions,
    SUM(tvt_millisec) / 3600000.0 AS total_hours
FROM core_prod.session.video_session
WHERE content_type = 'LINEAR'
  AND country = 'US'
  AND date >= CURRENT_DATE - INTERVAL {days} DAYS
  AND tvt_millisec > 0
GROUP BY date
ORDER BY date
""",
        },
        "linear_homepage_funnel": {
            "description": "Homepage linear container presentation → click → watch funnel",
            "sql": """
SELECT
    container,
    COUNT(*) AS presentations,
    SUM(CASE WHEN tvt_sec > 0 THEN 1 ELSE 0 END) AS conversions,
    ROUND(SUM(CASE WHEN tvt_sec > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS ctr_pct,
    AVG(pres_dwell_sec) AS avg_dwell_sec,
    AVG(CASE WHEN tvt_sec > 0 THEN tvt_sec END) AS avg_tvt_when_watched_sec
FROM core_dev.dsa.dsac_viewpres_vidsession_sample
WHERE page_type = 'HomePage'
  AND ds >= CURRENT_DATE - INTERVAL {days} DAYS
  AND container LIKE '%linear%'
GROUP BY container
ORDER BY presentations DESC
""",
        },
        "linear_channel_genre_breakdown": {
            "description": "Linear TVT by channel genre/category",
            "sql": """
SELECT
    ci.primary_genre,
    COUNT(DISTINCT vs.device_id) AS unique_viewers,
    SUM(vs.tvt_millisec) / 3600000.0 AS total_hours,
    ROUND(
        SUM(vs.tvt_millisec) * 100.0
        / SUM(SUM(vs.tvt_millisec)) OVER(), 2
    ) AS pct_of_linear_tvt
FROM core_prod.session.video_session vs
JOIN core_prod.tubidw.content_info ci ON vs.content_id = ci.content_id
WHERE vs.content_type = 'LINEAR'
  AND vs.country = 'US'
  AND vs.date >= CURRENT_DATE - INTERVAL {days} DAYS
  AND vs.tvt_millisec > 0
GROUP BY ci.primary_genre
ORDER BY total_hours DESC
""",
        },
        "linear_first_view_retention": {
            "description": "Retention of users whose first view was linear vs VOD",
            "sql": """
WITH first_views AS (
    SELECT
        vs.device_id,
        MIN(vs.start_ts) AS first_view_ts,
        FIRST_VALUE(vs.content_type) OVER (
            PARTITION BY vs.device_id ORDER BY vs.start_ts
        ) AS first_content_type
    FROM core_prod.session.video_session vs
    JOIN core_prod.tubidw.device_first_metrics dfm
        ON vs.device_id = dfm.device_id
    WHERE vs.country = 'US'
      AND vs.date >= CURRENT_DATE - INTERVAL {days} DAYS
      AND vs.tvt_millisec >= 300000
    GROUP BY vs.device_id, vs.content_type, vs.start_ts
),
cohorts AS (
    SELECT
        device_id,
        CASE WHEN first_content_type = 'LINEAR' THEN 'Linear First' ELSE 'VOD First' END AS cohort
    FROM first_views
    QUALIFY ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY first_view_ts) = 1
)
SELECT
    c.cohort,
    COUNT(DISTINCT c.device_id) AS cohort_size,
    COUNT(DISTINCT CASE
        WHEN vs.date >= DATE(c_first.first_view_ts) + INTERVAL 7 DAYS
        THEN vs.device_id
    END) AS returned_7d
FROM cohorts c
JOIN (SELECT device_id, MIN(first_view_ts) AS first_view_ts FROM first_views GROUP BY device_id) c_first
    ON c.device_id = c_first.device_id
LEFT JOIN core_prod.session.video_session vs
    ON c.device_id = vs.device_id
    AND vs.country = 'US'
    AND vs.tvt_millisec > 0
GROUP BY c.cohort
""",
        },
        "linear_deeplink_attribution": {
            "description": "Deeplink-attributed linear sessions by platform",
            "sql": """
SELECT
    platform,
    page_source,
    COUNT(*) AS sessions,
    COUNT(DISTINCT device_id) AS unique_users,
    SUM(tvt_millisec) / 3600000.0 AS total_hours,
    AVG(tvt_millisec) / 60000.0 AS avg_session_min
FROM core_prod.session.video_session
WHERE content_type = 'LINEAR'
  AND country = 'US'
  AND date >= CURRENT_DATE - INTERVAL {days} DAYS
  AND tvt_millisec > 0
  AND page_source LIKE '%deeplink%'
GROUP BY platform, page_source
ORDER BY total_hours DESC
""",
        },
    }


def list_queries():
    """List all available canonical queries."""
    queries = get_canonical_queries()
    lines = ["Available canonical queries:", ""]
    for name, q in queries.items():
        lines.append(f"  {name}")
        lines.append(f"    {q['description']}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Query Databricks for Tubi Linear TV data"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Raw SQL
    sql_parser = subparsers.add_parser("sql", help="Run raw SQL")
    sql_parser.add_argument("query", help="SQL query string")
    sql_parser.add_argument("--format", choices=["table", "json", "csv"], default="table")
    sql_parser.add_argument("--limit", type=int, default=100)

    # Named queries
    run_parser = subparsers.add_parser("run", help="Run a canonical query")
    run_parser.add_argument("name", help="Query name")
    run_parser.add_argument("--days", type=int, default=30)
    run_parser.add_argument("--limit", type=int, default=50)
    run_parser.add_argument("--format", choices=["table", "json", "csv"], default="table")

    # List queries
    subparsers.add_parser("list", help="List canonical queries")

    # Test connection
    subparsers.add_parser("test", help="Test Databricks connection")

    args = parser.parse_args()

    if args.command == "sql":
        print(run_query(args.query, format=args.format, limit=args.limit))
    elif args.command == "run":
        print(run_named_query(args.name, days=args.days, limit=args.limit, format=args.format))
    elif args.command == "list":
        print(list_queries())
    elif args.command == "test":
        from .connection import test_connection
        if test_connection():
            print("Connection successful!")
        else:
            print("Connection failed. Check your .env credentials.")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
