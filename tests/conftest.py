from __future__ import annotations

import os
from typing import Any

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/hh_optimizer_test")
os.environ.setdefault("SKIP_DB_INIT", "1")


class InMemoryResumeStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def ensure_schema(self) -> None:
        return None

    def get_resume_json(self, *, resume_id: str) -> dict[str, Any] | None:
        return self._data.get(resume_id)

    def save_resume_json(self, *, resume_id: str, resume_json: dict[str, Any]) -> None:
        self._data[resume_id] = resume_json


@pytest.fixture(autouse=True)
def _resume_store(monkeypatch: pytest.MonkeyPatch) -> InMemoryResumeStore:
    store = InMemoryResumeStore()
    monkeypatch.setattr("app.core.resume_store.get_resume_store", lambda: store)
    return store
