from __future__ import annotations

from datetime import datetime

import pytest

from app.services.excel_export import build_search_excel_bytes, xlsxwriter_available


pytestmark = pytest.mark.skipif(not xlsxwriter_available(), reason="xlsxwriter not installed")


def test_build_search_excel_bytes_creates_workbook() -> None:
    t0 = datetime(2026, 4, 5, 12, 0, 0)
    raw, name = build_search_excel_bytes(
        request_text="test vacancy",
        found_counts={"Уровень 2": 2},
        candidates_by_level_raw={
            "Уровень 2": [
                {"id": "1", "first_name": "A", "title": "Dev"},
            ]
        },
        traffic_light_candidates=[],
        started_at=t0,
        bool_finished_at=t0,
        hh_finished_at=t0,
        finished_at=t0,
        ran_traffic_light=False,
    )
    assert raw.startswith(b"PK")
    assert name.endswith(".xlsx")
    assert name.startswith("hh_search_")
