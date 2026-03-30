from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests
from app.core.log_store import LogStore, get_log_store

logger = logging.getLogger(__name__)


class HHClient:
    """Клиент HH API для получения токена и поиска резюме."""

    def __init__(
        self,
        token_url: str = "http://int-srv:8085/metrics/hh/accessToken",
        token_source: str = "ssp",
        log_store: LogStore | None = None,
    ) -> None:
        self.token_url = token_url
        self.token: str | None = None
        self.base_url = "https://api.hh.ru/resumes"
        self.token_source = token_source
        self.log_store = log_store or get_log_store()

    def get_token(self) -> str:
        """Получаем API-токен HH из SSP-эндпоинта."""
        response = requests.get(self.token_url, timeout=10)
        response.raise_for_status()
        self.token = response.content.decode("utf-8")
        logger.info("HH token received from SSP source: %s", self.token_source)
        return self.token

    def _build_api_params(self, query: str, filters: dict[str, Any] | None, per_page: int) -> dict[str, Any]:
        f = filters or {}
        params: dict[str, Any] = {
            "text": query,
            "area": f.get("area", ["113"]),
            "age_to": f.get("age_to", ["45"]),
            "experience": f.get("experience", ["between3And6", "moreThan6"]),
            "job_search_status": f.get("job_search_status", ["unknown", "active_search", "looking_for_offers"]),
            "period": f.get("period", ["0"]),
            "per_page": per_page,
        }
        title = f.get("title")
        if title:
            params["title"] = title
        professional_roles = f.get("professional_roles")
        if professional_roles:
            params["professional_role"] = professional_roles
        return params

    def _api_to_url_params(self, api_params: dict[str, Any]) -> dict[str, Any]:
        url_params = dict(api_params)
        if "period" in url_params:
            url_params["search_period"] = url_params.pop("period")
        if "per_page" in url_params:
            url_params["items_on_page"] = url_params.pop("per_page")
        return url_params

    def _compact_items(self, items_list: list[Any]) -> list[dict[str, Any]]:
        compact: list[dict[str, Any]] = []
        for item in items_list or []:
            if not isinstance(item, dict):
                continue

            experience_obj = item.get("experience")
            compact_experience: dict[str, Any] | None = None
            if isinstance(experience_obj, dict):
                compact_experience = {
                    "months": experience_obj.get("total_months"),
                    "text": experience_obj.get("text"),
                }

            compact.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "alternate_url": item.get("alternate_url"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                    "age": item.get("age"),
                    "experience": compact_experience if compact_experience is not None else None,
                    "salary": item.get("salary"),
                    "gender": item.get("gender"),
                    "citizenship": item.get("citizenship"),
                    "work_ticket": item.get("work_ticket"),
                    "relocation": item.get("relocation"),
                    "has_photo": item.get("has_photo"),
                    "is_archived": item.get("is_archived"),
                    "can_edit": item.get("can_edit"),
                    "area": item.get("area"),
                    "employer": item.get("employer"),
                    "tags": item.get("tags", []),
                    "skills": item.get("skills", [])[:10] if isinstance(item.get("skills"), list) else [],
                    # Keep for UI normalization fallbacks.
                    "first_name": item.get("first_name"),
                    "last_name": item.get("last_name"),
                }
            )
        return compact

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        per_page: int = 20,
        level_name: str = "",
        iteration: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        """Выполняем поиск резюме и возвращаем найденное и элементы для UI."""
        if not self.token:
            self.get_token()
        headers = {"Authorization": f"Bearer {self.token}"}
        params = self._build_api_params(query=query, filters=filters, per_page=per_page)
        url_params = self._api_to_url_params(params)
        try:
            logger.info("HH search started, level=%s", level_name)
            logger.info("HH search query=%s", query[:200])
            logger.info("HH API params=%s", json.dumps(params, ensure_ascii=False))
            response = requests.get(self.base_url, headers=headers, params=params, timeout=30)
            logger.info("HH response status=%s", response.status_code)

            if response.status_code == 401:
                logger.warning("HH token expired, refreshing token and retrying request")
                self.get_token()
                return self.search(query, filters, per_page, level_name, iteration)
            if response.status_code != 200:
                logger.error("HH API error status=%s body=%s", response.status_code, response.text[:500])
                return 0, []

            raw_response = response.json()
            logger.info("HH response keys=%s", list(raw_response.keys()))
            logger.info("HH found=%s", raw_response.get("found", 0))
            logger.debug("HH URL params (web mapping)=%s", json.dumps(url_params, ensure_ascii=False))

            found_count = int(raw_response.get("found", 0) or 0)
            items_list = raw_response.get("items", [])
            compact_items = self._compact_items(items_list)

            # Persist in DB instead of writing JSON files.
            try:
                self.log_store.save_hh_search_run(
                    level_name=level_name,
                    query=query,
                    iteration=iteration,
                    found_count=found_count,
                    items=compact_items,
                )
            except Exception:
                # DB must not break the core functionality.
                logger.exception("Failed to persist HH search run to DB")

            return found_count, compact_items
        except Exception:
            logger.exception("HH search request failed")
            return 0, []

    def get_resume_by_id(self, resume_id: str) -> dict[str, Any] | None:
        """Получаем полную карточку резюме по ID."""
        if not self.token:
            self.get_token()
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(f"{self.base_url}/{resume_id}", headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            logger.error("Failed to fetch resume id=%s status=%s", resume_id, response.status_code)
            return None
        except Exception:
            logger.exception("Failed to fetch resume by id")
            return None

