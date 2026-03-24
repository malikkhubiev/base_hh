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

    area_id: int | None = None
    professional_roles: list[str] | None = None
    system_prompt_override: str | None = None
    user_prompt_override: str | None = None

    mock_llm: bool = False
    mock_hh: bool = False


class SearchResponse(BaseModel):
    llm_raw: Any | None = None
    queries: dict[LevelName, str]
    queries_with_exclusions: dict[LevelName, str]
    found_counts: dict[LevelName, int]
    selected_level: LevelName
    token_source_used: TokenSource
    candidates_by_level: dict[LevelName, list[Candidate]]

