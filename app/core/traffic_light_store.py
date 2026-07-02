from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrafficLightRecord:
    resume_id: str
    candidate_name: str | None
    title: str | None
    location: str | None
    color_score_percent: int
    requirements: list[dict[str, Any]]


class PostgresTrafficLightStore:
    """Хранит результаты светофора (этап 2) для последующего этапа 3."""

    def __init__(self, *, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn, autocommit=True)

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS traffic_light_cache (
                      session_id TEXT NOT NULL,
                      resume_id TEXT NOT NULL,
                      scored_at TIMESTAMPTZ NOT NULL,
                      candidate_name TEXT,
                      title TEXT,
                      location TEXT,
                      color_score_percent INT NOT NULL DEFAULT 0,
                      requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
                      PRIMARY KEY (session_id, resume_id)
                    );
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_traffic_light_cache_session ON traffic_light_cache(session_id);"
                )

    def save_batch(
        self,
        *,
        session_id: str,
        items: list[dict[str, Any]],
    ) -> None:
        sid = str(session_id or "").strip()
        if not sid or not items:
            return
        scored_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            with conn.cursor() as cur:
                for item in items:
                    resume_id = str(item.get("id") or "").strip()
                    if not resume_id:
                        continue
                    requirements = item.get("requirements") or []
                    if not isinstance(requirements, list):
                        requirements = []
                    cur.execute(
                        """
                        INSERT INTO traffic_light_cache
                          (session_id, resume_id, scored_at, candidate_name, title, location,
                           color_score_percent, requirements)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (session_id, resume_id) DO UPDATE SET
                          scored_at=excluded.scored_at,
                          candidate_name=excluded.candidate_name,
                          title=excluded.title,
                          location=excluded.location,
                          color_score_percent=excluded.color_score_percent,
                          requirements=excluded.requirements
                        """,
                        (
                            sid,
                            resume_id,
                            scored_at,
                            item.get("candidate_name"),
                            item.get("title"),
                            item.get("location"),
                            int(item.get("color_score_percent") or 0),
                            json.dumps(requirements),
                        ),
                    )

    def get_for_session(
        self,
        *,
        session_id: str,
        resume_ids: list[str],
    ) -> dict[str, TrafficLightRecord]:
        sid = str(session_id or "").strip()
        ids = [str(x).strip() for x in resume_ids if str(x).strip()]
        if not sid or not ids:
            return {}
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT resume_id, candidate_name, title, location, color_score_percent, requirements
                    FROM traffic_light_cache
                    WHERE session_id = %s AND resume_id = ANY(%s)
                    """,
                    (sid, ids),
                )
                rows = cur.fetchall()
        out: dict[str, TrafficLightRecord] = {}
        for row in rows:
            resume_id, candidate_name, title, location, color_score_percent, requirements_raw = row
            requirements = requirements_raw if isinstance(requirements_raw, list) else json.loads(requirements_raw or "[]")
            if not isinstance(requirements, list):
                requirements = []
            out[str(resume_id)] = TrafficLightRecord(
                resume_id=str(resume_id),
                candidate_name=candidate_name,
                title=title,
                location=location,
                color_score_percent=int(color_score_percent or 0),
                requirements=[x for x in requirements if isinstance(x, dict)],
            )
        return out


_traffic_light_store: PostgresTrafficLightStore | None = None


def get_traffic_light_store() -> PostgresTrafficLightStore:
    global _traffic_light_store
    dsn = (settings.database_url or "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is not configured (set DB_* env vars or DATABASE_URL)")
    if _traffic_light_store is None or _traffic_light_store._dsn != dsn:
        _traffic_light_store = PostgresTrafficLightStore(dsn=dsn)
    return _traffic_light_store


def persist_traffic_light_batch(*, session_id: str, items: list[dict[str, Any]]) -> None:
    if not session_id or not items:
        return
    try:
        get_traffic_light_store().save_batch(session_id=session_id, items=items)
    except Exception:
        logger.exception("Failed to persist traffic light session_id=%s", session_id)
