"""
Проверка записи/чтения таблиц resume_cache, workflow_sessions и traffic_light_cache.

Запуск (из корня проекта):
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
    from app.core.settings import settings

    dsn = (settings.database_url or "").strip()
    if not dsn:
        print("ERROR: задайте DB_* env vars или DATABASE_URL")
        return 1

    from app.core.resume_store import get_resume_store, persist_scored_resume
    from app.core.traffic_light_store import get_traffic_light_store, persist_traffic_light_batch
    from app.core.workflow_session import ensure_session_schema, create_session, get_session

    store = get_resume_store()
    print("Подключение OK, применяю схему resume_cache, workflow_sessions, traffic_light_cache...")
    store.ensure_schema()
    ensure_session_schema()
    get_traffic_light_store().ensure_schema()

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

    print("OK: resume_cache — запись, чтение и upsert работают.")

    session = create_session(
        request_text="Postgres verify session",
        area_ids=[113, 16],
        candidates_limit=10,
        candidate_ids=[TEST_RESUME_ID],
    )
    loaded_session = get_session(session.session_id)
    if loaded_session is None or loaded_session.request_text != "Postgres verify session":
        print("ERROR: workflow_sessions — сессия не прочиталась из Postgres")
        return 1

    persist_traffic_light_batch(
        session_id=session.session_id,
        items=[
            {
                "id": TEST_RESUME_ID,
                "candidate_name": "User Test",
                "title": "Dev",
                "location": "Moscow",
                "color_score_percent": 77,
                "requirements": [
                    {
                        "requirement": "Python",
                        "resume_evidence": "ACME",
                        "match_percent": 100,
                        "difference_comment": "OK",
                    }
                ],
            }
        ],
    )
    tl_loaded = get_traffic_light_store().get_for_session(
        session_id=session.session_id,
        resume_ids=[TEST_RESUME_ID],
    )
    if TEST_RESUME_ID not in tl_loaded or tl_loaded[TEST_RESUME_ID].color_score_percent != 77:
        print("ERROR: traffic_light_cache — данные не совпали")
        return 1

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM traffic_light_cache WHERE session_id = %s", (session.session_id,))
            cur.execute("DELETE FROM workflow_sessions WHERE session_id = %s", (session.session_id,))
            cur.execute("DELETE FROM resume_cache WHERE resume_id = %s", (TEST_RESUME_ID,))

    print("OK: workflow_sessions и traffic_light_cache — запись и чтение работают.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
