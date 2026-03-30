from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SqliteChatBotStoreConfig:
    db_path: str


class SqliteChatBotStore:
    """
    Persistence for chat-bot automation:
    - mapping chat_id <-> resume_hash (safety filter)
    - last processed message id to avoid duplicates
    - bot prompts + polling settings
    """

    def __init__(self, *, config: SqliteChatBotStoreConfig) -> None:
        self._db_path = config.db_path

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_bot_state (
                    resume_hash TEXT PRIMARY KEY,
                    chat_id TEXT,
                    auto_reply_enabled INTEGER NOT NULL DEFAULT 0,
                    polling_enabled INTEGER NOT NULL DEFAULT 0,
                    polling_interval_sec INTEGER NOT NULL DEFAULT 30,
                    system_prompt TEXT,
                    user_prompt_template TEXT,
                    target_text TEXT,
                    last_processed_message_id TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_bot_state_chat_id ON chat_bot_state(chat_id);")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_bot_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    resume_hash TEXT,
                    chat_id TEXT,
                    message_id TEXT,
                    source TEXT,
                    incoming_text TEXT,
                    reply_text TEXT,
                    ok INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );
                """
            )
            conn.commit()

    def upsert_state(
        self,
        *,
        resume_hash: str,
        chat_id: str | None,
        auto_reply_enabled: bool,
        polling_enabled: bool,
        polling_interval_sec: int,
        system_prompt: str | None,
        user_prompt_template: str | None,
        target_text: str | None,
    ) -> None:
        self.ensure_schema()
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_bot_state (
                    resume_hash, chat_id, auto_reply_enabled, polling_enabled, polling_interval_sec,
                    system_prompt, user_prompt_template, target_text, last_processed_message_id, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT last_processed_message_id FROM chat_bot_state WHERE resume_hash=?), NULL), ?)
                ON CONFLICT(resume_hash) DO UPDATE SET
                    chat_id=excluded.chat_id,
                    auto_reply_enabled=excluded.auto_reply_enabled,
                    polling_enabled=excluded.polling_enabled,
                    polling_interval_sec=excluded.polling_interval_sec,
                    system_prompt=excluded.system_prompt,
                    user_prompt_template=excluded.user_prompt_template,
                    target_text=excluded.target_text,
                    updated_at=excluded.updated_at
                ;
                """,
                (
                    resume_hash,
                    chat_id,
                    int(bool(auto_reply_enabled)),
                    int(bool(polling_enabled)),
                    int(polling_interval_sec),
                    system_prompt,
                    user_prompt_template,
                    target_text,
                    resume_hash,
                    updated_at,
                ),
            )

    def update_last_processed(self, *, resume_hash: str, message_id: str) -> None:
        self.ensure_schema()
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE chat_bot_state
                SET last_processed_message_id=?, updated_at=?
                WHERE resume_hash=?
                """,
                (message_id, updated_at, resume_hash),
            )

    def set_polling_flags(self, *, resume_hash: str, polling_enabled: bool, polling_interval_sec: int | None) -> None:
        self.ensure_schema()
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            if polling_interval_sec is None:
                conn.execute(
                    """
                    UPDATE chat_bot_state
                    SET polling_enabled=?, updated_at=?
                    WHERE resume_hash=?
                    """,
                    (int(bool(polling_enabled)), updated_at, resume_hash),
                )
            else:
                conn.execute(
                    """
                    UPDATE chat_bot_state
                    SET polling_enabled=?, polling_interval_sec=?, updated_at=?
                    WHERE resume_hash=?
                    """,
                    (int(bool(polling_enabled)), int(polling_interval_sec), updated_at, resume_hash),
                )

    def get_state_by_resume_hash(self, *, resume_hash: str) -> dict | None:
        self.ensure_schema()
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM chat_bot_state WHERE resume_hash=?", (resume_hash,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

    def get_state_by_chat_id(self, *, chat_id: str) -> dict | None:
        self.ensure_schema()
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM chat_bot_state WHERE chat_id=? LIMIT 1", (chat_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

    def get_polling_enabled_states(self) -> list[dict]:
        self.ensure_schema()
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM chat_bot_state
                WHERE polling_enabled=1 AND auto_reply_enabled=1 AND chat_id IS NOT NULL
                """
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]

    def add_event(
        self,
        *,
        resume_hash: str,
        chat_id: str | None,
        message_id: str | None,
        source: str,
        incoming_text: str | None,
        reply_text: str | None,
        ok: bool,
        error: str | None,
    ) -> None:
        self.ensure_schema()
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_bot_events (
                    created_at, resume_hash, chat_id, message_id, source,
                    incoming_text, reply_text, ok, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    resume_hash,
                    chat_id,
                    message_id,
                    source,
                    incoming_text,
                    reply_text,
                    int(bool(ok)),
                    error,
                ),
            )

    def list_recent_events(self, *, limit: int = 30) -> list[dict]:
        self.ensure_schema()
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM chat_bot_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]


def get_chat_bot_store() -> SqliteChatBotStore:
    db_path = os.getenv("CHAT_BOT_DB_PATH", "hh_chat_bot.sqlite")
    return SqliteChatBotStore(config=SqliteChatBotStoreConfig(db_path=db_path))

