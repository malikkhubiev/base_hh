from __future__ import annotations

import logging
from typing import Any

from app.clients.hh_client import HHClient
from app.core.tracing import trace_step

logger = logging.getLogger(__name__)


class HHSearchService:
    def __init__(
        self,
        token_url: str,
        token_source: str = "ssp",
    ):
        self.hh = HHClient(token_url=token_url, token_source=token_source)

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

    def _build_search_filters(
        self,
        *,
        source_text: str,
        area_ids: list[int] | None,
    ) -> dict[str, Any]:
        trace_step(
            logger,
            "hh_search",
            "_build_search_filters",
            area_ids=area_ids,
            managerial=self._is_managerial_position(source_text),
        )

        areas = [str(a) for a in (area_ids or [113, 16]) if a is not None]
        if not areas:
            areas = ["113", "16"]

        return {
            "area": areas,
            "age_to": ["45"],
            "job_search_status": ["unknown", "active_search", "looking_for_offers"],
            "experience": ["between3And6", "moreThan6"],
            "period": ["0"],
        }

    def search_counts_and_candidates(
        self,
        query: str,
        *,
        search_plan: list[tuple[str, str]] | None = None,
        search_plan_meta: list[dict[str, Any]] | None = None,
        source_text: str,
        area_ids: list[int] | None,
        per_page: int = 20,
        min_needed: int | None = None,
    ) -> tuple[
        int,
        list[dict[str, Any]],
        str,
        str,
        list[dict[str, Any]],
    ]:
        """
        Returns (internally):
        - found_count
        - candidates (up to min_needed * 3 from a single final boolean query)
        - final_query (last successful query)
        - final_search_url (HH web url for last query)
        - stage_attempts (each attempt includes query_with_exclusion and web_url)
        """
        trace_step(
            logger,
            "hh_search",
            "search_counts_and_candidates.start",
            has_search_plan=bool(search_plan),
            per_page=per_page,
            min_needed=min_needed,
            source_text_preview=(source_text or "")[:300],
        )
        filters = self._build_search_filters(
            source_text=source_text,
            area_ids=area_ids,
        )

        if search_plan:
            ordered_pairs = search_plan
        else:
            ordered_pairs = [("Этап 1", query)]

        last_query = ""
        last_web_url = ""
        last_count = 0
        stage_attempts: list[dict[str, Any]] = []
        min_needed_int = int(min_needed) if min_needed is not None else int(per_page)
        min_needed_int = max(1, min_needed_int)
        target_count = min(200, min_needed_int * 3)
        fetch_per_page = max(target_count, int(per_page))
        main_items: list[dict[str, Any]] = []

        for idx, (stage_name, q) in enumerate(ordered_pairs):
            full_q = q if q is not None else ""
            last_query = full_q
            web_url = self.hh.build_web_search_url(query=full_q, filters=filters, per_page=fetch_per_page)
            last_web_url = web_url

            count, items, _raw = self.hh.search(
                query=full_q,
                filters=filters,
                per_page=fetch_per_page,
                level_name=stage_name,
                iteration=idx,
            )
            last_count = int(count or 0)
            stage_items = items if isinstance(items, list) else []
            stage_collected = len(stage_items)
            main_items = stage_items[:target_count]
            stage_attempts.append(
                {
                    "stage": stage_name,
                    "query": q,
                    "query_with_exclusion": full_q,
                    "found": last_count,
                    "collected": stage_collected,
                    "target": target_count,
                    "enough": stage_collected >= target_count,
                    "web_url": web_url,
                }
            )
            trace_step(
                logger,
                "hh_search",
                "search_counts_and_candidates.level_done",
                level=stage_name,
                found=last_count,
                items_returned=stage_collected,
                target=target_count,
            )
            if stage_collected >= target_count:
                break

        final_count = last_count
        trace_step(
            logger,
            "hh_search",
            "search_counts_and_candidates.complete",
            found_count=final_count,
            collected=len(main_items),
            target=target_count,
        )
        return final_count, main_items, last_query, last_web_url, stage_attempts
