from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from app.core.resume_pdf_store import resume_pdf_exists, resume_pdf_path
from app.core.resume_store import persist_scored_resume, persist_resume, get_resume_store
from app.core.traffic_light_store import get_traffic_light_store, persist_traffic_light_batch
from app.core.settings import settings
from app.core.tracing import trace_step
from app.core.workflow_session import create_session, require_session
from app.models.schemas import (
    GenerateQueriesRequest,
    GenerateQueriesResponse,
    SearchRequest,
    SearchResponse,
    RawResumeCandidate,
    SvetoforResponse,
    TrafficLightCandidate,
    TrafficLightRequirement,
    TrafficLightFromCandidatesRequest,
    TrafficLightFromCandidatesResponse,
    TrafficLightResultItem,
    ContactsRequest,
    ContactsResponse,
    AddedCandidateItem,
    TrafficLightPublic,
    TrafficLightRequirement,
)
from app.services.hh_search import HHSearchService
from app.services.prompts import PromptService
from app.services.request_query_planner import RequestQueryPlanner
from app.services.traffic_light_service import TrafficLightService

router = APIRouter()
_log = logging.getLogger(__name__)
def _run_query_generation(
    *,
    request_text: str,
    prompt_override: str | None,
    query_override: str | None,
) -> tuple[str, Any | None, list[tuple[str, str]], list[dict[str, Any]], datetime, datetime]:
    """Генерация или подстановка булевых запросов; возвращает (queries, llm_raw, started_at, bool_finished_at)."""
    if not (request_text or "").strip() and not (query_override or "").strip():
        raise HTTPException(status_code=400, detail="request_text is required (use /api/default_request button in UI if needed)")
    started_at = datetime.utcnow()
    trace_step(
        _log,
        "workflow",
        "_run_query_generation.start",
        has_query_override=(query_override is not None),
        request_text_preview=(request_text or "")[:500],
    )
    if query_override is not None:
        q = str(query_override or "").strip()
        trace_step(_log, "workflow", "_run_query_generation.override_query", query_len=len(q))
        plan = [
            ("Этап override 1", q),
        ]
        plan = [(k, v) for k, v in plan if v]
        meta = [{"stage": k, "query": v} for k, v in plan]
        return q, None, plan, meta, started_at, started_at

    # Новая логика из task.txt: разбивка запроса на блоки и комбинаторика.
    planner = RequestQueryPlanner(
        llm_url=settings.llm_url,
        llm_token_param=settings.llm_token_param,
    )
    planned = planner.build(request_text, prompt_override=prompt_override)
    query = planned.query
    llm_raw = planned.llm_raw
    bool_finished_at = datetime.utcnow()
    trace_step(
        _log,
        "workflow",
        "_run_query_generation.llm_done",
        query_len=len(query or ""),
        llm_raw_is_none=llm_raw is None,
    )
    return query, llm_raw, planned.search_plan, planned.search_plan_meta, started_at, bool_finished_at


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
                    "skills_text": it.get("skills_text"),
                    "education": it.get("education") if isinstance(it.get("education"), list) else None,
                    "contacts_opened": bool(it.get("contacts_opened")),
                }
            )
        candidates_by_level[level] = norm
    return candidates_by_level


@router.get("/default_request", response_class=PlainTextResponse)
def default_request() -> str:
    trace_step(_log, "workflow", "default_request")
    return PromptService().get_default_request_text()


@router.get("/resumes/{resume_id}/pdf")
async def download_resume_pdf(resume_id: str):
    import asyncio

    rid = str(resume_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="resume_id is required")
    if resume_pdf_exists(rid):
        trace_step(_log, "workflow", "download_resume_pdf.cache_hit", resume_id=rid)
        return FileResponse(
            resume_pdf_path(rid),
            media_type="application/pdf",
            filename=f"resume_{rid}.pdf",
        )

    hh = HHSearchService(token_url=settings.hh_token_url, token_source=settings.token_source)
    trace_step(_log, "workflow", "download_resume_pdf.fetch", resume_id=rid)
    ok = await asyncio.to_thread(hh.hh.download_resume_pdf, rid)
    if not ok or not resume_pdf_exists(rid):
        raise HTTPException(status_code=502, detail="Failed to download PDF from HH")

    return FileResponse(
        resume_pdf_path(rid),
        media_type="application/pdf",
        filename=f"resume_{rid}.pdf",
    )


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
    request_text = payload.request_text or ""
    trace_step(
        _log,
        "workflow",
        "generate_queries",
        request_text_preview=(request_text or "")[:300],
        has_query_override=payload.query_override is not None,
    )
    query, llm_raw, _, _, _, _ = _run_query_generation(
        request_text=request_text,
        prompt_override=payload.prompt_override,
        query_override=payload.query_override,
    )
    return GenerateQueriesResponse(llm_raw=llm_raw, query=query)


def _run_search_with_restarts(
    *,
    payload: SearchRequest,
    request_text: str,
    area_ids: list[int],
) -> tuple[
    str,
    Any | None,
    int,
    list[dict[str, Any]],
    str,
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
    query, llm_raw, search_plan, search_plan_meta, started_at, bool_finished_at = _run_query_generation(
        request_text=request_text,
        prompt_override=payload.prompt_override,
        query_override=payload.query_override,
    )
    found_count, candidates_raw, final_boolean_query, final_search_url, stage_attempts = hh.search_counts_and_candidates(
        query,
        search_plan=search_plan,
        search_plan_meta=search_plan_meta,
        source_text=request_text,
        area_ids=area_ids,
        per_page=min(200, int(payload.candidates_limit) * 3),
        min_needed=int(payload.candidates_limit),
    )
    if hh.hh.last_request_error and not candidates_raw:
        raise HTTPException(
            status_code=502,
            detail=(
                "Не удалось подключиться к HH API (проверьте интернет и настройки прокси). "
                f"Причина: {hh.hh.last_request_error}"
            ),
        )
    hh_finished_at = datetime.utcnow()
    total_iterations = len(stage_attempts)
    prompt_restarts = 0
    return (
        query,
        llm_raw,
        found_count,
        candidates_raw,
        final_boolean_query,
        final_search_url,
        stage_attempts,
        started_at,
        bool_finished_at,
        hh_finished_at,
        total_iterations,
        prompt_restarts,
    )


def _extract_skills_from_resume(resume_data: dict[str, Any]) -> list[str]:
    skill_set = resume_data.get("skill_set")
    if isinstance(skill_set, list):
        names = [str(s.get("name")).strip() for s in skill_set if isinstance(s, dict) and s.get("name")]
        if names:
            return names
    skills = resume_data.get("skills")
    if isinstance(skills, list):
        return [str(s).strip() for s in skills if str(s).strip()]
    return []


def _contact_item_text(item: dict[str, Any]) -> str | None:
    text = item.get("contact_value")
    if isinstance(text, str) and text.strip():
        return text.strip()
    value = item.get("value")
    if isinstance(value, dict):
        formatted = value.get("formatted") or value.get("number")
        if formatted:
            return str(formatted)
    elif value:
        return str(value)
    return None


def _contact_item_type_id(item: dict[str, Any]) -> str:
    ctype = item.get("type")
    if isinstance(ctype, dict):
        return str(ctype.get("id") or "").lower()
    return str(ctype or "").lower()


def _resume_has_contacts(resume_data: dict[str, Any]) -> bool:
    contact = resume_data.get("contact")
    if isinstance(contact, list):
        for item in contact:
            if isinstance(item, dict) and _contact_item_text(item):
                return True
    return bool(resume_data.get("phone") or resume_data.get("email"))


def _merge_candidate_with_full_resume(search_item: dict[str, Any], resume_data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(search_item)
    merged["experience_full"] = _normalize_full_experience(resume_data)
    skills = _extract_skills_from_resume(resume_data)
    if skills:
        merged["skills"] = skills
    skills_text = resume_data.get("skills")
    if isinstance(skills_text, str) and skills_text.strip():
        merged["skills_text"] = skills_text.strip()
    education = resume_data.get("education")
    if isinstance(education, list):
        merged["education"] = [x for x in education if isinstance(x, dict)]
    for key in ("first_name", "last_name", "title", "age", "area", "salary"):
        val = resume_data.get(key)
        if val is not None and val != "":
            merged[key] = val
    merged["contacts_opened"] = _resume_has_contacts(resume_data)
    return merged


def _extract_contacts_from_resume(resume_data: dict[str, Any]) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    phone: str | None = None
    email: str | None = None
    raw: list[dict[str, Any]] = []
    contact = resume_data.get("contact")
    if isinstance(contact, list):
        for item in contact:
            if not isinstance(item, dict):
                continue
            raw.append(item)
            text = _contact_item_text(item)
            if not text:
                continue
            type_id = _contact_item_type_id(item)
            kind = str(item.get("kind") or "").lower()
            if not email and (kind == "email" or type_id == "email"):
                email = text
            elif not phone and (
                kind == "phone" or type_id in {"cell", "home", "work", "phone"}
            ):
                phone = text
    if not phone and resume_data.get("phone"):
        phone = str(resume_data.get("phone"))
    if not email and resume_data.get("email"):
        email = str(resume_data.get("email"))
    return phone, email, raw


async def _fetch_full_resumes_raw(
    hh: HHSearchService,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Бесплатный просмотр полных резюме HH; возвращает сырой JSON."""
    import asyncio

    trace_step(
        _log,
        "workflow",
        "_fetch_full_resumes_raw.start",
        count=len(candidates),
    )
    semaphore = asyncio.Semaphore(10)

    async def fetch_one(item: dict[str, Any]) -> dict[str, Any] | None:
        async with semaphore:
            cid = str(item.get("id") or "")
            if not cid:
                return None
            resume_data = await asyncio.to_thread(hh.hh.get_resume_by_id, cid)
            if isinstance(resume_data, dict) and resume_data:
                persist_resume(resume_id=cid, resume_json=resume_data)
                return {"id": cid, "resume_json": resume_data}
            return None

    results = await asyncio.gather(*(fetch_one(c) for c in candidates))
    out = [r for r in results if isinstance(r, dict)]
    trace_step(_log, "workflow", "_fetch_full_resumes_raw.done", count=len(out))
    return out


def _load_resume_json(resume_id: str) -> dict[str, Any] | None:
    try:
        cached = get_resume_store().get_resume_json(resume_id=str(resume_id))
    except Exception:
        cached = None
    return cached if isinstance(cached, dict) and cached else None


def _validate_session_candidate_ids(session, candidate_ids: list[str]) -> None:
    allowed = set(session.candidate_ids)
    unknown = [cid for cid in candidate_ids if str(cid) not in allowed]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"candidate_ids not in session: {unknown[:5]}",
        )


def _traffic_light_item_from_candidate(tl: TrafficLightCandidate) -> TrafficLightResultItem:
    return TrafficLightResultItem(
        id=str(tl.id),
        candidate_name=tl.candidate_name,
        title=tl.title,
        location=tl.location,
        color_score_percent=int(tl.color_score_percent),
        requirements=list(tl.requirements or []),
        llm_raw=tl.debug_llm_raw,
        prompt=tl.debug_prompt,
    )


@router.post("/search", response_model=SearchResponse, response_model_exclude_none=True)
async def search(payload: SearchRequest):
    request_text = payload.request_text or ""
    area_ids = payload.area_ids or [113, 16]
    trace_step(
        _log,
        "workflow",
        "search.start",
        area_ids=area_ids,
        candidates_limit=payload.candidates_limit,
        request_preview=(request_text or "")[:300],
    )

    (
        query,
        llm_raw,
        found_count,
        candidates_raw,
        final_boolean_query,
        final_search_url,
        stage_attempts,
        started_at,
        bool_finished_at,
        hh_finished_at,
        total_iterations,
        prompt_restarts,
    ) = _run_search_with_restarts(payload=payload, request_text=request_text, area_ids=area_ids)
    trace_step(_log, "workflow", "search.hh_done", found_count=found_count, collected=len(candidates_raw or []))

    hh = HHSearchService(token_url=settings.hh_token_url, token_source=settings.token_source)
    raw_candidates = await _fetch_full_resumes_raw(hh, candidates_raw or [])
    resumes_finished_at = datetime.utcnow()

    candidate_ids = [str(c["id"]) for c in raw_candidates if c.get("id")]
    session = create_session(
        request_text=request_text,
        area_ids=area_ids,
        candidates_limit=int(payload.candidates_limit),
        candidate_ids=candidate_ids,
    )

    return SearchResponse(
        session_id=session.session_id,
        llm_raw=llm_raw,
        query=final_boolean_query or query,
        found_count=found_count,
        candidates=[RawResumeCandidate(id=str(c["id"]), resume_json=c["resume_json"]) for c in raw_candidates],  # type: ignore[arg-type]
        started_at=started_at,
        bool_finished_at=bool_finished_at,
        hh_finished_at=resumes_finished_at,
        finished_at=resumes_finished_at,
        final_search_url=final_search_url,
        stage_attempts=stage_attempts,  # type: ignore[arg-type]
        total_iterations=total_iterations,
        prompt_restarts=prompt_restarts,
    )


def _pick_best_level_by_candidates(candidates_by_level_raw: dict[str, list[dict]]):
    counts = {k: len(v or []) for k, v in candidates_by_level_raw.items()}
    choice = max(counts, key=lambda k: counts.get(k, 0) or 0) if counts else "main"
    trace_step(_log, "workflow", "_pick_best_level_by_candidates", choice=choice, counts=counts)
    return choice


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
    request_text: str,
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

            resume_data = _load_resume_json(str(candidate_id))
            if not resume_data:
                resume_data = await asyncio.to_thread(hh.hh.get_resume_by_id, str(candidate_id))
            if not isinstance(resume_data, dict):
                trace_step(_log, "workflow", "tl_candidate.skip", candidate_id=str(candidate_id), reason="resume_empty")
                return None

            persist_scored_resume(resume_id=str(candidate_id), resume_json=resume_data)

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
                    request_text=request_text,
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
    request_text = payload.request_text or ""
    trace_step(_log, "workflow", "svetofor.start", request_preview=(request_text or "")[:300])
    area_ids = payload.area_ids or [113, 16]

    top_x = max(1, int(payload.candidates_limit))
    search_payload = payload.model_copy(update={"candidates_limit": top_x})
    (
        query,
        llm_raw,
        found_count,
        candidates_raw,
        final_boolean_query,
        final_search_url,
        stage_attempts,
        started_at,
        bool_finished_at,
        hh_finished_at,
        total_iterations,
        prompt_restarts,
    ) = _run_search_with_restarts(payload=search_payload, request_text=request_text, area_ids=area_ids)

    hh = HHSearchService(token_url=settings.hh_token_url, token_source=settings.token_source)
    candidates_by_level = _normalize_candidates_by_level({"main": candidates_raw or []})
    selected_list = candidates_by_level.get("main", []) or []
    candidates_for_tl = selected_list[:top_x]

    scored_candidates = await _collect_traffic_light_candidates(hh, request_text, candidates_for_tl)
    traffic_light_candidates = sorted(scored_candidates, key=lambda x: x.color_score_percent, reverse=True)[:top_x]

    scored_ids = {str(item.id) for item in traffic_light_candidates}
    kept_candidates = [c for c in selected_list if str(c.get("id") or "") in scored_ids]
    found_count = len(kept_candidates)

    finished_at = datetime.utcnow()
    return SvetoforResponse(
        llm_raw=llm_raw,
        query=final_boolean_query or query,
        found_count=found_count,
        candidates=kept_candidates,  # type: ignore[arg-type]
        started_at=started_at,
        bool_finished_at=bool_finished_at,
        hh_finished_at=hh_finished_at,
        finished_at=finished_at,
        final_search_url=final_search_url,
        stage_attempts=stage_attempts,  # type: ignore[arg-type]
        total_iterations=total_iterations,
        prompt_restarts=prompt_restarts,
        traffic_light_candidates=traffic_light_candidates,  # type: ignore[arg-type]
    )


@router.post("/traffic_light", response_model=TrafficLightFromCandidatesResponse, response_model_exclude_none=True)
async def traffic_light_from_candidates(payload: TrafficLightFromCandidatesRequest):
    """
    Этап 2: светофор по выбранным candidate_ids.
    request_text и резюме берутся из сессии этапа 1.
    """
    trace_step(
        _log,
        "workflow",
        "traffic_light_from_candidates.start",
        session_id=payload.session_id,
        candidate_ids=len(payload.candidate_ids or []),
    )
    try:
        session = require_session(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found") from None

    ids = [str(x) for x in payload.candidate_ids]
    _validate_session_candidate_ids(session, ids)

    hh = HHSearchService(token_url=settings.hh_token_url, token_source=settings.token_source)
    candidates_for_tl: list[dict[str, Any]] = []
    for cid in ids:
        resume_json = _load_resume_json(cid)
        if not resume_json:
            raise HTTPException(status_code=400, detail=f"resume not found for id={cid}")
        item = dict(resume_json)
        item["id"] = cid
        candidates_for_tl.append(item)

    scored_candidates = await _collect_traffic_light_candidates(hh, session.request_text, candidates_for_tl)
    traffic_light_candidates = sorted(
        _merge_traffic_light_with_source_candidates(candidates_for_tl, scored_candidates),
        key=lambda x: x.color_score_percent,
        reverse=True,
    )
    items = [_traffic_light_item_from_candidate(tl) for tl in traffic_light_candidates]
    persist_traffic_light_batch(
        session_id=session.session_id,
        items=[
            {
                "id": it.id,
                "candidate_name": it.candidate_name,
                "title": it.title,
                "location": it.location,
                "color_score_percent": it.color_score_percent,
                "requirements": [r.model_dump() for r in (it.requirements or [])],
            }
            for it in items
        ],
    )
    trace_step(_log, "workflow", "traffic_light_from_candidates.done", n=len(items))

    return TrafficLightFromCandidatesResponse(session_id=session.session_id, candidates=items)  # type: ignore[arg-type]


def _traffic_light_public_from_record(record) -> TrafficLightPublic:
    requirements = [
        TrafficLightRequirement(**req)
        for req in (record.requirements or [])
        if isinstance(req, dict)
    ]
    return TrafficLightPublic(
        id=record.resume_id,
        candidate_name=record.candidate_name,
        title=record.title,
        location=record.location,
        color_score_percent=int(record.color_score_percent or 0),
        requirements=requirements,
    )


@router.post("/contacts", response_model=ContactsResponse, response_model_exclude_none=True)
async def open_contacts(payload: ContactsRequest):
    """
    Этап 3: платное открытие контактов для candidate_ids из сессии.
    Возвращает светофор (без prompt/raw) и полное резюме HH с контактами.
    """
    trace_step(
        _log,
        "workflow",
        "open_contacts.start",
        session_id=payload.session_id,
        candidate_ids=len(payload.candidate_ids or []),
    )
    try:
        session = require_session(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found") from None

    ids = [str(x) for x in payload.candidate_ids]
    _validate_session_candidate_ids(session, ids)

    tl_by_id = get_traffic_light_store().get_for_session(session_id=session.session_id, resume_ids=ids)
    missing_tl = [cid for cid in ids if cid not in tl_by_id]
    if missing_tl:
        raise HTTPException(
            status_code=400,
            detail=f"traffic light not found for candidate_ids (run /api/traffic_light first): {missing_tl[:5]}",
        )

    hh = HHSearchService(token_url=settings.hh_token_url, token_source=settings.token_source)
    import asyncio

    semaphore = asyncio.Semaphore(6)

    async def process_one(cid: str) -> AddedCandidateItem:
        async with semaphore:
            tl_public = _traffic_light_public_from_record(tl_by_id[cid])
            if not cid:
                return AddedCandidateItem(
                    traffic_light=TrafficLightPublic(id="", candidate_name=None),
                    error="missing id",
                )
            resume_data = await asyncio.to_thread(hh.hh.get_resume_by_id, cid, with_contacts=True)
            if not isinstance(resume_data, dict) or not resume_data:
                err = hh.hh.last_contact_error or "failed to open contacts"
                return AddedCandidateItem(traffic_light=tl_public, error=err)
            persist_resume(resume_id=cid, resume_json=resume_data)
            return AddedCandidateItem(traffic_light=tl_public, resume_json=resume_data)

    results = await asyncio.gather(*(process_one(cid) for cid in ids))
    trace_step(_log, "workflow", "open_contacts.done", count=len(results))
    return ContactsResponse(session_id=session.session_id, candidates=list(results))

