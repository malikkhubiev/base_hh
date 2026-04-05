from __future__ import annotations

import logging

from app.core.logging import setup_logging


def test_setup_logging_runs() -> None:
    setup_logging()
    assert logging.getLogger().level >= 0
