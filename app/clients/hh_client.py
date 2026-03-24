from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from app.utils.file_manager import FileManager

logger = logging.getLogger(__name__)


class HHClient:
    """Client for HH API token retrieval and resume search."""

    def __init__(
        self,
        token_url: str = "http://int-srv:8085/metrics/hh/accessToken",
        file_manager: FileManager | None = None,
        token_source: str = "ssp_soft",
        oauth_token_url: str = "https://hh.ru/oauth/token",
        base_client_id: str | None = None,
        base_client_secret: str | None = None,
    ) -> None:
        self.token_url = token_url
        self.token: str | None = None
        self.base_url = "https://api.hh.ru/resumes"
        self.fm = file_manager
        self.search_counter = 0
        self.token_source = token_source
        self.oauth_token_url = oauth_token_url
        self.base_client_id = base_client_id
        self.base_client_secret = base_client_secret

    def get_token(self) -> str:
        """Retrieve API token from configured source."""
        if self.token_source == "base":
            if not self.base_client_id or not self.base_client_secret:
                raise ValueError("BASE credentials are empty")
            response = requests.post(
                self.oauth_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.base_client_id,
                    "client_secret": self.base_client_secret,
                },
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            token = payload.get("access_token")
            if not token:
                raise ValueError(f"No access_token in OAuth response: {payload}")
            self.token = token
            logger.info("HH token received from OAuth source")
            return self.token

        response = requests.get(self.token_url, timeout=10)
        response.raise_for_status()
        self.token = response.content.decode("utf-8")
        logger.info("HH token received from SSP source")
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

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        per_page: int = 20,
        save_results: bool = True,
        level_name: str = "",
        iteration: int = 0,
    ) -> int:
        """Search resumes and return HH found count."""
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
                return self.search(query, filters, per_page, save_results, level_name, iteration)
            if response.status_code != 200:
                logger.error("HH API error status=%s body=%s", response.status_code, response.text[:500])
                return 0

            raw_response = response.json()
            logger.info("HH response keys=%s", list(raw_response.keys()))
            logger.info("HH found=%s", raw_response.get("found", 0))
            logger.debug("HH URL params (web mapping)=%s", json.dumps(url_params, ensure_ascii=False))

            if self.fm:
                raw_name = f'raw_hh_response_{level_name.replace(" ", "_")}_iter{iteration + 1}.json'
                self.fm.save_json(raw_name, raw_response)
                logger.info("Saved raw HH response: %s", raw_name)

            found_count = int(raw_response.get("found", 0) or 0)
            if save_results and found_count > 0:
                saved_file = self._save_search_results(query, raw_response, found_count, level_name, iteration)
                if saved_file:
                    logger.info("Saved formatted HH result file: %s", saved_file)
            elif save_results:
                logger.info("No HH results found, skip formatted file creation")
            return found_count
        except Exception:
            logger.exception("HH search request failed")
            return 0

    def _save_search_results(
        self,
        query: str,
        data: dict[str, Any],
        found_count: int,
        level_name: str = "",
        iteration: int = 0,
    ) -> str | None:
        """Save compact result metadata to logs directory."""
        try:
            self.search_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_query = query[:50].replace(" ", "_").replace("(", "").replace(")", "")
            clean_query = clean_query.replace("AND", "").replace("OR", "").replace("NOT", "")
            clean_query = re.sub(r"[^\w\-_\.]", "", clean_query)[:30]

            if level_name:
                clean_level = level_name.replace(" ", "_").replace("Уровень", "L")
                filename = f"hh_search_iter{iteration + 1}_{clean_level}_{clean_query}_{timestamp}.json"
            else:
                filename = f"hh_search_{self.search_counter}_{clean_query}_{timestamp}.json"

            items_list = data.get("items", [])
            if not isinstance(items_list, list):
                logger.warning("HH items field has invalid type: %s", type(items_list))
                items_list = []

            search_data = {
                "search_info": {
                    "timestamp": timestamp,
                    "query": query,
                    "level": level_name,
                    "iteration": iteration + 1 if iteration else None,
                    "total_found": found_count,
                    "returned_count": len(items_list),
                },
                "items": [],
            }

            for item in items_list:
                if not isinstance(item, dict):
                    continue
                search_data["items"].append(
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "alternate_url": item.get("alternate_url"),
                        "created_at": item.get("created_at"),
                        "updated_at": item.get("updated_at"),
                        "age": item.get("age"),
                        "experience": {
                            "months": item.get("experience", {}).get("total_months")
                            if isinstance(item.get("experience"), dict)
                            else None,
                            "text": item.get("experience", {}).get("text")
                            if isinstance(item.get("experience"), dict)
                            else None,
                        }
                        if item.get("experience")
                        else None,
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
                    }
                )

            if self.fm:
                return self.fm.save_json(filename, search_data)

            Path("logs").mkdir(exist_ok=True)
            filepath = Path("logs") / filename
            filepath.write_text(json.dumps(search_data, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(filepath)
        except Exception:
            logger.exception("Failed to save HH search results")
            return None

    def get_resume_by_id(self, resume_id: str) -> dict[str, Any] | None:
        """Fetch full resume details by resume ID."""
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

