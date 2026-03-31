from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, StreamingResponse

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

try:
    import io

    import xlsxwriter  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional dependency
    xlsxwriter = None  # type: ignore[assignment]


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


@router.post("/export_excel")
async def export_excel(payload: SearchRequest):
    """
    Генерация Excel по итогам поиска/светофора.
    Если библиотека xlsxwriter недоступна, вернём 500.
    """
    if xlsxwriter is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="xlsxwriter is not installed on server")

    started_at = datetime.utcnow()

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
    bool_finished_at = datetime.utcnow()

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

    # Плоский список кандидатов HH для таблицы.
    hh_candidates: list[dict] = []
    for items in candidates_by_level_raw.values():
        for it in items or []:
            if isinstance(it, dict):
                hh_candidates.append(it)

    # По желанию пользователя можем прогреть светофор, чтобы заполнить лист "Кандидаты Светофор".
    traffic_light_candidates: list = []
    if payload.include_traffic_light and payload.traffic_light_candidates_for_excel:
        # Используем уже рассчитанный в UI список, чтобы данные в UI и Excel совпадали.
        traffic_light_candidates = list(payload.traffic_light_candidates_for_excel)
    elif payload.include_traffic_light and payload.svetofor_top_x and payload.svetofor_top_x > 0:
        # Похожая логика на обработчик /svetofor, но без деталей промпта.
        from app.services.traffic_light_service import TrafficLightService  # локальный импорт, чтобы не плодить циклы

        traffic_light_service = TrafficLightService()
        selected_level = _pick_best_level_by_candidates(
            {
                k: (v or [])
                for k, v in candidates_by_level_raw.items()
                if isinstance(v, list)
            }
        )
        selected_list = candidates_by_level_raw.get(selected_level, []) or []

        import asyncio

        semaphore = asyncio.Semaphore(10)
        top_x = max(1, int(payload.svetofor_top_x))
        candidates_for_tl = selected_list[:top_x]

        async def process_one_candidate(c: dict) -> object | None:
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
        traffic_light_candidates = [r for r in results if r is not None]

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
    duration_sec = (finished_at - started_at).total_seconds()
    bool_duration_sec = (bool_finished_at - started_at).total_seconds()
    hh_duration_sec = (hh_finished_at - bool_finished_at).total_seconds()
    tl_duration_sec = (finished_at - hh_finished_at).total_seconds() if payload.include_traffic_light else 0.0

    # Формирование Excel.
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})

    # Лист "Запрос"
    sheet_req = workbook.add_worksheet("Запрос")
    bold = workbook.add_format({"bold": True})
    tl_green_fmt = workbook.add_format({"bg_color": "#DDF8E7", "border": 1, "align": "center"})
    tl_yellow_fmt = workbook.add_format({"bg_color": "#FEEAC3", "border": 1, "align": "center"})
    tl_red_fmt = workbook.add_format({"bg_color": "#FFB3B3", "border": 1, "align": "center"})

    row = 0
    sheet_req.write(row, 0, "Запрос:", bold)
    sheet_req.write(row, 1, payload.request_text or "")
    row += 2

    total_found = sum(int(v or 0) for v in (found_counts or {}).values())
    sheet_req.write(row, 0, "Кандидатов в выборке:", bold)
    sheet_req.write(row, 1, total_found)
    row += 1

    sheet_req.write(row, 0, "Общее время выполнения:", bold)
    sheet_req.write(
        row,
        1,
        f"{int(duration_sec // 60)} min {int(duration_sec % 60)} s | "
        f"{started_at.strftime('%d.%m.%Y %H:%M:%S')} ... {finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
    )
    row += 2

    sheet_req.write(row, 0, "Время выполнения булевого запроса:", bold)
    sheet_req.write(
        row,
        1,
        f"{int(bool_duration_sec // 60)} min {int(bool_duration_sec % 60)} s | "
        f"{started_at.strftime('%d.%m.%Y %H:%M:%S')} ... {bool_finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
    )
    row += 1
    sheet_req.write(row, 0, "Время поиска в HH.ru:", bold)
    sheet_req.write(
        row,
        1,
        f"{int(hh_duration_sec // 60)} min {int(hh_duration_sec % 60)} s | "
        f"{bool_finished_at.strftime('%d.%m.%Y %H:%M:%S')} ... {hh_finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
    )
    row += 1
    sheet_req.write(row, 0, "Время построения Светофора:", bold)
    if payload.include_traffic_light:
        sheet_req.write(
            row,
            1,
            f"{int(tl_duration_sec // 60)} min {int(tl_duration_sec % 60)} s | "
            f"{hh_finished_at.strftime('%d.%m.%Y %H:%M:%S')} ... {finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
        )
    else:
        sheet_req.write(
            row,
            1,
            f"0 min 0 s | {hh_finished_at.strftime('%d.%m.%Y %H:%M:%S')} ... {hh_finished_at.strftime('%d.%m.%Y %H:%M:%S')} "
            f"(не выполнялось)",
        )
    row += 2

    # Лист "Кандидаты HH"
    if hh_candidates:
        sheet_hh = workbook.add_worksheet("Кандидаты HH")
        first_keys = [
            "id",
            "first_name",
            "last_name",
            "title",
            "alternate_url",
            "url",
            "age",
            "area",
            "salary",
            "experience",
            "skills",
            "tags",
            "created_at",
            "updated_at",
        ]
        all_keys: list[str] = []
        seen: set[str] = set()
        for k in first_keys:
            if k == "employer":
                continue
            if any(isinstance(c, dict) and k in c for c in hh_candidates):
                all_keys.append(k)
                seen.add(k)
        for c in hh_candidates:
            if not isinstance(c, dict):
                continue
            for k in c.keys():
                if k == "employer" or k in seen:
                    continue
                all_keys.append(k)
                seen.add(k)
        headers = all_keys
        for col, h in enumerate(headers):
            sheet_hh.write(0, col, h, bold)
        r = 1
        for c in hh_candidates:
            for col, key in enumerate(headers):
                val = c.get(key)
                if val is None:
                    out = ""
                elif isinstance(val, (dict, list)):
                    out = json.dumps(val, ensure_ascii=False)
                else:
                    out = str(val)
                sheet_hh.write(r, col, out)
            r += 1

    # Лист "Светофор"
    if traffic_light_candidates:
        sheet_tl = workbook.add_worksheet("Светофор")
        headers_tl = ["Кандидат", "Локация", "Позиция", "Ссылка", "Итог +"]
        for col, h in enumerate(headers_tl):
            sheet_tl.write(0, col, h, bold)
        r = 1
        for c in traffic_light_candidates:
            name = getattr(c, "candidate_name", "") or getattr(c, "id", "")
            location = getattr(c, "location", "") or ""
            title = getattr(c, "title", "") or ""
            resume_url = getattr(c, "resume_url", "") or ""
            score_raw = getattr(c, "color_score_percent", 0) or 0
            try:
                score = float(score_raw)
            except (TypeError, ValueError):
                score = 0.0
            score_percent = f"{int(round(score))}%"
            sheet_tl.write(r, 0, str(name))
            sheet_tl.write(r, 1, str(location))
            sheet_tl.write(r, 2, str(title))
            sheet_tl.write(r, 3, resume_url)
            if score >= 60:
                score_fmt = tl_green_fmt
            elif score >= 40:
                score_fmt = tl_yellow_fmt
            else:
                score_fmt = tl_red_fmt
            sheet_tl.write(r, 4, score_percent, score_fmt)
            r += 1

    workbook.close()
    output.seek(0)

    filename = f"hh_search_{started_at.strftime('%Y%m%d_%H%M%S')}.xlsx"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return StreamingResponse(output, media_type=headers["Content-Type"], headers=headers)

