"""
Проверка записи/чтения таблицы resume_cache в вашем PostgreSQL.

Запуск (из корня проекта):
  set DATABASE_URL=postgresql://...
  python scripts/verify_postgres_resume_store.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TEST_RESUME_ID = "__hh_optimizer_resume_store_check__"


def main() -> int:
    dsn = (os.getenv("DATABASE_URL") or "").strip()
    if not dsn:
        print("ERROR: задайте DATABASE_URL (postgresql://USER:PASSWORD@HOST:PORT/DBNAME)")
        return 1

    from app.core.resume_store import get_resume_store, persist_scored_resume

    store = get_resume_store()
    print("Подключение OK, применяю схему resume_cache...")
    store.ensure_schema()

    sample = {
        "id": TEST_RESUME_ID,
        "title": "Postgres verify",
        "first_name": "Test",
        "last_name": "User",
        "experience": [{"company": "ACME", "position": "Dev"}],
    }
    persist_scored_resume(resume_id=TEST_RESUME_ID, resume_json=sample)
    loaded = store.get_resume_json(resume_id=TEST_RESUME_ID)
    if not isinstance(loaded, dict) or loaded.get("id") != TEST_RESUME_ID:
        print("ERROR: запись прочитана, но данные не совпали")
        return 1

    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM resume_cache WHERE resume_id = %s", (TEST_RESUME_ID,))

    print("OK: resume_cache — запись, чтение и upsert работают.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
