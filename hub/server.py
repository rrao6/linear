#!/usr/bin/env python3
"""
Linear Hub — FastAPI backend server.

Usage:
    python3 hub/server.py                  # Start on port 8888
    python3 hub/server.py --port 3000      # Custom port
"""

import argparse
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import HUB_PORT, HUB_HOST
from .monitoring import start_checker, stop_checker

logger = logging.getLogger(__name__)

# Import routers gracefully — missing routers (from unmerged PRs) should not
# crash the entire server.
_ROUTER_NAMES = [
    "dashboard", "intel", "data", "sentiment", "features", "oem",
    "strategy", "search", "qa", "monitor", "knowledge",
    "insights", "ask", "problems",
]
_routers = {}
for _name in _ROUTER_NAMES:
    try:
        _mod = __import__(f"hub.routers.{_name}", fromlist=["router"])
        _routers[_name] = _mod.router
    except Exception as e:
        logger.warning("Router %r unavailable, skipping: %s", _name, e)


@asynccontextmanager
async def lifespan(app):
    start_checker(interval_seconds=1800)
    try:
        from .qa.runner import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning("QA scheduler failed to start: %s", e)
    yield
    stop_checker()
    try:
        from .qa.runner import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.warning("QA scheduler failed to stop: %s", e)

app = FastAPI(
    title="Linear Hub",
    description="SSOT for Tubi Linear TV strategy, data, competitive intelligence, and operations",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount available routers
for _name, _router in _routers.items():
    app.include_router(_router)

# Static files
STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "service": "linear-hub"}


# Mount static last so API routes take priority
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main():
    parser = argparse.ArgumentParser(description="Linear Hub Server")
    parser.add_argument("--port", type=int, default=HUB_PORT)
    parser.add_argument("--host", default=HUB_HOST)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    print(f"\n  Linear Hub running at http://{args.host}:{args.port}")
    print(f"  API docs at http://{args.host}:{args.port}/docs")
    print(f"  Press Ctrl+C to stop.\n")

    uvicorn.run(
        "hub.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
