from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.core.settings import settings
from app.models.schemas import (
    GenerateQueriesRequest,
    GenerateQueriesResponse,
    LevelName,
    SearchRequest,
    SearchResponse,
    SvetoforResponse,
    normalize_level_queries,
)
from app.services.excel_export import build_search_excel_bytes, xlsxwriter_available
from app.services.hh_search import HHSearchService
from app.services.prompts import PromptService
from app.services.query_generator import QueryGenerator
from app.services.traffic_light_service import TrafficLightService
from app.services.job_stability import candidate_passes_job_stability

try:
    import io

    import xlsxwriter  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional dependency
    xlsxwriter = None  # type: ignore[assignment]


router = APIRouter()


def _run_query_generation(
    *,
    request_text: str,
    system_prompt_override: str | None,
    user_prompt_override: str | None,
    queries_override: dict[LevelName, str] | None,
) -> tuple[dict[str, str], Any | None, datetime, datetime]:
    """Генерация или подстановка булевых запросов; возвращает (queries, llm_raw, started_at, bool_finished_at)."""
    started_at = datetime.utcnow()
    if queries_override is not None:
        return normalize_level_queries(queries_override), None, started_at, started_at
    gen = QueryGenerator(
        llm_url=settings.llm_url,
        llm_token_param=settings.llm_token_param,
    )
    queries, llm_raw = gen.generate(
        request_text,
        system_prompt_override=system_prompt_override,
        user_prompt_override=user_prompt_override,
    )
    bool_finished_at = datetime.utcnow()
    return queries, llm_raw, started_at, bool_finished_at


def _excel_optional_b64(
    payload: SearchRequest,
    *,
    found_counts: dict,
    candidates_by_level_raw: dict[str, list],
    traffic_light_candidates: list,
    started_at: datetime,
    bool_finished_at: datetime,
    hh_finished_at: datetime,
    finished_at: datetime,
    ran_traffic_light: bool,
) -> tuple[str | None, str | None]:
    if not payload.include_excel:
        return None, None
    if not xlsxwriter_available():
        raise HTTPException(status_code=500, detail="xlsxwriter is not installed on server")
    raw, fname = build_search_excel_bytes(
        request_text=payload.request_text,
        found_counts=found_counts,
        candidates_by_level_raw=candidates_by_level_raw,
        traffic_light_candidates=traffic_light_candidates,
        started_at=started_at,
        bool_finished_at=bool_finished_at,
        hh_finished_at=hh_finished_at,
        finished_at=finished_at,
        ran_traffic_light=ran_traffic_light,
    )
    return base64.b64encode(raw).decode("ascii"), fname


@router.get("/default_request", response_class=PlainTextResponse)
def default_request() -> str:
    return PromptService().get_default_request_text()


@router.get("/system_prompt", response_class=PlainTextResponse)
def system_prompt() -> str:
    return PromptService().get_system_prompt_text()


@router.get("/user_prompt", response_class=PlainTextResponse)
def user_prompt() -> str:
    return PromptService().get_user_prompt_text()


@router.post("/generate_queries", response_model=GenerateQueriesResponse)
def generate_queries(payload: GenerateQueriesRequest):
    queries, llm_raw, _, _ = _run_query_generation(
        request_text=payload.request_text,
        system_prompt_override=payload.system_prompt_override,
        user_prompt_override=payload.user_prompt_override,
        queries_override=payload.queries_override,
    )
    return GenerateQueriesResponse(llm_raw=llm_raw, queries=queries)  # type: ignore[arg-type]


@router.post("/search", response_model=SearchResponse, response_model_exclude_none=True)
def search(payload: SearchRequest):
    area_id = payload.area_id or settings.area_id
    professional_roles = payload.professional_roles or settings.professional_roles

    queries, llm_raw, started_at, bool_finished_at = _run_query_generation(
        request_text=payload.request_text,
        system_prompt_override=payload.system_prompt_override,
        user_prompt_override=payload.user_prompt_override,
        queries_override=payload.queries_override,
    )

    token_source = settings.token_source
    hh = HHSearchService(
        token_url=settings.hh_token_url,
        token_source=token_source,
    )
    found_counts, candidates_by_level_raw, full_queries = hh.search_counts_and_candidates(
        queries,
        source_text=payload.request_text,
        area_id=area_id,
        professional_roles=professional_roles,
        per_page=payload.candidates_limit,
    )
    hh_finished_at = datetime.utcnow()
    finished_at = hh_finished_at

    candidates_by_level = {}
    for level, items in candidates_by_level_raw.items():
        norm = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            norm.append(
                {
                    "id": it.get("id"),
                    "title": it.get("title"),
                    "url": it.get("url"),
                    "alternate_url": it.get("alternate_url"),
                    "created_at": it.get("created_at"),
                    "updated_at": it.get("updated_at"),
                    "age": it.get("age"),
                    "area": it.get("area"),
                    "employer": it.get("employer"),
                    "salary": it.get("salary"),
                    "experience": it.get("experience"),
                    "skills": it.get("skills") if isinstance(it.get("skills"), list) else [],
                    "tags": it.get("tags") if isinstance(it.get("tags"), list) else [],
                    "first_name": it.get("first_name"),
                    "last_name": it.get("last_name"),
                }
            )
        candidates_by_level[level] = norm

    selected_level = payload.selected_level if payload.selected_level in queries else "Уровень 2"

    excel_b64, excel_fn = _excel_optional_b64(
        payload,
        found_counts=found_counts,
        candidates_by_level_raw=candidates_by_level_raw,
        traffic_light_candidates=[],
        started_at=started_at,
        bool_finished_at=bool_finished_at,
        hh_finished_at=hh_finished_at,
        finished_at=finished_at,
        ran_traffic_light=False,
    )

    return SearchResponse(
        llm_raw=llm_raw,
        queries=queries,  # type: ignore[arg-type]
        queries_with_exclusions=full_queries,  # type: ignore[arg-type]
        found_counts=found_counts,  # type: ignore[arg-type]
        selected_level=selected_level,  # type: ignore[arg-type]
        token_source_used=token_source,  # type: ignore[arg-type]
        candidates_by_level=candidates_by_level,  # type: ignore[arg-type]
        excel_base64=excel_b64,
        excel_filename=excel_fn,
    )


def _pick_best_level_by_candidates(candidates_by_level_raw: dict[str, list[dict]]):
    if (candidates_by_level_raw.get("Уровень 3") or []):
        return "Уровень 3"
    if (candidates_by_level_raw.get("Уровень 2") or []):
        return "Уровень 2"
    if (candidates_by_level_raw.get("Уровень 1") or []):
        return "Уровень 1"
    return "Уровень 2"


def _candidate_name(candidate: dict) -> str:
    first = candidate.get("first_name") or ""
    last = candidate.get("last_name") or ""
    name = f"{last} {first}".strip()
    return name or str(candidate.get("id") or "")


def _extract_candidate_prj_exp(resume_data: dict) -> str:
    exp = resume_data.get("experience")
    if not isinstance(exp, list):
        return ""

    parts: list[str] = []
    for it in exp[:12]:
        if not isinstance(it, dict):
            continue
        desc = it.get("description")
        if not desc:
            continue
        position = it.get("position") or ""
        company = it.get("company") or ""
        start = it.get("start") or ""
        end = it.get("end") or ""
        period = f"{start} - {end}".strip(" -")
        header = " ".join([p for p in [period, f"({company})" if company else "", position] if p]).strip()
        parts.append(f"{header}: {desc}".strip(": ").strip())
    return "\n".join(parts).strip()


async def _collect_traffic_light_candidates(
    hh: HHSearchService,
    payload: SearchRequest,
    candidates_for_tl: list[dict],
) -> list:
    traffic_light_service = TrafficLightService()
    import asyncio

    semaphore = asyncio.Semaphore(10)

    async def process_one_candidate(c: dict[str, Any]) -> Any | None:
        async with semaphore:
            candidate_id = c.get("id")
            if not candidate_id:
                return None

            name = _candidate_name(c)
            title = c.get("title")

            area = c.get("area")
            location = ""
            if isinstance(area, dict):
                location = area.get("name") or ""
            elif isinstance(area, str):
                location = area

            resume_url = c.get("alternate_url") or c.get("url")

            resume_data = await asyncio.to_thread(hh.hh.get_resume_by_id, str(candidate_id))
            if not isinstance(resume_data, dict):
                return None

            exp_list = resume_data.get("experience")
            if not candidate_passes_job_stability(
                exp_list if isinstance(exp_list, list) else None,
                min_stay_months=payload.min_stay_months,
                allowed_short_jobs=payload.allowed_short_jobs,
                jump_mode=payload.jump_mode,
                max_not_employed_months=payload.max_not_employed_months,
            ):
                return None

            candidate_prj_exp = _extract_candidate_prj_exp(resume_data)

            try:
                tl_candidate, _llm_raw_tl = await asyncio.to_thread(
                    traffic_light_service.generate_candidate_traffic_light,
                    request_text=payload.request_text,
                    candidate_prj_exp=candidate_prj_exp,
                    candidate_id=str(candidate_id),
                    candidate_name=name,
                    title=title,
                    location=location or None,
                    resume_url=resume_url or None,
                )
            except Exception:
                return None
            return tl_candidate

    results = await asyncio.gather(*(process_one_candidate(c) for c in candidates_for_tl))
    return [r for r in results if r is not None]


@router.post("/svetofor", response_model=SvetoforResponse, response_model_exclude_none=True)
async def svetofor(payload: SearchRequest):
    area_id = payload.area_id or settings.area_id
    professional_roles = payload.professional_roles or settings.professional_roles

    queries, llm_raw, started_at, bool_finished_at = _run_query_generation(
        request_text=payload.request_text,
        system_prompt_override=payload.system_prompt_override,
        user_prompt_override=payload.user_prompt_override,
        queries_override=payload.queries_override,
    )

    token_source = settings.token_source
    hh = HHSearchService(
        token_url=settings.hh_token_url,
        token_source=token_source,
    )
    found_counts, candidates_by_level_raw, full_queries = hh.search_counts_and_candidates(
        queries,
        source_text=payload.request_text,
        area_id=area_id,
        professional_roles=professional_roles,
        per_page=payload.candidates_limit,
    )
    hh_finished_at = datetime.utcnow()

    candidates_by_level: dict[str, list[dict]] = {}
    for level, items in candidates_by_level_raw.items():
        norm: list[dict] = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            norm.append(
                {
                    "id": it.get("id"),
                    "title": it.get("title"),
                    "url": it.get("url"),
                    "alternate_url": it.get("alternate_url"),
                    "created_at": it.get("created_at"),
                    "updated_at": it.get("updated_at"),
                    "age": it.get("age"),
                    "area": it.get("area"),
                    "employer": it.get("employer"),
                    "salary": it.get("salary"),
                    "experience": it.get("experience"),
                    "skills": it.get("skills") if isinstance(it.get("skills"), list) else [],
                    "tags": it.get("tags") if isinstance(it.get("tags"), list) else [],
                    "first_name": it.get("first_name"),
                    "last_name": it.get("last_name"),
                }
            )
        candidates_by_level[level] = norm

    selected_level = _pick_best_level_by_candidates(candidates_by_level)

    selected_list = candidates_by_level.get(selected_level, []) or []
    top_x = max(1, int(payload.svetofor_top_x))
    candidates_for_tl = selected_list[:top_x]

    traffic_light_candidates = await _collect_traffic_light_candidates(hh, payload, candidates_for_tl)
    traffic_light_candidates = sorted(traffic_light_candidates, key=lambda x: x.color_score_percent, reverse=True)

    finished_at = datetime.utcnow()

    excel_b64, excel_fn = _excel_optional_b64(
        payload,
        found_counts=found_counts,
        candidates_by_level_raw=candidates_by_level_raw,
        traffic_light_candidates=traffic_light_candidates,
        started_at=started_at,
        bool_finished_at=bool_finished_at,
        hh_finished_at=hh_finished_at,
        finished_at=finished_at,
        ran_traffic_light=True,
    )

    return SvetoforResponse(
        llm_raw=llm_raw,
        queries=queries,  # type: ignore[arg-type]
        queries_with_exclusions=full_queries,  # type: ignore[arg-type]
        found_counts=found_counts,  # type: ignore[arg-type]
        selected_level=selected_level,  # type: ignore[arg-type]
        token_source_used=token_source,  # type: ignore[arg-type]
        candidates_by_level=candidates_by_level,  # type: ignore[arg-type]
        traffic_light_candidates=traffic_light_candidates,  # type: ignore[arg-type]
        excel_base64=excel_b64,
        excel_filename=excel_fn,
    )


@router.post("/export_excel")
async def export_excel(payload: SearchRequest):
    """
    Скачивание Excel (бинарный поток). Логика совпадает с опцией include_excel у /search и /svetofor.
    """
    if xlsxwriter is None:
        raise HTTPException(status_code=500, detail="xlsxwriter is not installed on server")

    started_at = datetime.utcnow()

    queries, _llm_raw, gen_started, bool_finished_at = _run_query_generation(
        request_text=payload.request_text,
        system_prompt_override=payload.system_prompt_override,
        user_prompt_override=payload.user_prompt_override,
        queries_override=payload.queries_override,
    )
    # Старт замера — момент начала этапа булевых запросов (как в прежней реализации).
    started_at = gen_started

    area_id = payload.area_id or settings.area_id
    professional_roles = payload.professional_roles or settings.professional_roles

    token_source = settings.token_source
    hh = HHSearchService(
        token_url=settings.hh_token_url,
        token_source=token_source,
    )
    found_counts, candidates_by_level_raw, full_queries = hh.search_counts_and_candidates(
        queries,
        source_text=payload.request_text,
        area_id=area_id,
        professional_roles=professional_roles,
        per_page=payload.candidates_limit,
    )
    hh_finished_at = datetime.utcnow()

    traffic_light_candidates: list = []
    if payload.include_traffic_light and payload.traffic_light_candidates_for_excel:
        traffic_light_candidates = list(payload.traffic_light_candidates_for_excel)
    elif payload.include_traffic_light and payload.svetofor_top_x and payload.svetofor_top_x > 0:
        selected_level = _pick_best_level_by_candidates(
            {
                k: (v or [])
                for k, v in candidates_by_level_raw.items()
                if isinstance(v, list)
            }
        )
        selected_list = candidates_by_level_raw.get(selected_level, []) or []
        top_x = max(1, int(payload.svetofor_top_x))
        candidates_for_tl = selected_list[:top_x]
        traffic_light_candidates = await _collect_traffic_light_candidates(hh, payload, candidates_for_tl)

    if traffic_light_candidates:
        def _score_value(item: object) -> float:
            raw = getattr(item, "color_score_percent", 0)
            if isinstance(raw, str):
                raw = raw.replace("%", "").strip()
            try:
                return float(raw or 0)
            except (TypeError, ValueError):
                return 0.0

        traffic_light_candidates = sorted(traffic_light_candidates, key=_score_value, reverse=True)

    finished_at = datetime.utcnow()

    raw_bytes, filename = build_search_excel_bytes(
        request_text=payload.request_text,
        found_counts=found_counts,
        candidates_by_level_raw=candidates_by_level_raw,
        traffic_light_candidates=traffic_light_candidates,
        started_at=started_at,
        bool_finished_at=bool_finished_at,
        hh_finished_at=hh_finished_at,
        finished_at=finished_at,
        ran_traffic_light=bool(payload.include_traffic_light),
    )
    output = io.BytesIO(raw_bytes)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return StreamingResponse(output, media_type=headers["Content-Type"], headers=headers)
