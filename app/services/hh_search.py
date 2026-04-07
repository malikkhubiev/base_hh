from __future__ import annotations

import logging
import re
from typing import Any

from app.clients.hh_client import HHClient
from app.core.tracing import trace_step

logger = logging.getLogger(__name__)


EXCLUSION = "NOT (lead OR лид OR head OR руковод* OR начальн* OR директор OR CTO)"

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
        out = f"({query}) {EXCLUSION}"
        trace_step(logger, "hh_search", "add_exclusion", query_preview=(query or "")[:400], full_length=len(out))
        return out

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

    def _map_professional_roles(self, source_text: str) -> list[str]:
        text = (source_text or "").lower()
        found: list[str] = []
        for role_id, keywords in PROFESSIONAL_ROLE_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                found.append(role_id)
        result = sorted(set(found))
        trace_step(logger, "hh_search", "_map_professional_roles", mapped_role_ids=result)
        return result

    def _build_search_filters(
        self,
        *,
        source_text: str,
        area_id: int | None,
        professional_roles: list[str] | None,
    ) -> dict[str, Any]:
        mapped_roles = self._map_professional_roles(source_text)
        final_roles = professional_roles or mapped_roles or ["96"]
        trace_step(
            logger,
            "hh_search",
            "_build_search_filters",
            area_id=area_id,
            mapped_roles=mapped_roles,
            request_roles=professional_roles,
            final_professional_roles=final_roles,
            managerial=self._is_managerial_position(source_text),
        )

        # Важно: параметр `title` в веб-URL и в API-выдаче HH даёт "плохие" ссылки
        # (и искажает `Перейти/Копировать` в UI). Поэтому не используем `title` вообще.
        return {
            "area": str(area_id) if area_id else ["113"],
            "age_to": ["45"],
            "job_search_status": ["unknown", "active_search", "looking_for_offers"],
            "experience": ["between3And6", "moreThan6"],
            "period": ["0"],
            "professional_roles": final_roles,
        }

    def search_counts_and_candidates(
        self,
        queries: dict[str, str],
        *,
        source_text: str,
        area_id: int | None,
        professional_roles: list[str] | None,
        per_page: int = 20,
    ) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]], dict[str, str], dict[str, str]]:
        """
        Returns:
        - found_counts by level
        - candidates_by_level (up to per_page) by level
        - full_queries_with_exclusions by level
        - hh_web_urls_by_level (same params as API)
        """
        trace_step(
            logger,
            "hh_search",
            "search_counts_and_candidates.start",
            level_keys=list(queries.keys()),
            per_page=per_page,
            source_text_preview=(source_text or "")[:300],
        )
        found_counts: dict[str, int] = {}
        candidates_by_level: dict[str, list[dict[str, Any]]] = {}
        full_queries: dict[str, str] = {}
        web_urls: dict[str, str] = {}
        filters = self._build_search_filters(
            source_text=source_text,
            area_id=area_id,
            professional_roles=professional_roles,
        )

        for level, q in queries.items():
            full_q = self.add_exclusion(q)
            full_queries[level] = full_q
            # Для веб-ссылки используем исходный запрос (без NOT-исключений),
            # чтобы URL совпадал с ожидаемым форматом (валидные "Перейти/Копировать").
            web_urls[level] = self.hh.build_web_search_url(query=q, filters=filters, per_page=per_page)

            count, items = self.hh.search(
                query=full_q,
                filters=filters,
                per_page=per_page,
                level_name=level,
                iteration=0,
            )
            found_counts[level] = int(count or 0)
            candidates_by_level[level] = items if isinstance(items, list) else []
            trace_step(
                logger,
                "hh_search",
                "search_counts_and_candidates.level_done",
                level=level,
                found=found_counts[level],
                items_returned=len(candidates_by_level[level]),
            )

        trace_step(logger, "hh_search", "search_counts_and_candidates.complete", found_counts=found_counts)
        return found_counts, candidates_by_level, full_queries, web_urls

