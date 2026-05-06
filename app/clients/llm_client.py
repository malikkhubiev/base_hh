from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests
from requests import Response

from app.core.tracing import trace_step

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for sending prompt text to internal LLM endpoint."""

    def __init__(self, llm_url: str = "http://int-srv:8085/metrics/ecm/gpt", token_param: str = "?token=DebugEcmTest"):
        self.llm_url = llm_url
        self.token_param = token_param

    def _should_retry(self, response: Response | None, exc: Exception | None) -> bool:
        # Retry network errors and server-side errors from LLM.
        if exc is not None:
            return True
        if response is None:
            return True
        # Retry typical transient statuses.
        return response.status_code >= 500 or response.status_code in (408, 409, 429)

    def call(self, prompt_text: str, model="ChatGPT\\gpt-4o-mini", iteration: int | None = None, temperature: float = 0.0) -> dict[str, Any] | None:
        """Send request to LLM and return parsed JSON payload."""
        request_data = {
            "requestUser": "system",
            "promptName": "HH Search Optimizer",
            "promptModel": model,
            "promptText": prompt_text,
            "temperature": str(temperature),
        }
        iteration_label = iteration + 1 if iteration is not None else "n/a"
        trace_step(
            logger,
            "llm_client",
            "call.start",
            iteration=iteration_label,
            model=model,
            prompt_len=len(prompt_text or ""),
            temperature=temperature,
        )
        max_attempts = 10
        delay_s = 1.0

        last_exc: Exception | None = None
        last_response: Response | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                trace_step(logger, "llm_client", "call.attempt", attempt=attempt, delay_s=0 if attempt == 1 else delay_s)
                logger.info("Sending LLM request, iteration=%s, attempt=%s/%s", iteration_label, attempt, max_attempts)
                if attempt > 1:
                    time.sleep(delay_s)

                response = requests.post(
                    self.llm_url + self.token_param,
                    json=request_data,
                    headers={"Content-Type": "application/json"},
                    timeout=60,
                )
                last_response = response
                response.raise_for_status()
                llm_response = response.json()
                logger.info("Received LLM response, keys=%s", list(llm_response.keys()))
                trace_step(logger, "llm_client", "call.ok", response_keys=list(llm_response.keys()), attempt=attempt)
                return llm_response
            except Exception as exc:
                last_exc = exc
                retry = self._should_retry(last_response, exc)
                status_code = getattr(last_response, "status_code", None)
                trace_step(
                    logger,
                    "llm_client",
                    "call.failed",
                    attempt=attempt,
                    status_code=status_code,
                    will_retry=retry and attempt < max_attempts,
                )
                logger.exception(
                    "LLM request failed (attempt %s/%s, status=%s)",
                    attempt,
                    max_attempts,
                    status_code,
                )
                if not retry or attempt >= max_attempts:
                    return None
                delay_s = min(delay_s * 2.0, 60.0)

        # Should be unreachable, but keep the old shape (None on failure).
        _ = last_exc
        return None

    def extract_queries(self, llm_response: dict[str, Any]) -> dict[str, str] | None:
        """Extract three level queries from possible LLM response shapes."""
        trace_step(logger, "llm_client", "extract_queries.enter", top_keys=list(llm_response.keys()))
        queries: dict[str, Any] | None = None
        response_text = llm_response.get("response")
        if isinstance(response_text, str):
            queries = self._parse_json_from_text(response_text)

        if not queries:
            queries = self._extract_from_object(llm_response)

        if not queries and isinstance(response_text, str):
            matches = re.findall(r'\{[^{}]*"Уровень\s*\d+"[^{}]*\}', response_text)
            for match in matches:
                try:
                    data = json.loads(match)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict):
                    queries = data.get("markdown") if isinstance(data.get("markdown"), dict) else data
                    if queries:
                        break

        if not isinstance(queries, dict):
            trace_step(logger, "llm_client", "extract_queries.not_dict", queries_type=type(queries).__name__)
            logger.error("Unable to extract level queries from LLM response")
            return None

        normalized: dict[str, str] = {}
        for key, value in queries.items():
            normalized[str(key)] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        logger.info("Extracted level queries: %s", list(normalized.keys()))
        trace_step(logger, "llm_client", "extract_queries.ok", keys=list(normalized.keys()))
        return normalized

    def _parse_json_from_text(self, text: str) -> dict[str, Any] | None:
        patterns = [
            r'\{[^{}]*"[Уровень\s\d]+"[^{}]*\}',
            r'\{[^{}]*"markdown"[^{}]*\{[^{}]*"[Уровень\s\d]+"[^{}]*\}[^{}]*\}',
            r"\{.*\}",
        ]
        for pattern in patterns:
            json_match = re.search(pattern, text, re.DOTALL)
            if not json_match:
                continue
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                markdown = data.get("markdown")
                if isinstance(markdown, dict):
                    return markdown
                if any(str(key).startswith("Уровень") for key in data.keys()):
                    return data
        return None

    def _extract_from_object(self, obj: dict[str, Any]) -> dict[str, Any] | None:
        if all(k in obj for k in ["Уровень 1", "Уровень 2", "Уровень 3"]):
            return obj
        markdown = obj.get("markdown")
        if isinstance(markdown, dict):
            return markdown
        for value in obj.values():
            if isinstance(value, dict):
                result = self._extract_from_object(value)
                if result:
                    return result
        return None

