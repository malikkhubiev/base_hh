from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Self

from pydantic import BaseModel, Field, model_validator


class GenerateQueriesRequest(BaseModel):
    request_text: str = Field(
        default="",
        description="Текст требований для LLM; при передаче queries_override может быть пустым.",
    )
    prompt_override: str | None = Field(
        None,
        description="Если задано, используем этот текст промпта вместо system+user шаблонов. Можно использовать {vac_reqs}.",
    )
    query_override: str | None = Field(
        None,
        description="Если задано, LLM не вызывается; возвращается этот булевый запрос (без генерации).",
    )

class GenerateQueriesResponse(BaseModel):
    llm_raw: Any | None = None
    query: str = ""


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
    skills_text: str | None = Field(
        default=None,
        description="Текстовое описание навыков из полного резюме HH (поле skills).",
    )
    education: list[dict[str, Any]] | None = Field(
        default=None,
        description="Образование из полного резюме HH.",
    )
    contacts_opened: bool = Field(
        default=False,
        description="True если контакты уже открыты (платно) и доступны в кэше.",
    )


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
    candidates_limit: int = Field(10, ge=1, le=200, description="Необходимое кол-во кандидатов; поиск идёт до N×3 с одного булевого запроса")

    area_id: int | None = None
    prompt_override: str | None = Field(
        None,
        description="Если задано, используем этот текст промпта вместо system+user шаблонов. Можно использовать {vac_reqs}.",
    )
    query_override: str | None = Field(
        None,
        description="Готовый булевый запрос; если задано, шаг генерации через LLM пропускается.",
    )

    # NOTE: job_stability and svetofor_top_x are removed per task.txt.
class SearchResponse(BaseModel):
    llm_raw: Any | None = None
    query: str = ""
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
    query: str = ""
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


class CandidateContact(BaseModel):
    id: str
    candidate_name: str
    phone: str | None = None
    email: str | None = None
    contacts: list[dict[str, Any]] = Field(default_factory=list, description="Сырой массив contact[] из HH")
    error: str | None = None


class ContactsRequest(BaseModel):
    candidates: list[Candidate] = Field(default_factory=list, description="Выбранные кандидаты для платного открытия контактов")

    @model_validator(mode="after")
    def _require_candidates(self) -> Self:
        if not self.candidates:
            raise ValueError("candidates is required")
        return self


class ContactsResponse(BaseModel):
    contacts: list[CandidateContact]

