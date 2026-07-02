from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from app.core.settings import settings

logger = logging.getLogger(__name__)


class ResumeStore(Protocol):
    def ensure_schema(self) -> None: ...
    def get_resume_json(self, *, resume_id: str) -> dict[str, Any] | None: ...
    def save_resume_json(self, *, resume_id: str, resume_json: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class PostgresResumeStoreConfig:
    dsn: str


class PostgresResumeStore:
    """Хранит полные JSON резюме HH (бесплатный просмотр и/или с контактами)."""

    def __init__(self, *, config: PostgresResumeStoreConfig) -> None:
        self._dsn = config.dsn

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn, autocommit=True)

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS resume_cache (
                      resume_id TEXT PRIMARY KEY,
                      fetched_at TIMESTAMPTZ NOT NULL,
                      resume_json JSONB NOT NULL
                    );
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_resume_cache_fetched_at ON resume_cache(fetched_at);")

    def get_resume_json(self, *, resume_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT resume_json FROM resume_cache WHERE resume_id=%s", (resume_id,))
                row = cur.fetchone()
                if not row:
                    return None
                data = row[0]
                if isinstance(data, dict):
                    return data
                if isinstance(data, str):
                    try:
                        return json.loads(data)
                    except Exception:
                        return None
                return None

    def save_resume_json(self, *, resume_id: str, resume_json: dict[str, Any]) -> None:
        from psycopg.types.json import Json

        fetched_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO resume_cache (resume_id, fetched_at, resume_json)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (resume_id) DO UPDATE SET
                      fetched_at=excluded.fetched_at,
                      resume_json=excluded.resume_json
                    """,
                    (resume_id, fetched_at, Json(resume_json)),
                )


_resume_store: PostgresResumeStore | None = None


def get_resume_store() -> ResumeStore:
    global _resume_store
    dsn = (settings.database_url or "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is not configured (set DB_* env vars or DATABASE_URL)")
    if _resume_store is None or _resume_store._dsn != dsn:
        _resume_store = PostgresResumeStore(config=PostgresResumeStoreConfig(dsn=dsn))
    return _resume_store


def persist_resume(*, resume_id: str, resume_json: dict[str, Any]) -> None:
    """Сохраняет полное JSON резюме HH в кэш (просмотр без контактов или с контактами)."""
    if not resume_id or not isinstance(resume_json, dict) or not resume_json:
        return
    try:
        get_resume_store().save_resume_json(resume_id=str(resume_id), resume_json=resume_json)
    except Exception:
        logger.exception("Failed to persist resume id=%s", resume_id)


def persist_scored_resume(*, resume_id: str, resume_json: dict[str, Any]) -> None:
    """Alias для обратной совместимости."""
    persist_resume(resume_id=resume_id, resume_json=resume_json)
