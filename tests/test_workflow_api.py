from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _override_body():
    return {
        "request_text": "Python",
        "queries_override": {
            "Уровень 1": "q1",
            "Уровень 2": "q2",
            "Уровень 3": "q3",
        },
    }


def test_api_default_request(client: TestClient) -> None:
    r = client.get("/api/default_request")
    assert r.status_code == 200
    assert len(r.text) > 0


def test_api_generate_queries_override(client: TestClient) -> None:
    r = client.post(
        "/api/generate_queries",
        json={
            "request_text": "",
            "queries_override": {"Уровень 1": "a", "Уровень 2": "b", "Уровень 3": "c"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["llm_raw"] is None
    assert data["queries"]["Уровень 2"] == "b"


@patch("app.api.routes.workflow.HHSearchService")
def test_api_search_mocked(mock_hh_cls, client: TestClient) -> None:
    inst = MagicMock()
    mock_hh_cls.return_value = inst
    inst.search_counts_and_candidates.return_value = (
        {"Уровень 1": 0, "Уровень 2": 2, "Уровень 3": 0},
        {
            "Уровень 1": [],
            "Уровень 2": [{"id": "1", "title": "Dev", "skills": [], "tags": []}],
            "Уровень 3": [],
        },
        {"Уровень 1": "x", "Уровень 2": "y", "Уровень 3": "z"},
        {"Уровень 1": "u1", "Уровень 2": "u2", "Уровень 3": "u3"},
    )
    r = client.post("/api/search", json=_override_body())
    assert r.status_code == 200
    data = r.json()
    assert data["found_counts"]["Уровень 2"] == 2
    assert data["candidates_by_level"]["Уровень 2"][0]["id"] == "1"


@patch("app.api.routes.workflow._collect_traffic_light_candidates", new_callable=AsyncMock)
@patch("app.api.routes.workflow.HHSearchService")
def test_api_svetofor_mocked(mock_hh_cls, mock_tl, client: TestClient) -> None:
    inst = MagicMock()
    mock_hh_cls.return_value = inst
    inst.search_counts_and_candidates.return_value = (
        {"Уровень 1": 0, "Уровень 2": 1, "Уровень 3": 0},
        {
            "Уровень 1": [],
            "Уровень 2": [{"id": "1", "title": "T", "first_name": "A", "last_name": "B", "skills": [], "tags": []}],
            "Уровень 3": [],
        },
        {"Уровень 1": "a", "Уровень 2": "b", "Уровень 3": "c"},
        {"Уровень 1": "u1", "Уровень 2": "u2", "Уровень 3": "u3"},
    )
    mock_tl.return_value = []

    r = client.post("/api/svetofor", json=_override_body())
    assert r.status_code == 200
    assert r.json()["traffic_light_candidates"] == []


@patch("app.api.routes.workflow._collect_traffic_light_candidates", new_callable=AsyncMock)
@patch("app.api.routes.workflow.HHSearchService")
def test_api_traffic_light_from_candidates_mocked(mock_hh_cls, mock_tl, client: TestClient) -> None:
    inst = MagicMock()
    mock_hh_cls.return_value = inst
    mock_tl.return_value = []

    r = client.post(
        "/api/traffic_light",
        json={
            "request_text": "Python",
            "selected_level": "Уровень 2",
            "svetofor_top_x": 3,
            "candidates": [
                {"id": "1", "title": "Dev", "first_name": "A", "last_name": "B", "skills": [], "tags": []},
                {"id": "2", "title": "Dev2", "first_name": "C", "last_name": "D", "skills": [], "tags": []},
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["selected_level"] == "Уровень 2"
    assert data["traffic_light_candidates"] == []


@patch("app.api.routes.workflow.HHSearchService")
def test_api_export_excel_mocked(mock_hh_cls, client: TestClient) -> None:
    inst = MagicMock()
    mock_hh_cls.return_value = inst
    inst.search_counts_and_candidates.return_value = (
        {"Уровень 1": 0, "Уровень 2": 1, "Уровень 3": 0},
        {"Уровень 1": [], "Уровень 2": [{"id": "1"}], "Уровень 3": []},
        {"Уровень 1": "a", "Уровень 2": "b", "Уровень 3": "c"},
        {"Уровень 1": "u1", "Уровень 2": "u2", "Уровень 3": "u3"},
    )
    r = client.post("/api/export_excel", json=_override_body())
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/vnd.openxmlformats")


@patch("app.api.routes.workflow.build_search_excel_bytes")
def test_api_export_excel_ui_passes_stage_timing_markers(mock_build_excel, client: TestClient) -> None:
    mock_build_excel.return_value = (b"PK\x03\x04", "hh_search_20260405_120000.xlsx")
    body = {
        "request_text": "Python",
        "selected_level": "Уровень 2",
        "queries": {"Уровень 1": "q1", "Уровень 2": "q2", "Уровень 3": "q3"},
        "queries_with_exclusions": {"Уровень 1": "q1", "Уровень 2": "q2", "Уровень 3": "q3"},
        "hh_search_urls": {"Уровень 2": "https://example.com"},
        "found_counts": {"Уровень 1": 0, "Уровень 2": 1, "Уровень 3": 0},
        "candidates_by_level": {"Уровень 2": [{"id": "1", "title": "Dev"}]},
        "started_at": "2026-04-05T12:00:00",
        "bool_finished_at": "2026-04-05T12:00:02",
        "hh_finished_at": "2026-04-05T12:00:05",
        "finished_at": "2026-04-05T12:00:05",
        "ran_traffic_light": False,
    }
    r = client.post("/api/export_excel_ui", json=body)
    assert r.status_code == 200
    assert r.content.startswith(b"PK")
    kwargs = mock_build_excel.call_args.kwargs
    assert kwargs["started_at"].isoformat() == "2026-04-05T12:00:00"
    assert kwargs["bool_finished_at"].isoformat() == "2026-04-05T12:00:02"
    assert kwargs["hh_finished_at"].isoformat() == "2026-04-05T12:00:05"
    assert kwargs["finished_at"].isoformat() == "2026-04-05T12:00:05"
