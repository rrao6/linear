"""Thread-safe Databricks connection with retry logic."""

import os
import threading
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root
_env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_env_path)


class ConnectionProvider:
    """Thread-safe, lazy Databricks connection with health checks and retry."""

    def __init__(self):
        self._conn = None
        self._lock = threading.RLock()

    @property
    def host(self) -> str:
        return os.environ.get("DATABRICKS_HOST", "")

    @property
    def http_path(self) -> str:
        return os.environ.get("DATABRICKS_HTTP_PATH", "")

    @property
    def token(self) -> str:
        return os.environ.get("DATABRICKS_TOKEN", "")

    @property
    def catalog(self) -> str:
        return os.environ.get("DATABRICKS_CATALOG", "core_prod")

    @property
    def schema(self) -> str:
        return os.environ.get("DATABRICKS_SCHEMA", "tubidw")

    def _validate_config(self):
        missing = []
        if not self.host:
            missing.append("DATABRICKS_HOST")
        if not self.http_path:
            missing.append("DATABRICKS_HTTP_PATH")
        if not self.token:
            missing.append("DATABRICKS_TOKEN")
        if missing:
            raise RuntimeError(
                f"Missing Databricks credentials: {', '.join(missing)}\n"
                f"Add them to {_env_path}"
            )

    def _connect(self):
        from databricks import sql

        self._validate_config()
        self._conn = sql.connect(
            server_hostname=self.host,
            http_path=self.http_path,
            access_token=self.token,
            catalog=self.catalog,
            schema=self.schema,
        )
        return self._conn

    def _is_alive(self) -> bool:
        if self._conn is None:
            return False
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False

    def get_connection(self):
        with self._lock:
            if not self._is_alive():
                if self._conn is not None:
                    try:
                        self._conn.close()
                    except Exception:
                        pass
                self._connect()
            return self._conn

    def close(self):
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None


_provider = ConnectionProvider()


class _CursorContext:
    """Context manager for a Databricks cursor."""

    def __enter__(self):
        conn = _provider.get_connection()
        self._cursor = conn.cursor()
        return self._cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._cursor.close()
        except Exception:
            pass
        return False


def get_cursor():
    """Get a cursor context manager. Usage: `with get_cursor() as cur: ...`"""
    return _CursorContext()


def test_connection() -> bool:
    """Test that we can connect to Databricks."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            row = cur.fetchone()
            return row is not None
    except Exception as e:
        print(f"Connection failed: {e}")
        return False
