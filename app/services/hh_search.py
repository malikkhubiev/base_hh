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
        query: str,
        *,
        search_plan: list[tuple[str, str]] | None = None,
        search_plan_meta: list[dict[str, Any]] | None = None,
        source_text: str,
        area_id: int | None,
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
        - candidates (up to per_page)
        - final_query (last query attempted)
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
            area_id=area_id,
        )

        if search_plan:
            ordered_pairs = search_plan
        else:
            ordered_pairs = [("Этап 1", query)]

        collected: list[dict[str, Any]] = []
        collected_ids: set[str] = set()
        last_query = ""
        last_web_url = ""
        last_count = 0
        stage_attempts: list[dict[str, Any]] = []
        min_needed_int = int(min_needed) if min_needed is not None else int(per_page)
        min_needed_int = max(1, min_needed_int)
        display_limit = min(200, min_needed_int * 3)
        fetch_per_page = max(display_limit, int(per_page))
        for idx, (stage_name, q) in enumerate(ordered_pairs):
            full_q = q if q is not None else ""
            last_query = full_q
            web_url = self.hh.build_web_search_url(query=full_q, filters=filters, per_page=fetch_per_page)
            last_web_url = web_url

            count, items = self.hh.search(
                query=full_q,
                filters=filters,
                per_page=fetch_per_page,
                level_name=stage_name,
                iteration=idx,
            )
            last_count = int(count or 0)
            stage_items = items if isinstance(items, list) else []
            stage_new = 0
            for item in stage_items:
                cid = str(item.get("id") or "")
                if not cid or cid in collected_ids:
                    continue
                collected_ids.add(cid)
                collected.append(item)
                stage_new += 1
                if len(collected) >= display_limit:
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
                stage_new=stage_new,
                collected=len(collected),
            )
            # Минимум набран — дальше не ослабляем; на текущем этапе уже добрали до display_limit.
            if len(collected) >= min_needed_int:
                break

        main_items = collected[:display_limit]
        final_count = last_count
        trace_step(logger, "hh_search", "search_counts_and_candidates.complete", found_count=final_count, collected=len(main_items))
        return final_count, main_items, last_query, last_web_url, stage_attempts

