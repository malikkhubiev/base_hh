from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.settings import settings
from app.core.tracing import trace_step
from app.models.schemas import (
    GenerateQueriesRequest,
    GenerateQueriesResponse,
    SearchRequest,
    SearchResponse,
    ScreeningRequest,
    ScreeningResponse,
    SvetoforResponse,
    TrafficLightCandidate,
    TrafficLightRequirement,
    TrafficLightFromCandidatesRequest,
    TrafficLightFromCandidatesResponse,
)
from app.services.hh_search import HHSearchService
from app.services.prompts import PromptService
from app.services.request_query_planner import RequestQueryPlanner
from app.services.general_requirements_service import GeneralRequirementsService
from app.services.traffic_light_service import TrafficLightService

router = APIRouter()
_log = logging.getLogger(__name__)
MAX_SEARCH_ITERATIONS_BY_RESTART = (30, 40, 50, 60)
MAX_TOTAL_SEARCH_ITERATIONS = 100


def _run_query_generation(
    *,
    request_text: str,
    system_prompt_override: str | None,
    user_prompt_override: str | None,
    queries_override: dict[str, str] | None,
) -> tuple[dict[str, str], Any | None, list[tuple[str, str]], list[dict[str, Any]], datetime, datetime]:
    """Генерация или подстановка булевых запросов; возвращает (queries, llm_raw, started_at, bool_finished_at)."""
    if not (request_text or "").strip():
        request_text = PromptService().get_default_request_text()
    started_at = datetime.utcnow()
    trace_step(
        _log,
        "workflow",
        "_run_query_generation.start",
        has_queries_override=queries_override is not None,
        request_text_preview=(request_text or "")[:500],
    )
    if queries_override is not None:
        qn = {"Основной": str((queries_override or {}).get("Основной") or "")}
        trace_step(_log, "workflow", "_run_query_generation.override_queries", keys=list(qn.keys()))
        plan = [
            ("Этап override 1", qn.get("Основной", "")),
        ]
        plan = [(k, v) for k, v in plan if v]
        meta = [{"stage": k, "query": v} for k, v in plan]
        return qn, None, plan, meta, started_at, started_at

    # Новая логика из task.txt: разбивка запроса на блоки и комбинаторика.
    planner = RequestQueryPlanner(
        llm_url=settings.llm_url,
        llm_token_param=settings.llm_token_param,
    )
    planned = planner.build(request_text)
    queries = planned.queries
    llm_raw = planned.llm_debug
    bool_finished_at = datetime.utcnow()
    trace_step(
        _log,
        "workflow",
        "_run_query_generation.llm_done",
        level_keys=list(queries.keys()),
        llm_raw_is_none=llm_raw is None,
    )
    return queries, llm_raw, planned.search_plan, planned.search_plan_meta, started_at, bool_finished_at


def _normalize_candidates_by_level(candidates_by_level_raw: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    candidates_by_level: dict[str, list[dict[str, Any]]] = {}
    for level, items in candidates_by_level_raw.items():
        norm: list[dict[str, Any]] = []
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
                    "experience_full": it.get("experience_full"),
                    "skills": it.get("skills") if isinstance(it.get("skills"), list) else [],
                    "tags": it.get("tags") if isinstance(it.get("tags"), list) else [],
                    "first_name": it.get("first_name"),
                    "last_name": it.get("last_name"),
                }
            )
        candidates_by_level[level] = norm
    return candidates_by_level


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
    request_text = payload.request_text or PromptService().get_default_request_text()
    trace_step(
        _log,
        "workflow",
        "generate_queries",
        request_text_preview=(request_text or "")[:300],
        has_queries_override=payload.queries_override is not None,
    )
    queries, llm_raw, _, _, _, _ = _run_query_generation(
        request_text=request_text,
        system_prompt_override=payload.system_prompt_override,
        user_prompt_override=payload.user_prompt_override,
        queries_override=payload.queries_override,
    )
    return GenerateQueriesResponse(llm_raw=llm_raw, queries=queries)  # type: ignore[arg-type]


def _run_search_with_restarts(
    *,
    payload: SearchRequest,
    request_text: str,
    area_id: int,
) -> tuple[
    dict[str, str],
    Any | None,
    dict[str, int],
    dict[str, list[dict[str, Any]]],
    dict[str, str],
    dict[str, str],
    str,
    list[dict[str, Any]],
    datetime,
    datetime,
    datetime,
    int,
    int,
]:
    token_source = settings.token_source
    hh = HHSearchService(
        token_url=settings.hh_token_url,
        token_source=token_source,
    )
    accumulated_attempts: list[dict[str, Any]] = []
    prompt_restarts = 0
    total_iterations = 0
    started_at_overall: datetime | None = None
    bool_finished_at_last: datetime | None = None
    hh_finished_at_last: datetime | None = None
    last_output: tuple[Any, ...] | None = None
    best_output: tuple[Any, ...] | None = None
    best_count = -1

    for max_attempts in MAX_SEARCH_ITERATIONS_BY_RESTART:
        if total_iterations >= MAX_TOTAL_SEARCH_ITERATIONS:
            trace_step(
                _log,
                "workflow",
                "_run_search_with_restarts.iteration_limit_reached",
                total_iterations=total_iterations,
                max_total_iterations=MAX_TOTAL_SEARCH_ITERATIONS,
            )
            break
        queries, llm_raw, search_plan, search_plan_meta, started_at, bool_finished_at = _run_query_generation(
            request_text=request_text,
            system_prompt_override=payload.system_prompt_override,
            user_prompt_override=payload.user_prompt_override,
            queries_override=payload.queries_override,
        )
        if started_at_overall is None:
            started_at_overall = started_at
        bool_finished_at_last = bool_finished_at

        found_counts, candidates_by_level_raw, full_queries, web_urls, final_boolean_query, stage_attempts = hh.search_counts_and_candidates(
            queries,
            search_plan=search_plan,
            search_plan_meta=search_plan_meta,
            source_text=request_text,
            area_id=area_id,
            per_page=min(200, int(payload.candidates_limit) * 3),
            min_needed=int(payload.candidates_limit),
            max_stage_attempts=max_attempts,
        )
        hh_finished_at_last = datetime.utcnow()
        accumulated_attempts.extend(stage_attempts)
        total_iterations += len(stage_attempts)
        if total_iterations > MAX_TOTAL_SEARCH_ITERATIONS:
            overflow = total_iterations - MAX_TOTAL_SEARCH_ITERATIONS
            if overflow > 0:
                if overflow <= len(stage_attempts):
                    stage_attempts = stage_attempts[:-overflow] if overflow < len(stage_attempts) else []
                    accumulated_attempts = accumulated_attempts[:-overflow] if overflow <= len(accumulated_attempts) else []
                total_iterations = MAX_TOTAL_SEARCH_ITERATIONS
        last_output = (
            queries,
            llm_raw,
            found_counts,
            candidates_by_level_raw,
            full_queries,
            web_urls,
            final_boolean_query,
        )
        current_count = len(candidates_by_level_raw.get("Основной", []))
        if current_count > best_count:
            best_count = current_count
            best_output = last_output
        if len(candidates_by_level_raw.get("Основной", [])) >= payload.candidates_limit:
            break
        prompt_restarts += 1

    chosen_output = best_output or last_output
    if not chosen_output or started_at_overall is None or bool_finished_at_last is None or hh_finished_at_last is None:
        raise RuntimeError("Search pipeline failed unexpectedly")

    queries, llm_raw, found_counts, candidates_by_level_raw, full_queries, web_urls, final_boolean_query = chosen_output
    return (
        queries,
        llm_raw,
        found_counts,
        candidates_by_level_raw,
        full_queries,
        web_urls,
        final_boolean_query,
        accumulated_attempts,
        started_at_overall,
        bool_finished_at_last,
        hh_finished_at_last,
        total_iterations,
        prompt_restarts,
    )


@router.post("/search", response_model=SearchResponse, response_model_exclude_none=True)
def search(payload: SearchRequest):
    request_text = payload.request_text or PromptService().get_default_request_text()
    trace_step(_log, "workflow", "search.start", area_id=payload.area_id, candidates_limit=payload.candidates_limit, request_preview=(request_text or "")[:300])
    area_id = payload.area_id or settings.area_id
    trace_step(_log, "workflow", "search.params_resolved", area_id=area_id)

    (
        queries,
        llm_raw,
        found_counts,
        candidates_by_level_raw,
        full_queries,
        web_urls,
        final_boolean_query,
        stage_attempts,
        started_at,
        bool_finished_at,
        hh_finished_at,
        total_iterations,
        prompt_restarts,
    ) = _run_search_with_restarts(payload=payload, request_text=request_text, area_id=area_id)
    finished_at = hh_finished_at
    trace_step(_log, "workflow", "search.hh_done", found_counts=found_counts)

    candidates_by_level = _normalize_candidates_by_level(candidates_by_level_raw)

    trace_step(_log, "workflow", "search.normalized_candidates", counts_by_level={k: len(v) for k, v in candidates_by_level.items()})

    final_search_url = web_urls.get("Основной")
    found_count = int((found_counts or {}).get("Основной") or 0)
    candidates = candidates_by_level.get("Основной", []) or []
    return SearchResponse(
        llm_raw=llm_raw,
        queries=queries,  # type: ignore[arg-type]
        queries_with_exclusions=full_queries,  # type: ignore[arg-type]
        hh_search_urls=web_urls,  # type: ignore[arg-type]
        found_count=found_count,
        candidates=candidates,  # type: ignore[arg-type]
        started_at=started_at,
        bool_finished_at=bool_finished_at,
        hh_finished_at=hh_finished_at,
        finished_at=finished_at,
        final_boolean_query=final_boolean_query,
        final_search_url=final_search_url,
        stage_attempts=stage_attempts,  # type: ignore[arg-type]
        total_iterations=total_iterations,
        prompt_restarts=prompt_restarts,
    )


def _pick_best_level_by_candidates(candidates_by_level_raw: dict[str, list[dict]]):
    counts = {k: len(v or []) for k, v in candidates_by_level_raw.items()}
    if (candidates_by_level_raw.get("Основной") or []):
        trace_step(_log, "workflow", "_pick_best_level_by_candidates", choice="Основной", counts=counts)
        return "Основной"
    trace_step(_log, "workflow", "_pick_best_level_by_candidates", choice="Основной_fallback", counts=counts)
    return "Основной"


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


def _normalize_full_experience(resume_data: dict[str, Any]) -> list[dict[str, Any]]:
    exp = resume_data.get("experience")
    if not isinstance(exp, list):
        return []
    out: list[dict[str, Any]] = []
    for it in exp:
        if not isinstance(it, dict):
            continue
        industries = it.get("industries")
        if not isinstance(industries, list):
            industries = []
        area = it.get("area")
        if not isinstance(area, dict):
            area = None
        out.append(
            {
                "id": it.get("id"),
                "start": it.get("start"),
                "end": it.get("end"),
                "company": it.get("company"),
                "company_id": it.get("company_id"),
                "company_url": it.get("company_url"),
                "position": it.get("position"),
                "description": it.get("description"),
                "industry": it.get("industry"),
                "industries": industries,
                "area": area,
                "employer": it.get("employer"),
            }
        )
    return out


def _parse_llm_markdown_json_any(llm_raw: Any) -> Any | None:
    """
    LLM sometimes returns {'markdown': '```json ...```'} (or nested under {'response': ...}).
    This helper removes code fences and parses JSON to a Python object.
    """
    import json
    import re

    response_obj = llm_raw.get("response", llm_raw) if isinstance(llm_raw, dict) else llm_raw
    if isinstance(response_obj, dict):
        markdown = response_obj.get("markdown")
        if isinstance(markdown, (dict, list)):
            return markdown
        if isinstance(markdown, str):
            response_obj = markdown
        else:
            return response_obj
    if not isinstance(response_obj, str):
        return None
    txt = response_obj.strip()
    txt = re.sub(r"^```[a-zA-Z]*\s*", "", txt)
    txt = re.sub(r"```\s*$", "", txt)
    # Extract JSON substring if surrounded by prose.
    if not ((txt.startswith("{") and txt.endswith("}")) or (txt.startswith("[") and txt.endswith("]"))):
        a = txt.find("[")
        b = txt.rfind("]")
        if a != -1 and b != -1 and b > a:
            txt = txt[a : b + 1]
        else:
            a = txt.find("{")
            b = txt.rfind("}")
            if a != -1 and b != -1 and b > a:
                txt = txt[a : b + 1]
    try:
        return json.loads(txt)
    except Exception:
        return None


def _extract_general_requirements_checks(llm_json: Any) -> list[dict[str, Any]]:
    """
    Expected shape (from task.txt example): [[[ok, requirement, evidence], ...]].
    We normalize to: [{'ok': bool, 'requirement': str, 'evidence': str}, ...]
    """
    out: list[dict[str, Any]] = []
    root = llm_json
    if isinstance(root, list) and len(root) == 1 and isinstance(root[0], list):
        root = root[0]
    if not isinstance(root, list):
        return out
    for it in root:
        if isinstance(it, list) and len(it) >= 3:
            ok = bool(it[0])
            req = str(it[1] or "")
            ev = str(it[2] or "")
            out.append({"ok": ok, "requirement": req, "evidence": ev})
        elif isinstance(it, dict):
            ok = bool(it.get("ok") or it.get("true") or it.get("is_true"))
            req = str(it.get("requirement") or it.get("check") or "")
            ev = str(it.get("evidence") or it.get("resume_evidence") or it.get("comment") or "")
            out.append({"ok": ok, "requirement": req, "evidence": ev})
    return out


def _build_unscored_traffic_light_candidate(candidate: dict[str, Any]) -> TrafficLightCandidate:
    candidate_id = str(candidate.get("id") or "")
    return TrafficLightCandidate(
        id=candidate_id,
        candidate_name=_candidate_name(candidate),
        title=candidate.get("title"),
        location=(candidate.get("area") or {}).get("name") if isinstance(candidate.get("area"), dict) else candidate.get("area"),
        resume_url=candidate.get("alternate_url") or candidate.get("url"),
        color_score_percent=0,
        requirements=[
            TrafficLightRequirement(
                requirement="Оценка не выполнена",
                resume_evidence="",
                match_percent=0,
                difference_comment="Кандидат не прошел фильтр стабильности или не удалось получить/оценить резюме.",
            )
        ],
    )


def _merge_traffic_light_with_source_candidates(
    candidates_for_tl: list[dict[str, Any]],
    scored_candidates: list[TrafficLightCandidate],
) -> list[TrafficLightCandidate]:
    # Светофор должен возвращать тот же набор кандидатов, что показан в таблице.
    by_id = {str(item.id): item for item in scored_candidates}
    merged: list[TrafficLightCandidate] = []
    for src in candidates_for_tl:
        src_id = str(src.get("id") or "")
        merged.append(by_id.get(src_id) or _build_unscored_traffic_light_candidate(src))
    return merged


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
            candidate_prj_exp = _extract_candidate_prj_exp(resume_data)
            full_exp = _normalize_full_experience(resume_data)
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
            try:
                tl_candidate = tl_candidate.model_copy(update={"experience_full": full_exp})
            except Exception:
                # If pydantic rejects something unexpected, keep candidate without full experience.
                pass
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
    request_text = payload.request_text or PromptService().get_default_request_text()
    trace_step(_log, "workflow", "svetofor.start", request_preview=(request_text or "")[:300])
    area_id = payload.area_id or settings.area_id

    top_x = max(1, int(payload.candidates_limit))
    search_payload = payload.model_copy(update={"candidates_limit": top_x})
    (
        queries,
        llm_raw,
        found_counts,
        candidates_by_level_raw,
        full_queries,
        web_urls,
        final_boolean_query,
        _applied_requirements,
        stage_attempts,
        started_at,
        bool_finished_at,
        hh_finished_at,
        total_iterations,
        prompt_restarts,
    ) = _run_search_with_restarts(payload=search_payload, request_text=request_text, area_id=area_id)

    hh = HHSearchService(token_url=settings.hh_token_url, token_source=settings.token_source)
    candidates_by_level = _normalize_candidates_by_level(candidates_by_level_raw)
    selected_list = candidates_by_level.get("Основной", []) or []
    candidates_for_tl = selected_list[:top_x]

    scored_candidates = await _collect_traffic_light_candidates(hh, payload, candidates_for_tl)
    traffic_light_candidates = sorted(scored_candidates, key=lambda x: x.color_score_percent, reverse=True)[:top_x]

    scored_ids = {str(item.id) for item in traffic_light_candidates}
    kept_candidates = [c for c in selected_list if str(c.get("id") or "") in scored_ids]
    found_count = len(kept_candidates)

    finished_at = datetime.utcnow()
    final_search_url = web_urls.get("Основной")
    return SvetoforResponse(
        llm_raw=llm_raw,
        queries=queries,  # type: ignore[arg-type]
        queries_with_exclusions=full_queries,  # type: ignore[arg-type]
        hh_search_urls=web_urls,  # type: ignore[arg-type]
        found_count=found_count,
        candidates=kept_candidates,  # type: ignore[arg-type]
        started_at=started_at,
        bool_finished_at=bool_finished_at,
        hh_finished_at=hh_finished_at,
        finished_at=finished_at,
        final_boolean_query=final_boolean_query,
        final_search_url=final_search_url,
        stage_attempts=stage_attempts,  # type: ignore[arg-type]
        total_iterations=total_iterations,
        prompt_restarts=prompt_restarts,
        traffic_light_candidates=traffic_light_candidates,  # type: ignore[arg-type]
    )


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
        incoming_candidates=len(payload.candidates or []),
    )
    token_source = settings.token_source
    hh = HHSearchService(
        token_url=settings.hh_token_url,
        token_source=token_source,
    )

    top_x = max(1, len(payload.candidates or []))

    candidates_for_tl: list[dict[str, Any]] = []
    for c in (payload.candidates or [])[:top_x]:
        # Pydantic model -> dict with all fields (including first/last name).
        candidates_for_tl.append(c.model_dump())

    # Переиспользуем существующую логику, которая ожидает SearchRequest для светофора.
    search_like = SearchRequest(request_text=payload.request_text, candidates_limit=len(candidates_for_tl) or 1)

    scored_candidates = await _collect_traffic_light_candidates(hh, search_like, candidates_for_tl)
    traffic_light_candidates = _merge_traffic_light_with_source_candidates(candidates_for_tl, scored_candidates)
    trace_step(_log, "workflow", "traffic_light_from_candidates.done", n=len(traffic_light_candidates))

    return TrafficLightFromCandidatesResponse(traffic_light_candidates=traffic_light_candidates)  # type: ignore[arg-type]


@router.post("/screening", response_model=ScreeningResponse, response_model_exclude_none=True)
async def screening(payload: ScreeningRequest):
    """
    Скрининг по выбранным кандидатам:
    - параллельно запускает "Светофор" (ColorScore) и "Общие требования" (general_req_prompt.txt)
    - резюме догружается по id (HH API) для извлечения проектного опыта
    """
    trace_step(
        _log,
        "workflow",
        "screening.start",
        candidates=len(payload.candidates or []),
    )
    token_source = settings.token_source
    hh = HHSearchService(
        token_url=settings.hh_token_url,
        token_source=token_source,
    )
    traffic_light_service = TrafficLightService()
    general_req_service = GeneralRequirementsService()

    import asyncio

    semaphore = asyncio.Semaphore(6)

    async def process_one(cand: dict[str, Any]) -> tuple[TrafficLightCandidate, dict[str, Any]]:
        async with semaphore:
            cid = str(cand.get("id") or "")
            name = _candidate_name(cand) or "-"
            resume_data = await asyncio.to_thread(hh.hh.get_resume_by_id, cid)
            candidate_prj_exp = _extract_candidate_prj_exp(resume_data or {}) if isinstance(resume_data, dict) else ""
            full_exp = _normalize_full_experience(resume_data or {}) if isinstance(resume_data, dict) else []

            tl_task = asyncio.to_thread(
                traffic_light_service.generate_candidate_traffic_light,
                request_text=payload.request_text,
                candidate_prj_exp=candidate_prj_exp,
                candidate_id=cid,
                candidate_name=name,
                title=cand.get("title"),
                location=(cand.get("area") or {}).get("name") if isinstance(cand.get("area"), dict) else None,
                resume_url=cand.get("alternate_url") or cand.get("url"),
            )
            gr_task = asyncio.to_thread(
                general_req_service.generate_candidate_review,
                cust_req_text=payload.general_requirements_text,
                candidate_prj_exp=candidate_prj_exp,
                candidate_id=cid,
                candidate_name=name,
            )
            (tl_candidate, _), (review_text, prompt, llm_raw) = await asyncio.gather(tl_task, gr_task)
            try:
                tl_candidate = tl_candidate.model_copy(update={"experience_full": full_exp})
            except Exception:
                pass
            llm_json = _parse_llm_markdown_json_any(llm_raw)
            checks = _extract_general_requirements_checks(llm_json)
            gr = {
                "id": cid,
                "candidate_name": name,
                "review_text": review_text,
                "checks": checks,
                "debug_prompt": prompt,
                "debug_llm_raw": llm_json,
            }
            return tl_candidate, gr

    candidates_for_processing: list[dict[str, Any]] = [c.model_dump() for c in (payload.candidates or [])]
    results = await asyncio.gather(*(process_one(c) for c in candidates_for_processing))
    tl_candidates = [r[0] for r in results]
    general_reqs = [r[1] for r in results]

    trace_step(_log, "workflow", "screening.done", tl=len(tl_candidates), gr=len(general_reqs))
    return ScreeningResponse(
        traffic_light_candidates=tl_candidates,
        general_requirements=general_reqs,  # type: ignore[arg-type]
    )


