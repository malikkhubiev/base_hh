from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


@patch("app.api.routes.chat_bot_api.service")
def test_webhook_subscription_list_mocked(mock_service, client: TestClient) -> None:
    mock_service.hh.get_webhook_subscriptions.return_value = [{"id": "s1"}]
    r = client.get("/api/chat_bot/webhook/subscription/list")
    assert r.status_code == 200
    assert r.json()["subscriptions"] == [{"id": "s1"}]


@patch("app.api.routes.chat_bot_api.service")
def test_webhook_subscription_create_mocked(mock_service, client: TestClient) -> None:
    mock_service.hh.post_webhook_subscription.return_value = {"id": "new"}
    r = client.post(
        "/api/chat_bot/webhook/subscription/create",
        json={"callback_url": "https://example.com/hook"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
