import json
import logging
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class GeoSQLiteCache:
    """Thread-safe SQLite geospatial cache for NASA POWER, SRTM, and SoilGrids/SSURGO payloads."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = Path(db_path or settings.geo_cache_db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS geo_cache (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    PRIMARY KEY (namespace, cache_key)
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_geo_cache_expires ON geo_cache (expires_at)"
            )
            self._conn.commit()

    @staticmethod
    def grid_key(lat: float, lon: float, step_deg: float = 0.01, extra: str = "") -> str:
        """Snap coordinates onto a deterministic spatial grid (~1.1 km at 0.01°, ~5.5 km at 0.05°)."""
        q_lat = round(round(lat / step_deg) * step_deg, 4)
        q_lon = round(round(lon / step_deg) * step_deg, 4)
        return f"{q_lat:.4f},{q_lon:.4f}" + (f"|{extra}" if extra else "")

    def get_json(self, namespace: str, cache_key: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        try:
            with self._lock:
                row = self._conn.execute(
                    "SELECT payload_json, expires_at FROM geo_cache WHERE namespace = ? AND cache_key = ?",
                    (namespace, cache_key),
                ).fetchone()
                if not row:
                    return None
                payload_json, expires_at = row
                if expires_at <= now:
                    self._conn.execute(
                        "DELETE FROM geo_cache WHERE namespace = ? AND cache_key = ?",
                        (namespace, cache_key),
                    )
                    self._conn.commit()
                    return None
            return json.loads(payload_json)
        except Exception as exc:
            logger.debug("Geo cache read error (%s:%s): %s", namespace, cache_key, exc)
            return None

    def set_json(
        self,
        namespace: str,
        cache_key: str,
        payload: Dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        now = time.time()
        expires_at = now + max(60, int(ttl_seconds))
        try:
            serialized = json.dumps(payload, ensure_ascii=False)
            with self._lock:
                self._conn.execute(
                    """
                    INSERT INTO geo_cache (namespace, cache_key, payload_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(namespace, cache_key) DO UPDATE SET
                        payload_json = excluded.payload_json,
                        created_at = excluded.created_at,
                        expires_at = excluded.expires_at
                    """,
                    (namespace, cache_key, serialized, now, expires_at),
                )
                self._conn.commit()
        except Exception as exc:
            logger.debug("Geo cache write error (%s:%s): %s", namespace, cache_key, exc)

    def stats(self) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                "SELECT namespace, COUNT(*) FROM geo_cache WHERE expires_at > ? GROUP BY namespace",
                (now,),
            ).fetchall()
            total = sum(count for _, count in rows)
            by_namespace = {ns: count for ns, count in rows}
        return {
            "enabled": True,
            "db_path": str(self.db_path),
            "active_entries": total,
            "by_namespace": by_namespace,
        }


geo_cache = GeoSQLiteCache()
