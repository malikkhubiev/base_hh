from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from app.core.settings import settings


class LogStore(Protocol):
    def save_hh_search_run(
        self,
        *,
        level_name: str,
        query: str,
        iteration: int,
        found_count: int,
        items: list[dict[str, Any]],
    ) -> None: ...


class NoopLogStore:
    def save_hh_search_run(
        self,
        *,
        level_name: str,
        query: str,
        iteration: int,
        found_count: int,
        items: list[dict[str, Any]],
    ) -> None:
        return None


@dataclass(frozen=True)
class PostgresLogStoreConfig:
    dsn: str


class PostgresLogStore:
    def __init__(self, *, config: PostgresLogStoreConfig) -> None:
        self._dsn = config.dsn

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn, autocommit=True)

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS hh_search_runs (
                      id BIGSERIAL PRIMARY KEY,
                      created_at TIMESTAMPTZ NOT NULL,
                      level_name TEXT NOT NULL,
                      query TEXT NOT NULL,
                      iteration INTEGER NOT NULL,
                      found_count INTEGER NOT NULL,
                      items_json JSONB NOT NULL
                    );
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_hh_search_runs_level ON hh_search_runs(level_name);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_hh_search_runs_created_at ON hh_search_runs(created_at);")

    def save_hh_search_run(
        self,
        *,
        level_name: str,
        query: str,
        iteration: int,
        found_count: int,
        items: list[dict[str, Any]],
    ) -> None:
        self.ensure_schema()
        created_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hh_search_runs (created_at, level_name, query, iteration, found_count, items_json)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (created_at, level_name, query, int(iteration), int(found_count), items),
                )


def get_log_store() -> LogStore:
    dsn = (settings.database_url or "").strip()
    if not dsn:
        # SQLite removed; keep app usable without persistence in dev/tests.
        return NoopLogStore()
    return PostgresLogStore(config=PostgresLogStoreConfig(dsn=dsn))

