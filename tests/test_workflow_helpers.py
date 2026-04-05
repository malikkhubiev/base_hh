from __future__ import annotations

from app.api.routes import workflow as wf


def test_pick_best_level_prefers_level3() -> None:
    raw = {
        "Уровень 1": [],
        "Уровень 2": [{"id": "a"}],
        "Уровень 3": [{"id": "b"}],
    }
    assert wf._pick_best_level_by_candidates(raw) == "Уровень 3"


def test_pick_best_level_fallback_level2() -> None:
    raw = {"Уровень 1": [], "Уровень 2": [], "Уровень 3": []}
    assert wf._pick_best_level_by_candidates(raw) == "Уровень 2"


def test_candidate_name() -> None:
    assert wf._candidate_name({"first_name": "Иван", "last_name": "Петров"}) == "Петров Иван"
    assert wf._candidate_name({"id": "99"}) == "99"


def test_extract_candidate_prj_exp() -> None:
    resume = {
        "experience": [
            {
                "start": "2020-01",
                "end": "2021-01",
                "company": "ACME",
                "position": "Dev",
                "description": "Did things",
            }
        ]
    }
    text = wf._extract_candidate_prj_exp(resume)
    assert "ACME" in text
    assert "Did things" in text
