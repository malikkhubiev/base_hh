from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.clients.hh_client import HHClient
from app.utils.file_manager import FileManager

logger = logging.getLogger(__name__)


EXCLUSION = "NOT (lead OR лид OR head OR руковод* OR начальн* OR директор OR CTO)"
NON_MANAGERIAL_TITLE_EXCLUSION = "not (lead and лид and head and руковод* and начальн* and директор and CTO and Arhitect* and Архитект*)"

# Minimal keyword-based mapping to HH professional_roles ids.
PROFESSIONAL_ROLE_KEYWORDS: dict[str, list[str]] = {
    "96": ["python", "backend", "бэкенд", "fastapi", "django", "flask"],
    "156": ["data engineer", "инженер данных", "etl", "dwh", "greenplum", "arenadata", "airflow"],
    "160": ["data scientist", "ml", "machine learning", "nlp", "cv", "deep learning"],
    "10": ["analyst", "аналитик", "bi", "product analyst", "data analyst"],
    "113": ["devops", "sre", "kubernetes", "docker", "ci/cd"],
}


class HHSearchService:
    def __init__(
        self,
        token_url: str,
        token_source: str = "ssp_soft",
        oauth_token_url: str = "https://hh.ru/oauth/token",
        base_client_id: str | None = None,
        base_client_secret: str | None = None,
        txt_folder: str = "txt",
        output_folder: str = "logs",
    ):
        self.fm = FileManager(txt_folder=txt_folder, output_folder=output_folder)
        self.hh = HHClient(
            token_url=token_url,
            file_manager=self.fm,
            token_source=token_source,
            oauth_token_url=oauth_token_url,
            base_client_id=base_client_id,
            base_client_secret=base_client_secret,
        )

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
        # Keep title reasonably compact for HH `title` filter.
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
        mock: bool = False,
    ) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]], dict[str, str]]:
        """
        Returns:
        - found_counts by level
        - candidates_by_level (up to per_page) by level
        - full_queries_with_exclusions by level
        """
        if mock:
            logger.info("Using mock HH data from logs")
            return self._mock_from_logs(), {k: v for k, v in self._mock_from_logs_candidates().items()}, {
                level: self.add_exclusion(q) for level, q in queries.items()
            }

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

            count = self.hh.search(
                query=full_q,
                filters=filters,
                per_page=per_page,
                save_results=True,
                level_name=level,
                iteration=0,
            )
            found_counts[level] = int(count or 0)

            # If results saved, they are in logs/ as generated by HHClient.
            # But for UI we also need returned items; easiest is to re-read last raw response.
            raw_path = Path(self.fm.output_folder) / f"raw_hh_response_{level.replace(' ', '_')}_iter1.json"
            if raw_path.exists():
                try:
                    raw = json.loads(raw_path.read_text(encoding="utf-8"))
                    items = raw.get("items") if isinstance(raw, dict) else None
                    candidates_by_level[level] = items if isinstance(items, list) else []
                except Exception:
                    candidates_by_level[level] = []
            else:
                candidates_by_level[level] = []

        return found_counts, candidates_by_level, full_queries

    def _mock_from_logs(self) -> dict[str, int]:
        path = Path("logs") / "iteration_results_iter1_20260324_120612.json"
        if not path.exists():
            return {"Уровень 1": 0, "Уровень 2": 0, "Уровень 3": 0}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("results", {"Уровень 1": 0, "Уровень 2": 0, "Уровень 3": 0})

    def _mock_from_logs_candidates(self) -> dict[str, list[dict[str, Any]]]:
        # Use one saved formatted result as sample for all levels.
        # (We can extend later to distinct files per level.)
        sample = next(Path("logs").glob("hh_search_iter1_L_1_*.json"), None)
        if not sample:
            return {"Уровень 1": [], "Уровень 2": [], "Уровень 3": []}
        data = json.loads(sample.read_text(encoding="utf-8"))
        items = data.get("items", [])
        return {"Уровень 1": items, "Уровень 2": items, "Уровень 3": items}

