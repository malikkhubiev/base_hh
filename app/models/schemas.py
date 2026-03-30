from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


LevelName = Literal["Уровень 1", "Уровень 2", "Уровень 3"]
TokenSource = Literal["ssp"]


class GenerateQueriesRequest(BaseModel):
    request_text: str = Field(..., description="Текст требований/запроса пользователя")
    system_prompt_override: str | None = None
    user_prompt_override: str | None = None


class GenerateQueriesResponse(BaseModel):
    llm_raw: Any | None = None
    queries: dict[LevelName, str]


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
    skills: list[Any] = Field(default_factory=list)
    tags: list[Any] = Field(default_factory=list)


class SearchRequest(BaseModel):
    request_text: str
    selected_level: LevelName = "Уровень 2"
    candidates_limit: int = Field(20, ge=1, le=200, description="Кол-во кандидатов в таблице")

    area_id: int | None = None
    professional_roles: list[str] | None = None
    system_prompt_override: str | None = None
    user_prompt_override: str | None = None

    # Filter params for "job stability" stage in traffic light.
    min_stay_months: int = Field(3, ge=1, le=240, description="Минимальный срок работы на одном месте (мес)")
    allowed_short_jobs: int = Field(
        2, ge=0, le=50, description="Разрешённое кол-во мест работы, где длительность < min_stay_months"
    )
    jump_mode: Literal["consecutive", "total"] = Field(
        "consecutive",
        description='Режим "прыгуна": consecutive = отсекать по подряд коротким, total = отсекать по общему числу коротких',
    )
    max_not_employed_months: int = Field(
        6,
        ge=0,
        le=240,
        description="Максимум не в деле (мес): если end последнего места работы старше этого — кандидат не берётся",
    )

    # How many first candidates to process by traffic light.
    svetofor_top_x: int = Field(20, ge=1, le=200, description="Первые X кандидатов для вызова светофора")


class SearchResponse(BaseModel):
    llm_raw: Any | None = None
    queries: dict[LevelName, str]
    queries_with_exclusions: dict[LevelName, str]
    found_counts: dict[LevelName, int]
    selected_level: LevelName
    token_source_used: TokenSource
    candidates_by_level: dict[LevelName, list[Candidate]]


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
    debug_prompt: str | None = None
    debug_llm_raw: Any | None = None


class SvetoforResponse(BaseModel):
    llm_raw: Any | None = None
    queries: dict[LevelName, str]
    queries_with_exclusions: dict[LevelName, str]
    found_counts: dict[LevelName, int]
    selected_level: LevelName
    token_source_used: TokenSource
    candidates_by_level: dict[LevelName, list[Candidate]]

    # Кандидаты, отсортированные по ColorScore (пока для теста может быть <= 1).
    traffic_light_candidates: list[TrafficLightCandidate]

