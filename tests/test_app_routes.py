from __future__ import annotations

from fastapi.testclient import TestClient


def test_root_ui_ok(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_ui_bot_ok(client: TestClient) -> None:
    r = client.get("/ui/bot")
    assert r.status_code == 200


def test_openapi_json_available(client: TestClient) -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json().get("openapi")
