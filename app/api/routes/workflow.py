from __future__ import annotations

import base64
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.core.settings import settings
from app.core.tracing import trace_step
from app.models.schemas import (
    ExportExcelUiRequest,
    GenerateQueriesRequest,
    GenerateQueriesResponse,
    LevelName,
    SearchRequest,
    SearchResponse,
    SvetoforResponse,
    TrafficLightFromCandidatesRequest,
    TrafficLightFromCandidatesResponse,
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
_log = logging.getLogger(__name__)


def _run_query_generation(
    *,
    request_text: str,
    system_prompt_override: str | None,
    user_prompt_override: str | None,
    queries_override: dict[LevelName, str] | None,
) -> tuple[dict[str, str], Any | None, datetime, datetime]:
    """Генерация или подстановка булевых запросов; возвращает (queries, llm_raw, started_at, bool_finished_at)."""
    started_at = datetime.utcnow()
    trace_step(
        _log,
        "workflow",
        "_run_query_generation.start",
        has_queries_override=queries_override is not None,
        request_text_preview=(request_text or "")[:500],
    )
    if queries_override is not None:
        qn = normalize_level_queries(queries_override)
        trace_step(_log, "workflow", "_run_query_generation.override_queries", level_keys=list(qn.keys()))
        return qn, None, started_at, started_at
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
    trace_step(
        _log,
        "workflow",
        "_run_query_generation.llm_done",
        level_keys=list(queries.keys()),
        llm_raw_is_none=llm_raw is None,
    )
    return queries, llm_raw, started_at, bool_finished_at


def _excel_optional_b64(
    payload: SearchRequest,
    *,
    level_queries: dict[str, str] | None,
    queries_with_exclusions: dict[str, str] | None,
    hh_search_urls: dict[str, str] | None,
    selected_level: str | None,
    found_counts: dict,
    candidates_by_level_raw: dict[str, list],
    traffic_light_candidates: list,
    started_at: datetime,
    bool_finished_at: datetime,
    hh_finished_at: datetime,
    finished_at: datetime,
    ran_traffic_light: bool,
) -> tuple[str | None, str | None]:
    trace_step(_log, "workflow", "_excel_optional_b64.check", include_excel=payload.include_excel)
    if not payload.include_excel:
        return None, None
    if not xlsxwriter_available():
        trace_step(_log, "workflow", "_excel_optional_b64.fail", reason="xlsxwriter_missing")
        raise HTTPException(status_code=500, detail="xlsxwriter is not installed on server")
    raw, fname = build_search_excel_bytes(
        request_text=payload.request_text,
        level_queries=level_queries,
        queries_with_exclusions=queries_with_exclusions,
        hh_search_urls=hh_search_urls,
        selected_level=selected_level,
        found_counts=found_counts,
        candidates_by_level_raw=candidates_by_level_raw,
        traffic_light_candidates=traffic_light_candidates,
        started_at=started_at,
        bool_finished_at=bool_finished_at,
        hh_finished_at=hh_finished_at,
        finished_at=finished_at,
        ran_traffic_light=ran_traffic_light,
    )
    trace_step(_log, "workflow", "_excel_optional_b64.built", filename=fname, raw_bytes=len(raw))
    return base64.b64encode(raw).decode("ascii"), fname


@router.get("/default_request", response_class=PlainTextResponse)
def default_request() -> str:
    trace_step(_log, "workflow", "default_request")
    return PromptService().get_default_request_text()


@router.get("/system_prompt", response_class=PlainTextResponse)
def system_prompt() -> str:
    trace_step(_log, "workflow", "system_prompt")
    return PromptService().get_system_prompt_text()


@router.get("/user_prompt", response_class=PlainTextResponse)
def user_prompt() -> str:
    trace_step(_log, "workflow", "user_prompt")
    return PromptService().get_user_prompt_text()


@router.post("/generate_queries", response_model=GenerateQueriesResponse)
def generate_queries(payload: GenerateQueriesRequest):
    trace_step(
        _log,
        "workflow",
        "generate_queries",
        request_text_preview=(payload.request_text or "")[:300],
        has_queries_override=payload.queries_override is not None,
    )
    queries, llm_raw, _, _ = _run_query_generation(
        request_text=payload.request_text,
        system_prompt_override=payload.system_prompt_override,
        user_prompt_override=payload.user_prompt_override,
        queries_override=payload.queries_override,
    )
    return GenerateQueriesResponse(llm_raw=llm_raw, queries=queries)  # type: ignore[arg-type]


@router.post("/search", response_model=SearchResponse, response_model_exclude_none=True)
def search(payload: SearchRequest):
    trace_step(
        _log,
        "workflow",
        "search.start",
        area_id=payload.area_id,
        candidates_limit=payload.candidates_limit,
        include_excel=payload.include_excel,
        request_preview=(payload.request_text or "")[:300],
    )
    area_id = payload.area_id or settings.area_id
    professional_roles = payload.professional_roles or settings.professional_roles
    trace_step(_log, "workflow", "search.params_resolved", area_id=area_id, professional_roles=professional_roles)

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
    found_counts, candidates_by_level_raw, full_queries, web_urls = hh.search_counts_and_candidates(
        queries,
        source_text=payload.request_text,
        area_id=area_id,
        professional_roles=professional_roles,
        per_page=payload.candidates_limit,
    )
    hh_finished_at = datetime.utcnow()
    finished_at = hh_finished_at
    trace_step(_log, "workflow", "search.hh_done", found_counts=found_counts)

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
    trace_step(
        _log,
        "workflow",
        "search.normalized_candidates",
        selected_level=selected_level,
        counts_by_level={k: len(v) for k, v in candidates_by_level.items()},
    )

    excel_b64, excel_fn = _excel_optional_b64(
        payload,
        level_queries=queries,
        queries_with_exclusions=full_queries,
        hh_search_urls=web_urls,
        selected_level=selected_level,
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
        hh_search_urls=web_urls,  # type: ignore[arg-type]
        found_counts=found_counts,  # type: ignore[arg-type]
        selected_level=selected_level,  # type: ignore[arg-type]
        token_source_used=token_source,  # type: ignore[arg-type]
        candidates_by_level=candidates_by_level,  # type: ignore[arg-type]
        excel_base64=excel_b64,
        excel_filename=excel_fn,
    )
    trace_step(_log, "workflow", "search.response_ready", selected_level=selected_level, has_excel=excel_b64 is not None)


def _pick_best_level_by_candidates(candidates_by_level_raw: dict[str, list[dict]]):
    counts = {k: len(v or []) for k, v in candidates_by_level_raw.items()}
    if (candidates_by_level_raw.get("Уровень 3") or []):
        trace_step(_log, "workflow", "_pick_best_level_by_candidates", choice="Уровень 3", counts=counts)
        return "Уровень 3"
    if (candidates_by_level_raw.get("Уровень 2") or []):
        trace_step(_log, "workflow", "_pick_best_level_by_candidates", choice="Уровень 2", counts=counts)
        return "Уровень 2"
    if (candidates_by_level_raw.get("Уровень 1") or []):
        trace_step(_log, "workflow", "_pick_best_level_by_candidates", choice="Уровень 1", counts=counts)
        return "Уровень 1"
    trace_step(_log, "workflow", "_pick_best_level_by_candidates", choice="Уровень 2_fallback", counts=counts)
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
    trace_step(
        _log,
        "workflow",
        "_collect_traffic_light_candidates.start",
        input_count=len(candidates_for_tl),
        ids=[str(c.get("id")) for c in candidates_for_tl if c.get("id")],
        stability_params={
            "min_stay_months": payload.min_stay_months,
            "allowed_short_jobs": payload.allowed_short_jobs,
            "jump_mode": payload.jump_mode,
            "max_not_employed_months": payload.max_not_employed_months,
        },
    )
    traffic_light_service = TrafficLightService()
    import asyncio

    semaphore = asyncio.Semaphore(10)

    async def process_one_candidate(c: dict[str, Any]) -> Any | None:
        async with semaphore:
            candidate_id = c.get("id")
            if not candidate_id:
                trace_step(_log, "workflow", "tl_candidate.skip", reason="no_id")
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
            trace_step(_log, "workflow", "tl_candidate.fetch_resume", candidate_id=str(candidate_id), name=name)

            resume_data = await asyncio.to_thread(hh.hh.get_resume_by_id, str(candidate_id))
            if not isinstance(resume_data, dict):
                trace_step(_log, "workflow", "tl_candidate.skip", candidate_id=str(candidate_id), reason="resume_empty")
                return None

            exp_list = resume_data.get("experience")
            passed = candidate_passes_job_stability(
                exp_list if isinstance(exp_list, list) else None,
                min_stay_months=payload.min_stay_months,
                allowed_short_jobs=payload.allowed_short_jobs,
                jump_mode=payload.jump_mode,
                max_not_employed_months=payload.max_not_employed_months,
            )
            if not passed:
                trace_step(
                    _log,
                    "workflow",
                    "tl_candidate.stability_reject",
                    candidate_id=str(candidate_id),
                )
                return None

            candidate_prj_exp = _extract_candidate_prj_exp(resume_data)
            trace_step(
                _log,
                "workflow",
                "tl_candidate.llm_traffic_light",
                candidate_id=str(candidate_id),
                prj_exp_len=len(candidate_prj_exp or ""),
            )

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
                trace_step(_log, "workflow", "tl_candidate.llm_error", candidate_id=str(candidate_id))
                return None
            trace_step(
                _log,
                "workflow",
                "tl_candidate.done",
                candidate_id=str(candidate_id),
                score=getattr(tl_candidate, "color_score_percent", None),
            )
            return tl_candidate

    results = await asyncio.gather(*(process_one_candidate(c) for c in candidates_for_tl))
    out = [r for r in results if r is not None]
    trace_step(_log, "workflow", "_collect_traffic_light_candidates.done", kept=len(out))
    return out


@router.post("/svetofor", response_model=SvetoforResponse, response_model_exclude_none=True)
async def svetofor(payload: SearchRequest):
    trace_step(
        _log,
        "workflow",
        "svetofor.start",
        svetofor_top_x=payload.svetofor_top_x,
        selected_level=payload.selected_level,
        request_preview=(payload.request_text or "")[:300],
    )
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
    found_counts, candidates_by_level_raw, full_queries, web_urls = hh.search_counts_and_candidates(
        queries,
        source_text=payload.request_text,
        area_id=area_id,
        professional_roles=professional_roles,
        per_page=payload.candidates_limit,
    )
    hh_finished_at = datetime.utcnow()
    trace_step(_log, "workflow", "svetofor.hh_done", found_counts=found_counts)

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

    # Важно: светофор должен строиться по выбранному уровню (таблице) из UI.
    # Если уровень не задан/некорректный — фолбэк на "лучший" по наличию кандидатов.
    selected_level = (
        payload.selected_level
        if payload.selected_level and payload.selected_level in candidates_by_level
        else _pick_best_level_by_candidates(candidates_by_level)
    )

    selected_list = candidates_by_level.get(selected_level, []) or []
    top_x = max(1, int(payload.svetofor_top_x))
    candidates_for_tl = selected_list[:top_x]
    trace_step(
        _log,
        "workflow",
        "svetofor.selection",
        selected_level=selected_level,
        top_x=top_x,
        shortlist_size=len(candidates_for_tl),
    )

    traffic_light_candidates = await _collect_traffic_light_candidates(hh, payload, candidates_for_tl)
    traffic_light_candidates = sorted(traffic_light_candidates, key=lambda x: x.color_score_percent, reverse=True)

    finished_at = datetime.utcnow()
    trace_step(_log, "workflow", "svetofor.tl_sorted", n=len(traffic_light_candidates))

    excel_b64, excel_fn = _excel_optional_b64(
        payload,
        level_queries=queries,
        queries_with_exclusions=full_queries,
        hh_search_urls=web_urls,
        selected_level=selected_level,
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
        hh_search_urls=web_urls,  # type: ignore[arg-type]
        found_counts=found_counts,  # type: ignore[arg-type]
        selected_level=selected_level,  # type: ignore[arg-type]
        token_source_used=token_source,  # type: ignore[arg-type]
        candidates_by_level=candidates_by_level,  # type: ignore[arg-type]
        traffic_light_candidates=traffic_light_candidates,  # type: ignore[arg-type]
        excel_base64=excel_b64,
        excel_filename=excel_fn,
    )
    trace_step(_log, "workflow", "svetofor.response_ready", tl_count=len(traffic_light_candidates))


@router.post("/traffic_light", response_model=TrafficLightFromCandidatesResponse, response_model_exclude_none=True)
async def traffic_light_from_candidates(payload: TrafficLightFromCandidatesRequest):
    """
    Светофор по уже найденным кандидатам (без LLM-генерации булевых запросов и без поиска HH).

    Важно: сервер всё равно догружает детали резюме по id (HH API), чтобы собрать проектный опыт,
    и затем вызывает LLM только для оценки соответствия (ColorScore).
    """
    trace_step(
        _log,
        "workflow",
        "traffic_light_from_candidates.start",
        selected_level=payload.selected_level,
        incoming_candidates=len(payload.candidates or []),
        top_x=payload.svetofor_top_x,
    )
    token_source = settings.token_source
    hh = HHSearchService(
        token_url=settings.hh_token_url,
        token_source=token_source,
    )

    level: LevelName = payload.selected_level
    top_x = max(1, int(payload.svetofor_top_x))

    candidates_for_tl: list[dict[str, Any]] = []
    for c in (payload.candidates or [])[:top_x]:
        # Pydantic model -> dict with all fields (including first/last name).
        candidates_for_tl.append(c.model_dump())

    # Переиспользуем существующую логику, которая ожидает SearchRequest для job-stability фильтров.
    search_like = SearchRequest(
        request_text=payload.request_text,
        selected_level=level,
        candidates_limit=len(candidates_for_tl) or 1,
        min_stay_months=payload.min_stay_months,
        allowed_short_jobs=payload.allowed_short_jobs,
        jump_mode=payload.jump_mode,
        max_not_employed_months=payload.max_not_employed_months,
        svetofor_top_x=top_x,
    )

    traffic_light_candidates = await _collect_traffic_light_candidates(hh, search_like, candidates_for_tl)
    traffic_light_candidates = sorted(traffic_light_candidates, key=lambda x: x.color_score_percent, reverse=True)
    trace_step(_log, "workflow", "traffic_light_from_candidates.done", n=len(traffic_light_candidates))

    return TrafficLightFromCandidatesResponse(
        selected_level=level,
        traffic_light_candidates=traffic_light_candidates,  # type: ignore[arg-type]
    )


@router.post("/export_excel")
async def export_excel(payload: SearchRequest):
    """
    Скачивание Excel (бинарный поток). Логика совпадает с опцией include_excel у /search и /svetofor.
    """
    trace_step(
        _log,
        "workflow",
        "export_excel.start",
        include_traffic_light=payload.include_traffic_light,
        has_precomputed_tl=bool(payload.traffic_light_candidates_for_excel),
    )
    if xlsxwriter is None:
        trace_step(_log, "workflow", "export_excel.fail", reason="no_xlsxwriter")
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
    found_counts, candidates_by_level_raw, full_queries, web_urls = hh.search_counts_and_candidates(
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

    trace_step(_log, "workflow", "export_excel.after_search", found_counts=found_counts, tl_stage=len(traffic_light_candidates))

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

    selected_level = payload.selected_level or _pick_best_level_by_candidates(
        {
            k: (v or [])
            for k, v in candidates_by_level_raw.items()
            if isinstance(v, list)
        }
    )

    raw_bytes, filename = build_search_excel_bytes(
        request_text=payload.request_text,
        level_queries=queries,
        queries_with_exclusions=full_queries,
        hh_search_urls=web_urls,
        selected_level=selected_level,
        found_counts=found_counts,
        candidates_by_level_raw=candidates_by_level_raw,
        traffic_light_candidates=traffic_light_candidates,
        started_at=started_at,
        bool_finished_at=bool_finished_at,
        hh_finished_at=hh_finished_at,
        finished_at=finished_at,
        ran_traffic_light=bool(payload.include_traffic_light),
    )
    trace_step(_log, "workflow", "export_excel.built", filename=filename, size=len(raw_bytes))
    output = io.BytesIO(raw_bytes)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return StreamingResponse(output, media_type=headers["Content-Type"], headers=headers)


@router.post("/export_excel_ui")
async def export_excel_ui(payload: ExportExcelUiRequest):
    """
    Скачивание Excel (бинарный поток) без повторного запуска поиска HH.
    UI передаёт уже полученные результаты поиска и (опционально) светофоры по уровням.
    """
    trace_step(
        _log,
        "workflow",
        "export_excel_ui.start",
        selected_level=payload.selected_level,
        tl_levels=list((payload.traffic_lights_by_level or {}).keys()) if payload.traffic_lights_by_level else [],
    )
    if xlsxwriter is None:
        trace_step(_log, "workflow", "export_excel_ui.fail", reason="no_xlsxwriter")
        raise HTTPException(status_code=500, detail="xlsxwriter is not installed on server")

    started_at = datetime.utcnow()

    # UI уже прислал нормализованные данные.
    candidates_by_level_raw: dict[str, list[Any]] = {}
    for lvl, items in (payload.candidates_by_level or {}).items():
        out: list[Any] = []
        for c in items or []:
            # Candidate model -> dict
            try:
                out.append(c.model_dump())
            except Exception:
                out.append(c)
        candidates_by_level_raw[lvl] = out

    traffic_light_candidates_by_level: dict[str, list[Any]] | None = None
    ran_traffic_light = False
    if payload.traffic_lights_by_level:
        traffic_light_candidates_by_level = {}
        for lvl, items in payload.traffic_lights_by_level.items():
            out_tl: list[Any] = []
            for c in items or []:
                try:
                    out_tl.append(c.model_dump())
                except Exception:
                    out_tl.append(c)
            if out_tl:
                traffic_light_candidates_by_level[lvl] = out_tl
        ran_traffic_light = bool(traffic_light_candidates_by_level)

    # Тайминги: для UI-экспорта ставим одинаковые отметки (мы не можем восстановить реальные).
    finished_at = datetime.utcnow()
    raw_bytes, filename = build_search_excel_bytes(
        request_text=payload.request_text,
        level_queries=payload.queries,
        queries_with_exclusions=payload.queries_with_exclusions,
        hh_search_urls=payload.hh_search_urls,
        selected_level=payload.selected_level,
        found_counts=payload.found_counts,
        candidates_by_level_raw=candidates_by_level_raw,
        traffic_light_candidates=[],
        traffic_light_candidates_by_level=traffic_light_candidates_by_level,
        started_at=started_at,
        bool_finished_at=started_at,
        hh_finished_at=started_at,
        finished_at=finished_at,
        ran_traffic_light=ran_traffic_light,
    )
    output = io.BytesIO(raw_bytes)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    trace_step(_log, "workflow", "export_excel_ui.built", filename=filename, size=len(raw_bytes))
    return StreamingResponse(output, media_type=headers["Content-Type"], headers=headers)
