from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlencode
from typing import Any

import requests
from app.core.resume_store import ResumeStore, get_resume_store
from app.core.tracing import trace_step

logger = logging.getLogger(__name__)


class HHClient:
    """Клиент HH API для получения токена и поиска резюме."""

    def __init__(
        self,
        token_url: str = "http://int-srv:8085/metrics/hh/accessToken",
        token_source: str = "ssp",
        resume_store: ResumeStore | None = None,
    ) -> None:
        self.token_url = token_url
        self.token: str | None = None
        self.base_url = "https://api.hh.ru/resumes"
        self.token_source = token_source
        self.resume_store = resume_store or get_resume_store()

    def get_token(self) -> str:
        """Получаем API-токен HH из SSP-эндпоинта."""
        trace_step(logger, "hh_client", "get_token.request", token_source=self.token_source, token_url=self.token_url)
        response = requests.get(self.token_url, timeout=10)
        response.raise_for_status()
        self.token = response.content.decode("utf-8")
        logger.info("HH token received from SSP source: %s", self.token_source)
        trace_step(logger, "hh_client", "get_token.ok", token_length=len(self.token or ""))
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
        return params

    def _api_to_url_params(self, api_params: dict[str, Any]) -> dict[str, Any]:
        url_params = dict(api_params)
        if "period" in url_params:
            url_params["search_period"] = url_params.pop("period")
        if "per_page" in url_params:
            url_params["items_on_page"] = url_params.pop("per_page")
        return url_params

    def build_web_search_url(
        self,
        *,
        query: str,
        filters: dict[str, Any] | None = None,
        per_page: int = 20,
        base_url: str = "https://tomsk.hh.ru/search/resume",
    ) -> str:
        """
        Строит URL для веб-поиска HH в "человеческом" формате (как в UI HH),
        чтобы действия "Перейти" и "Копировать" давали корректную ссылку.
        """
        f = filters or {}
        url_params: dict[str, Any] = {
            "text": query,
            "area": f.get("area", ["113"]),
            "isDefaultArea": "true",
            "pos": "full_text",
            "logic": "normal",
            "exp_period": "all_time",
            "ored_clusters": "true",
            "order_by": "relevance",
            "search_period": f.get("period", ["0"]),
            "age_to": f.get("age_to", ["45"]),
            "job_search_status": f.get("job_search_status", ["unknown", "active_search", "looking_for_offers"]),
            "experience": f.get("experience", ["between3And6", "moreThan6"]),
            "hhtmFrom": "resume_search_result",
            "hhtmFromLabel": "resume_search_line",
        }
        qs = urlencode(url_params, doseq=True)
        return f"{base_url}?{qs}"

    def _compact_items(self, items_list: list[Any]) -> list[dict[str, Any]]:
        compact: list[dict[str, Any]] = []
        for item in items_list or []:
            if not isinstance(item, dict):
                continue

            experience_obj = item.get("experience")
            compact_experience: dict[str, Any] | None = None
            experience_full: list[dict[str, Any]] | None = None
            if isinstance(experience_obj, dict):
                compact_experience = {
                    "months": experience_obj.get("total_months"),
                    "text": experience_obj.get("text"),
                }
            elif isinstance(experience_obj, list):
                # If HH search already includes full experience list, pass it through.
                experience_full = [x for x in experience_obj if isinstance(x, dict)]

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
                    "experience_full": experience_full,
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
        trace_step(
            logger,
            "hh_client",
            "search.enter",
            level_name=level_name,
            iteration=iteration,
            per_page=per_page,
            has_token=bool(self.token),
        )
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
                trace_step(logger, "hh_client", "search.retry_401", level_name=level_name, iteration=iteration)
                logger.warning("HH token expired, refreshing token and retrying request")
                self.get_token()
                return self.search(query, filters, per_page, level_name, iteration)
            if response.status_code != 200:
                trace_step(
                    logger,
                    "hh_client",
                    "search.http_error",
                    status=response.status_code,
                    body_preview=response.text[:500],
                )
                logger.error("HH API error status=%s body=%s", response.status_code, response.text[:500])
                return 0, []

            raw_response = response.json()
            logger.info("HH response keys=%s", list(raw_response.keys()))
            logger.info("HH found=%s", raw_response.get("found", 0))
            logger.debug("HH URL params (web mapping)=%s", json.dumps(url_params, ensure_ascii=False))

            found_count = int(raw_response.get("found", 0) or 0)
            items_list = raw_response.get("items", [])
            compact_items = self._compact_items(items_list)

            trace_step(
                logger,
                "hh_client",
                "search.success",
                level_name=level_name,
                found_count=found_count,
                items=len(compact_items),
            )
            return found_count, compact_items
        except Exception:
            trace_step(logger, "hh_client", "search.exception", level_name=level_name)
            logger.exception("HH search request failed")
            return 0, []

    def get_resume_by_id(self, resume_id: str) -> dict[str, Any] | None:
        """Получаем полную карточку резюме по ID."""
        trace_step(logger, "hh_client", "get_resume_by_id.enter", resume_id=resume_id)
        if not self.token:
            self.get_token()
        # Resume cache: if we already fetched this resume, return cached JSON.
        try:
            cached = self.resume_store.get_resume_json(resume_id=str(resume_id))
        except Exception:
            cached = None
        if isinstance(cached, dict) and cached:
            trace_step(logger, "hh_client", "get_resume_by_id.cache_hit", resume_id=resume_id)
            return cached
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(f"{self.base_url}/{resume_id}", headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                trace_step(
                    logger,
                    "hh_client",
                    "get_resume_by_id.ok",
                    resume_id=resume_id,
                    keys=list(data.keys())[:40] if isinstance(data, dict) else None,
                )
                return data
            trace_step(logger, "hh_client", "get_resume_by_id.http_error", resume_id=resume_id, status=response.status_code)
            logger.error("Failed to fetch resume id=%s status=%s", resume_id, response.status_code)
            return None
        except Exception:
            trace_step(logger, "hh_client", "get_resume_by_id.exception", resume_id=resume_id)
            logger.exception("Failed to fetch resume by id")
            return None

