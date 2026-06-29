from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlencode
from typing import Any

import requests
from requests import Session
from app.core.resume_pdf_store import resume_pdf_exists, save_resume_pdf
from app.core.resume_store import ResumeStore, get_resume_store, persist_resume
from app.core.settings import settings
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
        self.last_request_error: str | None = None
        self._session = self._build_session()

    def _build_session(self) -> Session:
        session = Session()
        http_proxy = (settings.hh_http_proxy or "").strip()
        https_proxy = (settings.hh_https_proxy or "").strip()
        if http_proxy or https_proxy:
            session.proxies = {
                "http": http_proxy or None,
                "https": https_proxy or None,
            }
            session.trust_env = False
        elif settings.hh_trust_env_proxy:
            session.trust_env = True
        else:
            session.trust_env = False
        return session

    def _http_get(self, url: str, **kwargs: Any) -> requests.Response:
        return self._session.get(url, **kwargs)

    def get_token(self) -> str:
        """Получаем API-токен HH из SSP-эндпоинта."""
        trace_step(logger, "hh_client", "get_token.request", token_source=self.token_source, token_url=self.token_url)
        response = self._http_get(self.token_url, timeout=10)
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
    ) -> tuple[int, list[dict[str, Any]], dict[str, Any] | None]:
        """Выполняем поиск резюме и возвращаем найденное, элементы для UI и сырой ответ HH."""
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
            self.last_request_error = None
            response = self._http_get(self.base_url, headers=headers, params=params, timeout=30)
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
                return 0, [], None

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
            return found_count, compact_items, raw_response
        except requests.RequestException as exc:
            self.last_request_error = str(exc)
            trace_step(logger, "hh_client", "search.exception", level_name=level_name, error=self.last_request_error)
            logger.exception("HH search request failed")
            return 0, [], None
        except Exception:
            self.last_request_error = "unexpected HH search error"
            trace_step(logger, "hh_client", "search.exception", level_name=level_name)
            logger.exception("HH search request failed")
            return 0, [], None

    def get_resume_by_id(self, resume_id: str, *, with_contacts: bool = False) -> dict[str, Any] | None:
        """Получаем полную карточку резюме по ID (бесплатно без контактов, платно с контактами)."""
        if with_contacts:
            return self._fetch_resume_with_contacts(resume_id)
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
            response = self._http_get(f"{self.base_url}/{resume_id}", headers=headers, timeout=30)
            if response.status_code == 401:
                trace_step(logger, "hh_client", "get_resume_by_id.retry_401", resume_id=resume_id)
                self.get_token()
                return self.get_resume_by_id(resume_id, with_contacts=False)
            if response.status_code == 200:
                data = response.json()
                trace_step(
                    logger,
                    "hh_client",
                    "get_resume_by_id.ok",
                    resume_id=resume_id,
                    keys=list(data.keys())[:40] if isinstance(data, dict) else None,
                )
                if isinstance(data, dict) and data:
                    persist_resume(resume_id=str(resume_id), resume_json=data)
                return data
            trace_step(logger, "hh_client", "get_resume_by_id.http_error", resume_id=resume_id, status=response.status_code)
            logger.error("Failed to fetch resume id=%s status=%s", resume_id, response.status_code)
            return None
        except Exception:
            trace_step(logger, "hh_client", "get_resume_by_id.exception", resume_id=resume_id)
            logger.exception("Failed to fetch resume by id")
            return None

    def _extract_pdf_download_url(self, resume_data: dict[str, Any]) -> str | None:
        """URL PDF без контактов: actions.download.pdf (не download_with_contact)."""
        actions = resume_data.get("actions")
        if isinstance(actions, dict):
            download = actions.get("download")
            if isinstance(download, dict):
                pdf_info = download.get("pdf")
                if isinstance(pdf_info, dict):
                    url = pdf_info.get("url")
                    if url:
                        return str(url).strip()
        # В сокращённой выдаче HH ссылка может быть только в корневом download.
        download = resume_data.get("download")
        if isinstance(download, dict):
            pdf_info = download.get("pdf")
            if isinstance(pdf_info, dict):
                url = pdf_info.get("url")
                if url:
                    return str(url).strip()
        return None

    def _fetch_resume_for_pdf_url(self, resume_id: str) -> dict[str, Any] | None:
        """Свежий GET /resumes/{id} без with_contact — не из кэша с открытыми контактами."""
        rid = str(resume_id or "").strip()
        if not rid:
            return None
        if not self.token:
            self.get_token()
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = self._http_get(f"{self.base_url}/{rid}", headers=headers, timeout=30)
            if response.status_code == 401:
                self.get_token()
                return self._fetch_resume_for_pdf_url(rid)
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, dict) and data else None
            logger.error("Failed to fetch resume for PDF url id=%s status=%s", rid, response.status_code)
            return None
        except Exception:
            logger.exception("Failed to fetch resume for PDF url id=%s", rid)
            return None

    def download_resume_pdf(self, resume_id: str) -> bool:
        """Скачивает PDF резюме без контактов (actions.download.pdf.url)."""
        rid = str(resume_id or "").strip()
        if not rid:
            return False
        trace_step(logger, "hh_client", "download_resume_pdf.enter", resume_id=rid)
        if resume_pdf_exists(rid):
            trace_step(logger, "hh_client", "download_resume_pdf.cache_hit", resume_id=rid)
            return True

        # Всегда берём свежий JSON без контактов: кэш после open_contacts может
        # содержать download_with_contact или top-level download с контактами.
        data = self._fetch_resume_for_pdf_url(rid)
        if not isinstance(data, dict):
            return False

        pdf_url = self._extract_pdf_download_url(data)
        if not pdf_url:
            trace_step(logger, "hh_client", "download_resume_pdf.no_url", resume_id=rid)
            return False

        if not self.token:
            self.get_token()
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = self._http_get(pdf_url, headers=headers, timeout=60)
            if response.status_code == 401:
                trace_step(logger, "hh_client", "download_resume_pdf.retry_401", resume_id=rid)
                self.get_token()
                return self.download_resume_pdf(rid)
            if response.status_code == 200 and response.content:
                save_resume_pdf(resume_id=rid, content=response.content)
                trace_step(
                    logger,
                    "hh_client",
                    "download_resume_pdf.ok",
                    resume_id=rid,
                    size=len(response.content),
                )
                return True
            trace_step(
                logger,
                "hh_client",
                "download_resume_pdf.http_error",
                resume_id=rid,
                status=response.status_code,
            )
            logger.error("Failed to download resume PDF id=%s status=%s", rid, response.status_code)
            return False
        except Exception:
            trace_step(logger, "hh_client", "download_resume_pdf.exception", resume_id=rid)
            logger.exception("Failed to download resume PDF id=%s", rid)
            return False

    def _fetch_resume_with_contacts(self, resume_id: str) -> dict[str, Any] | None:
        """Платное открытие контактов: GET по URL из actions.get_with_contact.url (токен with_contact)."""
        trace_step(logger, "hh_client", "get_resume_with_contacts.enter", resume_id=resume_id)
        if not self.token:
            self.get_token()
        headers = {"Authorization": f"Bearer {self.token}"}
        base_resume = self.get_resume_by_id(resume_id, with_contacts=False)
        contact_url = f"{self.base_url}/{resume_id}?with_contact=true"
        if isinstance(base_resume, dict):
            actions = base_resume.get("actions")
            if isinstance(actions, dict):
                get_with_contact = actions.get("get_with_contact")
                if isinstance(get_with_contact, dict) and get_with_contact.get("url"):
                    contact_url = str(get_with_contact["url"])
        try:
            response = self._http_get(contact_url, headers=headers, timeout=30)
            if response.status_code == 401:
                self.get_token()
                return self._fetch_resume_with_contacts(resume_id)
            if response.status_code == 200:
                data = response.json()
                trace_step(logger, "hh_client", "get_resume_with_contacts.ok", resume_id=resume_id)
                if isinstance(data, dict) and data:
                    persist_resume(resume_id=str(resume_id), resume_json=data)
                return data
            trace_step(
                logger,
                "hh_client",
                "get_resume_with_contacts.http_error",
                resume_id=resume_id,
                status=response.status_code,
            )
            logger.error("Failed to fetch resume with contacts id=%s status=%s", resume_id, response.status_code)
            return None
        except Exception:
            trace_step(logger, "hh_client", "get_resume_with_contacts.exception", resume_id=resume_id)
            logger.exception("Failed to fetch resume with contacts")
            return None

