from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock

from app.core.settings import settings

logger = logging.getLogger(__name__)

# HH area_id: 113 — Россия, 16 — Беларусь
DEFAULT_AREA_IDS: list[int] = [113, 16]

_lock = Lock()
_sessions: dict[str, WorkflowSession] = {}


@dataclass
class WorkflowSession:
    session_id: str
    request_text: str
    area_ids: list[int]
    candidates_limit: int
    candidate_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _postgres_dsn() -> str:
    return (settings.database_url or "").strip()


def _connect():
    import psycopg

    return psycopg.connect(_postgres_dsn(), autocommit=True)


def ensure_session_schema() -> None:
    """Создаёт таблицу workflow_sessions при наличии DATABASE_URL."""
    dsn = _postgres_dsn()
    if not dsn:
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_sessions (
                  session_id TEXT PRIMARY KEY,
                  request_text TEXT NOT NULL,
                  area_ids JSONB NOT NULL,
                  candidates_limit INT NOT NULL,
                  candidate_ids JSONB NOT NULL,
                  created_at TIMESTAMPTZ NOT NULL
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_sessions_created_at ON workflow_sessions(created_at);"
            )


def _session_to_row(session: WorkflowSession) -> tuple:
    return (
        session.session_id,
        session.request_text,
        json.dumps(session.area_ids),
        int(session.candidates_limit),
        json.dumps(session.candidate_ids),
        session.created_at,
    )


def _row_to_session(row: tuple) -> WorkflowSession:
    session_id, request_text, area_ids_raw, candidates_limit, candidate_ids_raw, created_at = row
    area_ids = area_ids_raw if isinstance(area_ids_raw, list) else json.loads(area_ids_raw or "[]")
    candidate_ids = candidate_ids_raw if isinstance(candidate_ids_raw, list) else json.loads(candidate_ids_raw or "[]")
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return WorkflowSession(
        session_id=str(session_id),
        request_text=str(request_text or ""),
        area_ids=[int(x) for x in area_ids],
        candidates_limit=int(candidates_limit),
        candidate_ids=[str(x) for x in candidate_ids if str(x)],
        created_at=created_at,
    )


def _save_session_pg(session: WorkflowSession) -> None:
    dsn = _postgres_dsn()
    if not dsn:
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_sessions
                  (session_id, request_text, area_ids, candidates_limit, candidate_ids, created_at)
                VALUES (%s, %s, %s::jsonb, %s, %s::jsonb, %s)
                ON CONFLICT (session_id) DO UPDATE SET
                  request_text=excluded.request_text,
                  area_ids=excluded.area_ids,
                  candidates_limit=excluded.candidates_limit,
                  candidate_ids=excluded.candidate_ids,
                  created_at=excluded.created_at
                """,
                _session_to_row(session),
            )


def _load_session_pg(session_id: str) -> WorkflowSession | None:
    dsn = _postgres_dsn()
    if not dsn:
        return None
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, request_text, area_ids, candidates_limit, candidate_ids, created_at
                FROM workflow_sessions
                WHERE session_id = %s
                """,
                (str(session_id or ""),),
            )
            row = cur.fetchone()
            if not row:
                return None
            return _row_to_session(row)


def create_session(
    *,
    request_text: str,
    area_ids: list[int],
    candidates_limit: int,
    candidate_ids: list[str],
) -> WorkflowSession:
    session = WorkflowSession(
        session_id=str(uuid.uuid4()),
        request_text=request_text,
        area_ids=list(area_ids),
        candidates_limit=int(candidates_limit),
        candidate_ids=[str(x) for x in candidate_ids if str(x)],
    )
    with _lock:
        _sessions[session.session_id] = session
    try:
        _save_session_pg(session)
    except Exception:
        logger.exception("Failed to persist workflow session id=%s", session.session_id)
    return session


def get_session(session_id: str) -> WorkflowSession | None:
    sid = str(session_id or "")
    if not sid:
        return None
    with _lock:
        cached = _sessions.get(sid)
    if cached is not None:
        return cached
    try:
        loaded = _load_session_pg(sid)
    except Exception:
        logger.exception("Failed to load workflow session id=%s", sid)
        return None
    if loaded is not None:
        with _lock:
            _sessions[sid] = loaded
    return loaded


def require_session(session_id: str) -> WorkflowSession:
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"session not found: {session_id}")
    return session
