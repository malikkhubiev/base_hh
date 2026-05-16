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
    """Хранит полные JSON резюме HH только после платного открытия в сценарии скоринга."""

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
                    (resume_id, fetched_at, resume_json),
                )


class NoopResumeStore:
    def ensure_schema(self) -> None:
        return None

    def get_resume_json(self, *, resume_id: str) -> dict[str, Any] | None:
        return None

    def save_resume_json(self, *, resume_id: str, resume_json: dict[str, Any]) -> None:
        return None


def get_resume_store() -> ResumeStore:
    dsn = (settings.database_url or "").strip()
    if not dsn:
        return NoopResumeStore()
    return PostgresResumeStore(config=PostgresResumeStoreConfig(dsn=dsn))


def persist_scored_resume(*, resume_id: str, resume_json: dict[str, Any]) -> None:
    """Сохраняет полное резюме после открытия в скоринге (traffic_light / screening / svetofor)."""
    if not resume_id or not isinstance(resume_json, dict) or not resume_json:
        return
    try:
        get_resume_store().save_resume_json(resume_id=str(resume_id), resume_json=resume_json)
    except Exception:
        logger.exception("Failed to persist scored resume id=%s", resume_id)
