from __future__ import annotations

import logging
import re
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
        area_id: int | None,
    ) -> dict[str, Any]:
        trace_step(
            logger,
            "hh_search",
            "_build_search_filters",
            area_id=area_id,
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
        }

    def search_counts_and_candidates(
        self,
        queries: dict[str, str],
        *,
        search_plan: list[tuple[str, str]] | None = None,
        search_plan_meta: list[dict[str, Any]] | None = None,
        source_text: str,
        area_id: int | None,
        per_page: int = 20,
        min_needed: int | None = None,
        max_stage_attempts: int | None = None,
    ) -> tuple[
        dict[str, int],
        dict[str, list[dict[str, Any]]],
        dict[str, str],
        dict[str, str],
        str,
        list[dict[str, Any]],
    ]:
        """
        Returns (internally):
        - found_counts by level (currently only 'Основной' is used)
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
            min_needed=min_needed,
            source_text_preview=(source_text or "")[:300],
        )
        found_counts: dict[str, int] = {}
        candidates_by_level: dict[str, list[dict[str, Any]]] = {}
        full_queries: dict[str, str] = {}
        web_urls: dict[str, str] = {}
        filters = self._build_search_filters(
            source_text=source_text,
            area_id=area_id,
        )

        if search_plan:
            ordered_pairs = search_plan
        else:
            ordered_pairs = list(queries.items())

        collected: list[dict[str, Any]] = []
        collected_ids: set[str] = set()
        last_query = ""
        last_web_url = ""
        last_count = 0
        used_stage_name = ""
        stage_attempts: list[dict[str, Any]] = []
        min_needed_int = int(min_needed) if min_needed is not None else int(per_page)
        min_needed_int = max(1, min_needed_int)
        show_limit = max(min_needed_int, int(per_page))
        for idx, (stage_name, q) in enumerate(ordered_pairs):
            if max_stage_attempts is not None and len(stage_attempts) >= max_stage_attempts:
                break
            if not q:
                continue
            full_q = q
            last_query = full_q
            web_url = self.hh.build_web_search_url(query=q, filters=filters, per_page=show_limit)
            last_web_url = web_url

            count, items = self.hh.search(
                query=full_q,
                filters=filters,
                per_page=show_limit,
                level_name=stage_name,
                iteration=idx,
            )
            last_count = int(count or 0)
            used_stage_name = stage_name
            stage_items = items if isinstance(items, list) else []
            for item in stage_items:
                cid = str(item.get("id") or "")
                if not cid or cid in collected_ids:
                    continue
                collected_ids.add(cid)
                collected.append(item)
                if len(collected) >= show_limit:
                    break
            stage_attempts.append(
                {
                    "stage": stage_name,
                    "query": q,
                    "query_with_exclusion": full_q,
                    "found": last_count,
                    "collected": len(collected),
                    "target": min_needed_int,
                    "enough": len(collected) >= min_needed_int,
                    "web_url": web_url,
                }
            )
            trace_step(
                logger,
                "hh_search",
                "search_counts_and_candidates.level_done",
                level=stage_name,
                found=last_count,
                items_returned=len(stage_items),
                collected=len(collected),
            )
            # Стоп-условие: как только набрали минимум — не продолжаем "ослабления" (удаление пункта булевого запроса).
            if len(collected) >= min_needed_int:
                break

        main_items = collected[:show_limit]
        candidates_by_level = {
            "Основной": main_items,
        }
        final_count = last_count
        found_counts = {
            "Основной": final_count,
        }
        full_queries = {
            "Основной": last_query,
        }
        web_urls = {
            "Основной": last_web_url,
        }
        trace_step(logger, "hh_search", "search_counts_and_candidates.complete", found_counts=found_counts)
        return found_counts, candidates_by_level, full_queries, web_urls, last_query, stage_attempts

