from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import GenerateQueriesRequest, SearchRequest, normalize_level_queries


def test_normalize_level_queries_empty() -> None:
    assert normalize_level_queries(None) == {"Уровень 1": "", "Уровень 2": "", "Уровень 3": ""}


def test_normalize_level_queries_partial() -> None:
    out = normalize_level_queries({"Уровень 2": "only mid"})
    assert out["Уровень 2"] == "only mid"
    assert out["Уровень 1"] == ""


def test_generate_queries_requires_request_text_without_override() -> None:
    with pytest.raises(ValidationError):
        GenerateQueriesRequest(request_text="   ")


def test_generate_queries_allows_empty_text_with_override() -> None:
    req = GenerateQueriesRequest(
        request_text="",
        queries_override={"Уровень 1": "a", "Уровень 2": "b", "Уровень 3": "c"},
    )
    assert req.request_text == ""


def test_search_request_requires_text_without_override() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(request_text="")


def test_search_request_with_override() -> None:
    r = SearchRequest(
        request_text="",
        queries_override={"Уровень 1": "", "Уровень 2": "x", "Уровень 3": ""},
    )
    assert r.candidates_limit == 20
