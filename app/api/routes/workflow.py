from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.settings import settings
from app.models.schemas import (
    GenerateQueriesRequest,
    GenerateQueriesResponse,
    SearchRequest,
    SearchResponse,
    SvetoforResponse,
)
from app.services.hh_search import HHSearchService
from app.services.prompts import PromptService
from app.services.query_generator import QueryGenerator
from app.services.traffic_light_service import TrafficLightService
from app.services.job_stability import candidate_passes_job_stability


router = APIRouter()


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
    gen = QueryGenerator(
        llm_url=settings.llm_url,
        llm_token_param=settings.llm_token_param,
    )
    queries, llm_raw = gen.generate(
        payload.request_text,
        system_prompt_override=payload.system_prompt_override,
        user_prompt_override=payload.user_prompt_override,
    )
    return GenerateQueriesResponse(llm_raw=llm_raw, queries=queries)  # type: ignore[arg-type]


@router.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest):
    area_id = payload.area_id or settings.area_id
    professional_roles = payload.professional_roles or settings.professional_roles

    gen = QueryGenerator(
        llm_url=settings.llm_url,
        llm_token_param=settings.llm_token_param,
    )
    queries, llm_raw = gen.generate(
        payload.request_text,
        system_prompt_override=payload.system_prompt_override,
        user_prompt_override=payload.user_prompt_override,
    )

    # В проекте используется единственный источник токена: SSP.
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

    # Нормализуем ответ HH до стабильной структуры для UI.
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
                    # В некоторых ответах HH приходят имя/фамилия отдельными полями.
                    "first_name": it.get("first_name"),
                    "last_name": it.get("last_name"),
                }
            )
        candidates_by_level[level] = norm

    selected_level = payload.selected_level if payload.selected_level in queries else "Уровень 2"

    return SearchResponse(
        llm_raw=llm_raw,
        queries=queries,  # type: ignore[arg-type]
        queries_with_exclusions=full_queries,  # type: ignore[arg-type]
        found_counts=found_counts,  # type: ignore[arg-type]
        selected_level=selected_level,  # type: ignore[arg-type]
        token_source_used=token_source,  # type: ignore[arg-type]
        candidates_by_level=candidates_by_level,  # type: ignore[arg-type]
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
    """
    "Проектный опыт" в проекте подставляется как часть `experience` резюме.
    Не вставляем контакты/всю карточку, только выдержки из описаний опытов.
    """
    exp = resume_data.get("experience")
    if not isinstance(exp, list):
        return ""

    parts: list[str] = []
    # Ограничиваем размер под LLM и чтобы не вставлять всю карточку.
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


@router.post("/svetofor", response_model=SvetoforResponse)
async def svetofor(payload: SearchRequest):
    area_id = payload.area_id or settings.area_id
    professional_roles = payload.professional_roles or settings.professional_roles

    gen = QueryGenerator(
        llm_url=settings.llm_url,
        llm_token_param=settings.llm_token_param,
    )
    queries, llm_raw = gen.generate(
        payload.request_text,
        system_prompt_override=payload.system_prompt_override,
        user_prompt_override=payload.user_prompt_override,
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

    # Нормализуем ответ HH до стабильной структуры для UI.
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

    traffic_light_service = TrafficLightService()
    selected_list = candidates_by_level.get(selected_level, []) or []
    traffic_light_candidates: list = []

    top_x = max(1, int(payload.svetofor_top_x))
    candidates_for_tl = selected_list[:top_x]

    # Async processing: each candidate needs HH resume fetch + LLM traffic light call.
    # We run tasks concurrently to reduce end-to-end latency.
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

            # HH resume is sync; run in thread to avoid blocking the event loop.
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
                # If LLM returns unexpected shape for a candidate, skip it.
                return None
            return tl_candidate

    results = await asyncio.gather(*(process_one_candidate(c) for c in candidates_for_tl))
    traffic_light_candidates = [r for r in results if r is not None]

    traffic_light_candidates = sorted(traffic_light_candidates, key=lambda x: x.color_score_percent, reverse=True)

    return SvetoforResponse(
        llm_raw=llm_raw,
        queries=queries,  # type: ignore[arg-type]
        queries_with_exclusions=full_queries,  # type: ignore[arg-type]
        found_counts=found_counts,  # type: ignore[arg-type]
        selected_level=selected_level,  # type: ignore[arg-type]
        token_source_used=token_source,  # type: ignore[arg-type]
        candidates_by_level=candidates_by_level,  # type: ignore[arg-type]
        traffic_light_candidates=traffic_light_candidates,  # type: ignore[arg-type]
    )

