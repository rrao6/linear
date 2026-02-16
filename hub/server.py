#!/usr/bin/env python3
"""
Linear Hub — FastAPI backend server.

Usage:
    python3 hub/server.py                  # Start on port 8888
    python3 hub/server.py --port 3000      # Custom port
"""

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import HUB_PORT, HUB_HOST
from .routers import dashboard, intel, data, sentiment, features, oem, strategy, search, qa

app = FastAPI(
    title="Linear Hub",
    description="SSOT for Tubi Linear TV strategy, data, competitive intelligence, and operations",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(dashboard.router)
app.include_router(intel.router)
app.include_router(data.router)
app.include_router(sentiment.router)
app.include_router(features.router)
app.include_router(oem.router)
app.include_router(strategy.router)
app.include_router(search.router)
app.include_router(qa.router)

# Static files
STATIC_DIR = Path(__file__).parent / "static"


@app.on_event("startup")
def startup_event():
    """Start background services on server boot."""
    from .qa.runner import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
def shutdown_event():
    """Stop background services on server shutdown."""
    from .qa.runner import stop_scheduler
    stop_scheduler()


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
