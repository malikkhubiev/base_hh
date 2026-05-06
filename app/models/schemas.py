from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Self

from pydantic import BaseModel, Field, model_validator


def normalize_level_queries(override: Mapping[str, str] | None) -> dict[str, str]:
    """Совместимость: приводим override к словарю запросов (ключ 'Основной')."""
    base: dict[str, str] = {"Основной": ""}
    if not override:
        return base
    for k in base:
        if k in override and override[k] is not None:
            base[k] = str(override[k])
    return base


class GenerateQueriesRequest(BaseModel):
    request_text: str = Field(
        default="",
        description="Текст требований для LLM; при передаче queries_override может быть пустым.",
    )
    system_prompt_override: str | None = None
    user_prompt_override: str | None = None
    queries_override: dict[str, str] | None = Field(
        None,
        description="Если задано, LLM не вызывается; возвращаются эти булевы запросы (без генерации).",
    )

class GenerateQueriesResponse(BaseModel):
    llm_raw: Any | None = None
    queries: dict[str, str]


class Candidate(BaseModel):
    id: str | None = None
    title: str | None = None
    url: str | None = None
    alternate_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    age: int | None = None
    area: Any | None = None
    employer: Any | None = None
    salary: Any | None = None
    experience: Any | None = None
    experience_full: list[dict[str, Any]] | None = Field(
        default=None,
        description="Полный список опыта из HH resume (start/end/company/position/industries/etc).",
    )
    skills: list[Any] = Field(default_factory=list)
    tags: list[Any] = Field(default_factory=list)
    first_name: str | None = None
    last_name: str | None = None


class AppliedRequirement(BaseModel):
    block: str
    expression: str


class SearchStageAttempt(BaseModel):
    stage: str
    query: str
    query_with_exclusion: str
    found: int
    collected: int
    target: int
    enough: bool
    web_url: str | None = None


class SearchRequest(BaseModel):
    request_text: str = Field(
        default="",
        description="Текст вакансии/требований; для LLM и контекста HH. При queries_override может быть пустым.",
    )
    candidates_limit: int = Field(20, ge=1, le=200, description="Минимум кандидатов: ищем до тех пор, пока не соберём минимум (в UI показываем до N*3)")

    area_id: int | None = None
    system_prompt_override: str | None = None
    user_prompt_override: str | None = None
    queries_override: dict[str, str] | None = Field(
        None,
        description="Готовые булевы запросы по уровням; если задано, шаг генерации через LLM пропускается.",
    )

    # NOTE: job_stability and svetofor_top_x are removed per task.txt.
class SearchResponse(BaseModel):
    llm_raw: Any | None = None
    queries: dict[str, str]
    queries_with_exclusions: dict[str, str]
    hh_search_urls: dict[str, str] = Field(
        default_factory=dict,
        description="Ссылки на веб-поиск HH с теми же параметрами, что использовались в API.",
    )
    found_count: int = 0
    candidates: list[Candidate] = Field(default_factory=list)
    started_at: datetime | None = None
    bool_finished_at: datetime | None = None
    hh_finished_at: datetime | None = None
    finished_at: datetime | None = None
    final_boolean_query: str | None = None
    final_search_url: str | None = None
    stage_attempts: list[SearchStageAttempt] = Field(default_factory=list)
    total_iterations: int = 0
    prompt_restarts: int = 0


class SvetoforResponse(BaseModel):
    llm_raw: Any | None = None
    queries: dict[str, str]
    queries_with_exclusions: dict[str, str]
    hh_search_urls: dict[str, str] = Field(default_factory=dict)
    found_count: int = 0
    candidates: list[Candidate] = Field(default_factory=list)
    started_at: datetime | None = None
    bool_finished_at: datetime | None = None
    hh_finished_at: datetime | None = None
    finished_at: datetime | None = None
    final_boolean_query: str | None = None
    final_search_url: str | None = None
    stage_attempts: list[SearchStageAttempt] = Field(default_factory=list)
    total_iterations: int = 0
    prompt_restarts: int = 0

    traffic_light_candidates: list[TrafficLightCandidate] = Field(default_factory=list)


class TrafficLightRequirement(BaseModel):
    requirement: str
    resume_evidence: str
    match_percent: int = Field(ge=0, le=100)
    difference_comment: str


class TrafficLightCandidate(BaseModel):
    id: str
    candidate_name: str
    title: str | None = None
    location: str | None = None
    resume_url: str | None = None
    color_score_percent: int = Field(ge=0, le=100)
    requirements: list[TrafficLightRequirement]

    # Debug fields: нужны, чтобы выяснять, почему "Светофор" пустой.
    # Показываем в UI итоговый промпт, который отправили в LLM, и raw-ответ LLM.
    candidate_prj_exp: str | None = None
    experience_full: list[dict[str, Any]] | None = Field(
        default=None,
        description="Полный список опыта из HH resume (start/end/company/position/industries/etc).",
    )
    debug_prompt: str | None = None
    debug_llm_raw: Any | None = None


class TrafficLightFromCandidatesRequest(BaseModel):
    """
    Запрос для расчёта "Светофора" без повторного запуска булевых запросов и поиска в HH.
    UI передаёт уже найденных кандидатов (по уровню), а сервер догружает резюме по id и считает ColorScore.
    """

    request_text: str = Field(description="Текст вакансии/требований для LLM")
    candidates: list[Candidate] = Field(default_factory=list, description="Кандидаты, уже найденные в поиске")

    @model_validator(mode="after")
    def _require_text(self) -> Self:
        if not (self.request_text or "").strip():
            raise ValueError("request_text is required")
        return self


class TrafficLightFromCandidatesResponse(BaseModel):
    traffic_light_candidates: list[TrafficLightCandidate]


class GeneralRequirementsCandidateResult(BaseModel):
    id: str
    candidate_name: str
    review_text: str
    checks: list[dict[str, Any]] | None = Field(
        default=None,
        description="Чистый JSON (после очистки markdown) со списком проверок: [ok(bool), requirement, evidence].",
    )
    debug_prompt: str | None = None
    debug_llm_raw: Any | None = None


class ScreeningRequest(BaseModel):
    request_text: str = Field(description="Текст вакансии/требований (для светофора)")
    general_requirements_text: str = Field(default="", description="Общие требования (вставляются в ${custReqText})")
    candidates: list[Candidate] = Field(default_factory=list, description="Выбранные кандидаты из таблицы поиска")

    @model_validator(mode="after")
    def _require_candidates(self) -> Self:
        if not self.candidates:
            raise ValueError("candidates is required")
        return self


class ScreeningResponse(BaseModel):
    traffic_light_candidates: list[TrafficLightCandidate]
    general_requirements: list[GeneralRequirementsCandidateResult]



