from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.settings import settings
from app.models.schemas import (
    GenerateQueriesRequest,
    GenerateQueriesResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.hh_search import HHSearchService
from app.services.prompts import PromptService
from app.services.query_generator import QueryGenerator


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
def generate_queries(payload: GenerateQueriesRequest, mock_llm: bool = False):
    gen = QueryGenerator(
        llm_url=settings.llm_url,
        llm_token_param=settings.llm_token_param,
    )
    queries, llm_raw = gen.generate(
        payload.request_text,
        system_prompt_override=payload.system_prompt_override,
        user_prompt_override=payload.user_prompt_override,
        mock=mock_llm or settings.use_mock_llm,
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
        mock=payload.mock_llm or settings.use_mock_llm,
    )

    token_source = settings.default_token_source
    hh = HHSearchService(
        token_url=settings.hh_token_url,
        token_source=token_source,
        oauth_token_url=settings.hh_oauth_token_url,
        base_client_id=settings.base_client_id,
        base_client_secret=settings.base_client_secret,
    )
    found_counts, candidates_by_level_raw, full_queries = hh.search_counts_and_candidates(
        queries,
        source_text=payload.request_text,
        area_id=area_id,
        professional_roles=professional_roles,
        mock=payload.mock_hh or settings.use_mock_hh,
    )

    # Normalize candidates to a thin useful shape for UI.
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
                    # sometimes HH raw item may include names; keep if present
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

