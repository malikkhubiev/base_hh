from __future__ import annotations

from app.core.settings import Settings


def test_settings_defaults() -> None:
    s = Settings()
    assert s.token_source == "ssp"
    assert isinstance(s.area_id, int)
