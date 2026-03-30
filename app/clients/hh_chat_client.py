from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

import requests

from app.core.log_store import get_log_store
from app.core.settings import settings

logger = logging.getLogger(__name__)


class HHChatClient:
    """
    HH API client for chat + webhook subscription management.

    Note: HH API base for chats is https://api.hh.ru (not the /resumes sub-path).
    """

    def __init__(
        self,
        *,
        token_url: str | None = None,
        token_source: str | None = None,
    ) -> None:
        self.token_url = token_url or settings.hh_token_url
        self.token_source = token_source or settings.token_source
        self.token: str | None = None

        # HH host for chat endpoints.
        self.base_url = "https://api.hh.ru"
        self.log_store = get_log_store()

    def get_token(self) -> str:
        if self.token:
            return self.token

        response = requests.get(self.token_url, timeout=10)
        response.raise_for_status()
        self.token = response.content.decode("utf-8")
        logger.info("HH token received from SSP source: %s", self.token_source)
        return self.token

    def _headers(self) -> dict[str, str]:
        token = self.get_token()
        return {"Authorization": f"Bearer {token}"}

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None):
        url = f"{self.base_url}{path}"
        headers = self._headers()
        # Use a slightly larger timeout for chat polling.
        timeout_s = 45 if method.upper() == "GET" else 30
        resp = requests.request(method, url, headers=headers, params=params, json=json, timeout=timeout_s)
        return resp

    def get_common_chat_list(
        self,
        *,
        page: int = 0,
        per_page: int = 20,
        filter_unread: bool | None = None,
        filter_has_text_message: bool | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": int(page), "per_page": int(per_page)}
        if filter_unread is not None:
            params["filter_unread"] = bool(filter_unread)
        if filter_has_text_message is not None:
            params["filter_has_text_message"] = bool(filter_has_text_message)

        resp = self._request("GET", "/common/chats", params=params)
        if resp.status_code == 401:
            # Token might be stale.
            self.token = None
            resp = self._request("GET", "/common/chats", params=params)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def unread_chats_count(self) -> dict[str, Any]:
        resp = self._request("GET", "/common/chats/counters/unread")
        if resp.status_code == 401:
            self.token = None
            resp = self._request("GET", "/common/chats/counters/unread")
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def get_chat_messages(
        self,
        *,
        chat_id: str,
        start_message_id: str | None = None,
        limit: int = 10,
        order: str = "prev",
    ) -> dict[str, Any]:
        if order not in ("prev", "next"):
            raise ValueError("order must be prev|next")

        params: dict[str, Any] = {"limit": int(limit), "order": order}
        if start_message_id:
            params["start_message_id"] = str(start_message_id)

        resp = self._request("GET", f"/common/chats/{chat_id}/messages", params=params)
        if resp.status_code == 401:
            self.token = None
            resp = self._request("GET", f"/common/chats/{chat_id}/messages", params=params)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def chat_message_post(self, *, chat_id: str, text: str, idempotency_key: str | None = None) -> dict[str, Any]:
        if not text:
            raise ValueError("text must be non-empty")
        idempotency_key = idempotency_key or str(uuid4())
        payload = {"idempotency_key": idempotency_key, "text": text}

        resp = self._request("POST", f"/common/chats/{chat_id}/messages", json=payload)
        if resp.status_code == 401:
            self.token = None
            resp = self._request("POST", f"/common/chats/{chat_id}/messages", json=payload)

        # HH returns 409 Conflict for duplicate idempotency_key. Treat it as success.
        if resp.status_code not in (200, 201, 409):
            resp.raise_for_status()
        return resp.json() if resp.content else {"status": resp.status_code}

    def get_or_create_chat_without_vacancy_common(self, *, resume_hash: str, first_message: str) -> dict[str, Any]:
        payload = {"resume_hash": resume_hash, "first_message": first_message}
        resp = self._request("POST", "/common/chats/without_vacancy", json=payload)
        if resp.status_code == 401:
            self.token = None
            resp = self._request("POST", "/common/chats/without_vacancy", json=payload)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    # Webhook API
    def post_webhook_subscription(self, *, url: str, action_types: list[str]) -> dict[str, Any]:
        # Schema: { url, actions: [{type: ...}] }
        payload = {"url": url, "actions": [{"type": t} for t in action_types]}
        resp = self._request("POST", "/webhook/subscriptions", json=payload)
        if resp.status_code == 401:
            self.token = None
            resp = self._request("POST", "/webhook/subscriptions", json=payload)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def get_webhook_subscriptions(self) -> dict[str, Any]:
        resp = self._request("GET", "/webhook/subscriptions")
        if resp.status_code == 401:
            self.token = None
            resp = self._request("GET", "/webhook/subscriptions")
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def cancel_webhook_subscription(self, *, subscription_id: str) -> None:
        resp = self._request("DELETE", f"/webhook/subscriptions/{subscription_id}")
        if resp.status_code == 401:
            self.token = None
            resp = self._request("DELETE", f"/webhook/subscriptions/{subscription_id}")

        # 204 expected.
        if resp.status_code not in (204, 200):
            resp.raise_for_status()
        return

