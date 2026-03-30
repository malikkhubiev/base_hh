from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


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


@dataclass(frozen=True)
class SqliteLogStoreConfig:
    db_path: str


class SqliteLogStore:
    """
    Simple persistence layer for HH search runs.

    Rationale:
    - render.com forbids writing arbitrary JSON logs to files;
    - keep storage behind an interface so it is easy to swap to another DB later.
    """

    def __init__(self, *, config: SqliteLogStoreConfig) -> None:
        self._db_path = config.db_path

    def _connect(self) -> sqlite3.Connection:
        # check_same_thread=False because we may call this from asyncio.to_thread.
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def ensure_schema(self) -> None:
        # Create tables once. Safe to call repeatedly.
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hh_search_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    level_name TEXT NOT NULL,
                    query TEXT NOT NULL,
                    iteration INTEGER NOT NULL,
                    found_count INTEGER NOT NULL,
                    items_json TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hh_search_runs_level ON hh_search_runs(level_name);")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hh_search_runs_created_at ON hh_search_runs(created_at);"
            )

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
        created_at = datetime.now(timezone.utc).isoformat()
        items_json = json.dumps(items, ensure_ascii=False)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO hh_search_runs (created_at, level_name, query, iteration, found_count, items_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (created_at, level_name, query, iteration, int(found_count), items_json),
            )


def get_log_store() -> LogStore:
    db_path = os.getenv("LOG_DB_PATH", "hh_optimizer.sqlite")
    return SqliteLogStore(config=SqliteLogStoreConfig(db_path=db_path))

