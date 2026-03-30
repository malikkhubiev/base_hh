from __future__ import annotations

import logging
import re
from typing import Any

from app.clients.hh_client import HHClient

logger = logging.getLogger(__name__)


EXCLUSION = "NOT (lead OR лид OR head OR руковод* OR начальн* OR директор OR CTO)"
NON_MANAGERIAL_TITLE_EXCLUSION = "not (lead and лид and head and руковод* and начальн* and директор and CTO and Arhitect* and Архитект*)"

# Базовый маппинг ключевых слов в professional_roles HH.
PROFESSIONAL_ROLE_KEYWORDS: dict[str, list[str]] = {
    "96": ["python", "backend", "бэкенд", "back-end", "fastapi", "django", "flask", "rest api", "микросервис"],
    "156": [
        "data engineer",
        "инженер данных",
        "etl",
        "elt",
        "dwh",
        "хранилище данных",
        "greenplum",
        "arenadata",
        "airflow",
        "spark",
        "hadoop",
        "kafka",
    ],
    "160": ["data scientist", "ml", "machine learning", "nlp", "cv", "deep learning", "pytorch", "tensorflow"],
    "10": ["analyst", "аналитик", "bi", "product analyst", "data analyst", "sql", "power bi", "tableau"],
    "113": ["devops", "sre", "kubernetes", "docker", "ci/cd", "terraform", "ansible", "prometheus", "grafana"],
}


class HHSearchService:
    def __init__(
        self,
        token_url: str,
        token_source: str = "ssp",
    ):
        self.hh = HHClient(token_url=token_url, token_source=token_source)

    def add_exclusion(self, query: str) -> str:
        return f"({query}) {EXCLUSION}"

    def _is_managerial_position(self, source_text: str) -> bool:
        managerial_markers = (
            "lead",
            "head",
            "руковод",
            "началь",
            "директор",
            "cto",
            "architect",
            "архитект",
        )
        text = source_text.lower()
        return any(marker in text for marker in managerial_markers)

    def _extract_title(self, source_text: str) -> str:
        clean = re.sub(r"\s+", " ", source_text or "").strip()
        # Ограничиваем длину, чтобы параметр title оставался управляемым.
        return clean[:120]

    def _map_professional_roles(self, source_text: str) -> list[str]:
        text = (source_text or "").lower()
        found: list[str] = []
        for role_id, keywords in PROFESSIONAL_ROLE_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                found.append(role_id)
        return sorted(set(found))

    def _build_search_filters(
        self,
        *,
        source_text: str,
        area_id: int | None,
        professional_roles: list[str] | None,
    ) -> dict[str, Any]:
        mapped_roles = self._map_professional_roles(source_text)
        final_roles = professional_roles or mapped_roles or ["96"]
        title = self._extract_title(source_text)
        is_managerial = self._is_managerial_position(source_text)
        if title and not is_managerial:
            title = f"{title} {NON_MANAGERIAL_TITLE_EXCLUSION}"

        return {
            "area": str(area_id) if area_id else ["113"],
            "age_to": ["45"],
            "job_search_status": ["unknown", "active_search", "looking_for_offers"],
            "experience": ["between3And6", "moreThan6"],
            "period": ["0"],
            "professional_roles": final_roles,
            "title": title,
        }

    def search_counts_and_candidates(
        self,
        queries: dict[str, str],
        *,
        source_text: str,
        area_id: int | None,
        professional_roles: list[str] | None,
        per_page: int = 20,
    ) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]], dict[str, str]]:
        """
        Returns:
        - found_counts by level
        - candidates_by_level (up to per_page) by level
        - full_queries_with_exclusions by level
        """
        found_counts: dict[str, int] = {}
        candidates_by_level: dict[str, list[dict[str, Any]]] = {}
        full_queries: dict[str, str] = {}
        filters = self._build_search_filters(
            source_text=source_text,
            area_id=area_id,
            professional_roles=professional_roles,
        )

        for level, q in queries.items():
            full_q = self.add_exclusion(q)
            full_queries[level] = full_q

            count, items = self.hh.search(
                query=full_q,
                filters=filters,
                per_page=per_page,
                level_name=level,
                iteration=0,
            )
            found_counts[level] = int(count or 0)
            candidates_by_level[level] = items if isinstance(items, list) else []

        return found_counts, candidates_by_level, full_queries

