from __future__ import annotations

from app.clients.llm_client import LLMClient


def test_extract_queries_from_flat_response() -> None:
    c = LLMClient(llm_url="http://x", token_param="")
    raw = {
        "Уровень 1": "a",
        "Уровень 2": "b",
        "Уровень 3": "c",
    }
    out = c.extract_queries(raw)
    assert out == {"Уровень 1": "a", "Уровень 2": "b", "Уровень 3": "c"}


def test_extract_queries_nested_markdown() -> None:
    c = LLMClient(llm_url="http://x", token_param="")
    raw = {"markdown": {"Уровень 1": "x", "Уровень 2": "y", "Уровень 3": "z"}}
    out = c.extract_queries(raw)
    assert out["Уровень 2"] == "y"


def test_extract_queries_from_string_response() -> None:
    c = LLMClient(llm_url="http://x", token_param="")
    raw = {
        "response": '{"Уровень 1": "q1", "Уровень 2": "q2", "Уровень 3": "q3"}',
    }
    out = c.extract_queries(raw)
    assert out["Уровень 1"] == "q1"
