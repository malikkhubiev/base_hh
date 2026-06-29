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
    error: str | None = None


class SearchRequest(BaseModel):
    request_text: str = Field(
        default="",
        description="Квалификационные требования для LLM и светофора.",
    )
    candidates_limit: int = Field(
        10,
        ge=1,
        le=200,
        description="Требуется кандидатов; поиск идёт до N×3 с одного булевого запроса",
    )
    area_ids: list[int] = Field(
        default_factory=lambda: [113, 16],
        description="Регионы HH (по умолчанию Россия 113 и Беларусь 16).",
    )
    prompt_override: str | None = Field(
        None,
        description="Если задано, используем этот текст промпта вместо system+user шаблонов.",
    )
    query_override: str | None = Field(
        None,
        description="Готовый булевый запрос; если задано, шаг генерации через LLM пропускается.",
    )


class RawResumeCandidate(BaseModel):
    id: str
    resume_json: dict[str, Any] = Field(description="Сырой JSON полного резюме HH (без контактов).")


class SearchResponse(BaseModel):
    session_id: str
    llm_raw: Any | None = None
    query: str = ""
    found_count: int = 0
    candidates: list[RawResumeCandidate] = Field(default_factory=list)
    started_at: datetime | None = None
    bool_finished_at: datetime | None = None
    hh_finished_at: datetime | None = None
    finished_at: datetime | None = None
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
    session_id: str = Field(description="Сессия этапа 1 (request_text и резюме на бэкенде)")
    candidate_ids: list[str] = Field(default_factory=list, description="ID выбранных кандидатов")

    @model_validator(mode="after")
    def _require_ids(self) -> Self:
        if not self.candidate_ids:
            raise ValueError("candidate_ids is required")
        if not (self.session_id or "").strip():
            raise ValueError("session_id is required")
        return self


class TrafficLightResultItem(BaseModel):
    id: str
    candidate_name: str | None = None
    title: str | None = None
    location: str | None = None
    color_score_percent: int = Field(ge=0, le=100, default=0)
    requirements: list[TrafficLightRequirement] = Field(default_factory=list)
    llm_raw: Any | None = None
    prompt: str | None = None


class TrafficLightFromCandidatesResponse(BaseModel):
    session_id: str
    candidates: list[TrafficLightResultItem] = Field(default_factory=list)


class CandidateContact(BaseModel):
    id: str
    candidate_name: str
    phone: str | None = None
    email: str | None = None
    contacts: list[dict[str, Any]] = Field(default_factory=list, description="Сырой массив contact[] из HH")
    error: str | None = None


class ContactsRequest(BaseModel):
    session_id: str = Field(description="Сессия этапа 1")
    candidate_ids: list[str] = Field(default_factory=list, description="ID выбранных кандидатов для открытия контактов")

    @model_validator(mode="after")
    def _require_ids(self) -> Self:
        if not self.candidate_ids:
            raise ValueError("candidate_ids is required")
        if not (self.session_id or "").strip():
            raise ValueError("session_id is required")
        return self


class ContactsResponse(BaseModel):
    session_id: str
    contacts: list[CandidateContact]

