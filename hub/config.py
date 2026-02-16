"""Hub configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Paths
SCANS_DIR = ROOT / "intel" / "scans"
INTEL_DIR = ROOT / "intel"
ANALYSIS_DIR = ROOT / "analysis"
DOCS_DIR = ROOT / "docs"
DATA_DIR = ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma"
HUB_DB_PATH = DATA_DIR / "hub.db"
TOOLS_DIR = ROOT / "tools"
SCANNER_DIR = TOOLS_DIR / "scanner"
PLUGINS_DIR = ROOT / "plugins"

# Databricks
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")
DATABRICKS_HTTP_PATH = os.environ.get("DATABRICKS_HTTP_PATH", "")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "")

# OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Server
HUB_PORT = int(os.environ.get("HUB_PORT", "8888"))
HUB_HOST = os.environ.get("HUB_HOST", "localhost")
