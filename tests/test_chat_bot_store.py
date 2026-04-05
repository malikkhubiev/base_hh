from __future__ import annotations

from pathlib import Path

from app.core.chat_bot_store import SqliteChatBotStore, SqliteChatBotStoreConfig


def test_chat_bot_store_upsert_and_get(tmp_path: Path) -> None:
    db = tmp_path / "cb.sqlite"
    store = SqliteChatBotStore(config=SqliteChatBotStoreConfig(db_path=str(db)))
    store.upsert_state(
        resume_hash="abc",
        chat_id="chat-1",
        auto_reply_enabled=True,
        polling_enabled=False,
        polling_interval_sec=30,
        system_prompt=None,
        user_prompt_template=None,
        target_text=None,
    )
    row = store.get_state_by_resume_hash(resume_hash="abc")
    assert row is not None
    assert row["chat_id"] == "chat-1"
    assert row["auto_reply_enabled"] == 1
