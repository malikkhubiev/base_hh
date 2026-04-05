from __future__ import annotations

from pathlib import Path

from app.core.log_store import SqliteLogStore, SqliteLogStoreConfig


def test_sqlite_log_store_save(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite"
    store = SqliteLogStore(config=SqliteLogStoreConfig(db_path=str(db)))
    store.save_hh_search_run(
        level_name="Уровень 2",
        query="q",
        iteration=0,
        found_count=1,
        items=[{"id": "1"}],
    )
    assert db.exists()
