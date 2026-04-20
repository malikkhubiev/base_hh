from __future__ import annotations

from datetime import datetime
from zipfile import ZipFile
import io

import pytest

from app.services.excel_export import build_search_excel_bytes, xlsxwriter_available


pytestmark = pytest.mark.skipif(not xlsxwriter_available(), reason="xlsxwriter not installed")


def test_build_search_excel_bytes_creates_workbook() -> None:
    t0 = datetime(2026, 4, 5, 12, 0, 0)
    raw, name = build_search_excel_bytes(
        request_text="test vacancy",
        level_queries={"Уровень 2": "python AND fastapi"},
        queries_with_exclusions={"Уровень 2": "python AND fastapi NOT junior"},
        hh_search_urls={"Уровень 2": "https://example.com/hh?q=1"},
        selected_level="Уровень 2",
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


def _xlsx_shared_strings(raw: bytes) -> str:
    with ZipFile(io.BytesIO(raw), "r") as zf:
        return zf.read("xl/sharedStrings.xml").decode("utf-8")


def test_build_search_excel_bytes_formats_subsecond_stage_timings() -> None:
    t0 = datetime(2026, 4, 5, 12, 0, 0, 0)
    raw, _ = build_search_excel_bytes(
        request_text="test vacancy",
        level_queries={"Уровень 2": "python AND fastapi"},
        queries_with_exclusions={"Уровень 2": "python AND fastapi NOT junior"},
        hh_search_urls={"Уровень 2": "https://example.com/hh?q=1"},
        selected_level="Уровень 2",
        found_counts={"Уровень 2": 2},
        candidates_by_level_raw={"Уровень 2": [{"id": "1"}]},
        traffic_light_candidates=[],
        started_at=t0,
        bool_finished_at=datetime(2026, 4, 5, 12, 0, 0, 500000),
        hh_finished_at=datetime(2026, 4, 5, 12, 0, 1, 200000),
        finished_at=datetime(2026, 4, 5, 12, 0, 1, 300000),
        ran_traffic_light=True,
    )
    shared_strings = _xlsx_shared_strings(raw)
    assert "0.500 s" in shared_strings
    assert "0.700 s" in shared_strings
    assert "0.100 s" in shared_strings


def test_build_search_excel_bytes_hides_tl_timing_when_not_run() -> None:
    t0 = datetime(2026, 4, 5, 12, 0, 0)
    raw, _ = build_search_excel_bytes(
        request_text="test vacancy",
        level_queries={"Уровень 2": "python AND fastapi"},
        queries_with_exclusions={"Уровень 2": "python AND fastapi NOT junior"},
        hh_search_urls={"Уровень 2": "https://example.com/hh?q=1"},
        selected_level="Уровень 2",
        found_counts={"Уровень 2": 2},
        candidates_by_level_raw={"Уровень 2": [{"id": "1"}]},
        traffic_light_candidates=[],
        started_at=t0,
        bool_finished_at=t0,
        hh_finished_at=t0,
        finished_at=datetime(2026, 4, 5, 12, 0, 0, 200000),
        ran_traffic_light=False,
    )
    shared_strings = _xlsx_shared_strings(raw)
    assert "Время построения Светофора:" not in shared_strings
