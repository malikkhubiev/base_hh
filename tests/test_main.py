from __future__ import annotations

from app.main import create_app


def test_create_app_title() -> None:
    app = create_app()
    assert app.title == "HH Optimizer UI"
