from __future__ import annotations

from typing import Any, Literal, Mapping, Self

from pydantic import BaseModel, Field, model_validator


LevelName = Literal["Уровень 1", "Уровень 2", "Уровень 3"]
TokenSource = Literal["ssp"]


def normalize_level_queries(override: Mapping[str, str] | None) -> dict[LevelName, str]:
    """Приводит переданные булевы запросы к полному набору уровней (пустые строки для отсутствующих)."""
    base: dict[LevelName, str] = {"Уровень 1": "", "Уровень 2": "", "Уровень 3": ""}
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
    queries_override: dict[LevelName, str] | None = Field(
        None,
        description="Если задано, LLM не вызывается; возвращаются эти булевы запросы (без генерации).",
    )

    @model_validator(mode="after")
    def _require_text_unless_override(self) -> Self:
        if self.queries_override is not None:
            return self
        if not (self.request_text or "").strip():
            raise ValueError("request_text is required when queries_override is not set")
        return self


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
    first_name: str | None = None
    last_name: str | None = None


class SearchRequest(BaseModel):
    request_text: str = Field(
        default="",
        description="Текст вакансии/требований; для LLM и контекста HH. При queries_override может быть пустым.",
    )
    selected_level: LevelName = "Уровень 2"
    candidates_limit: int = Field(20, ge=1, le=200, description="Кол-во кандидатов в таблице")

    area_id: int | None = None
    professional_roles: list[str] | None = None
    system_prompt_override: str | None = None
    user_prompt_override: str | None = None
    queries_override: dict[LevelName, str] | None = Field(
        None,
        description="Готовые булевы запросы по уровням; если задано, шаг генерации через LLM пропускается.",
    )
    include_excel: bool = Field(
        False,
        description="Если true, к JSON добавляется excel_base64 (+ excel_filename). По умолчанию только JSON.",
    )

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
    include_traffic_light: bool = Field(
        False,
        description="Включать расчёт и лист Светофора в Excel (только если пользователь запускал кнопку Светофор)",
    )
    traffic_light_candidates_for_excel: list[TrafficLightCandidate] | None = Field(
        default=None,
        description="Готовые кандидаты Светофора из UI для экспорта в Excel без повторного пересчёта",
    )

    @model_validator(mode="after")
    def _require_text_unless_queries_override(self) -> Self:
        if self.queries_override is not None:
            return self
        if not (self.request_text or "").strip():
            raise ValueError("request_text is required when queries_override is not set")
        return self


class SearchResponse(BaseModel):
    llm_raw: Any | None = None
    queries: dict[LevelName, str]
    queries_with_exclusions: dict[LevelName, str]
    hh_search_urls: dict[LevelName, str] = Field(
        default_factory=dict,
        description="Ссылки на веб-поиск HH с теми же параметрами, что использовались в API.",
    )
    found_counts: dict[LevelName, int]
    selected_level: LevelName
    token_source_used: TokenSource
    candidates_by_level: dict[LevelName, list[Candidate]]
    excel_base64: str | None = Field(None, description="Заполняется при include_excel=true")
    excel_filename: str | None = None


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
    hh_search_urls: dict[LevelName, str] = Field(
        default_factory=dict,
        description="Ссылки на веб-поиск HH с теми же параметрами, что использовались в API.",
    )
    found_counts: dict[LevelName, int]
    selected_level: LevelName
    token_source_used: TokenSource
    candidates_by_level: dict[LevelName, list[Candidate]]

    # Кандидаты, отсортированные по ColorScore (пока для теста может быть <= 1).
    traffic_light_candidates: list[TrafficLightCandidate]
    excel_base64: str | None = Field(None, description="Заполняется при include_excel=true")
    excel_filename: str | None = None


class TrafficLightFromCandidatesRequest(BaseModel):
    """
    Запрос для расчёта "Светофора" без повторного запуска булевых запросов и поиска в HH.
    UI передаёт уже найденных кандидатов (по уровню), а сервер догружает резюме по id и считает ColorScore.
    """

    request_text: str = Field(description="Текст вакансии/требований для LLM")
    selected_level: LevelName = "Уровень 2"
    candidates: list[Candidate] = Field(default_factory=list, description="Кандидаты, уже найденные в поиске")

    # Filter params for "job stability" stage in traffic light.
    min_stay_months: int = Field(3, ge=1, le=240)
    allowed_short_jobs: int = Field(2, ge=0, le=50)
    jump_mode: Literal["consecutive", "total"] = "consecutive"
    max_not_employed_months: int = Field(6, ge=0, le=240)

    # How many first candidates to process by traffic light.
    svetofor_top_x: int = Field(20, ge=1, le=200)

    @model_validator(mode="after")
    def _require_text(self) -> Self:
        if not (self.request_text or "").strip():
            raise ValueError("request_text is required")
        return self


class TrafficLightFromCandidatesResponse(BaseModel):
    selected_level: LevelName
    traffic_light_candidates: list[TrafficLightCandidate]


class ExportExcelUiRequest(BaseModel):
    """
    Запрос для экспорта Excel без повторного поиска в HH:
    UI передаёт уже полученные данные (queries/urls/counts/candidates) + светофоры (если были).
    """

    request_text: str = Field(default="", description="Текст вакансии/требований")
    selected_level: LevelName = "Уровень 2"

    queries: dict[LevelName, str] = Field(default_factory=lambda: normalize_level_queries(None))
    queries_with_exclusions: dict[LevelName, str] = Field(default_factory=lambda: normalize_level_queries(None))
    hh_search_urls: dict[LevelName, str] = Field(default_factory=dict)
    found_counts: dict[LevelName, int] = Field(default_factory=dict)
    candidates_by_level: dict[LevelName, list[Candidate]] = Field(default_factory=dict)

    # Светофоры, которые уже были рассчитаны в UI (по уровням).
    traffic_lights_by_level: dict[LevelName, list[TrafficLightCandidate]] | None = None

    @model_validator(mode="after")
    def _require_text(self) -> Self:
        if not (self.request_text or "").strip():
            raise ValueError("request_text is required")
        return self

