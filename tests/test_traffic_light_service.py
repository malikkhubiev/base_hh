from __future__ import annotations

import json

from app.models.schemas import TrafficLightRequirement
from app.services.traffic_light_service import TrafficLightService


def _build_llm_raw_fixture() -> dict:
    # The service expects a possible shape like:
    # { "response": { "markdown": { "requirements": { "items": [...] } } } }
    items = [
        {"requirement": "r1", "resume_evidence": "", "match_percent": 60, "difference_comment": ""},
        *[
            {"requirement": f"r{i}", "resume_evidence": "", "match_percent": 0, "difference_comment": ""}
            for i in range(2, 10)
        ],
    ]
    return {
        "response": {"markdown": {"requirements": {"items": items}}},
        # Some LLM wrappers might include extra fields; the parser is resilient.
        "meta": {"ok": True},
    }

def _build_llm_raw_fixture_with_match_percent(match_percent) -> dict:
    items = [
        {
            "requirement": "r1",
            "resume_evidence": "",
            "match_percent": match_percent,
            "difference_comment": "",
        },
        *[
            {"requirement": f"r{i}", "resume_evidence": "", "match_percent": 0, "difference_comment": ""}
            for i in range(2, 10)
        ],
    ]
    return {"response": {"markdown": {"requirements": {"items": items}}}}

def _build_llm_raw_fixture_markdown_string() -> dict:
    items = [
        {"requirement": "r1", "resume_evidence": "", "match_percent": 60, "difference_comment": ""},
        *[
            {"requirement": f"r{i}", "resume_evidence": "", "match_percent": 0, "difference_comment": ""}
            for i in range(2, 10)
        ],
    ]
    payload = {"requirements": {"items": items}}
    # Match real-world wrapper output: markdown is a STRING with JSON fenced in ``` blocks.
    return {"markdown": f"```\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"}


def test_parse_json_from_llm_unwraps_markdown() -> None:
    service = TrafficLightService(txt_folder="txt")
    llm_raw = _build_llm_raw_fixture()

    parsed = service._parse_json_from_llm(llm_raw)
    assert "requirements" in parsed
    items = parsed["requirements"]["items"]
    assert isinstance(items, list)
    assert len(items) > 0


def test_calculate_color_score_percent_expected() -> None:
    service = TrafficLightService(txt_folder="txt")

    # Формула: b=match>=70, c=30..69, d<30.
    # В right_response.txt: 1 элемент match_percent=60 (c=1), остальные 0 (d=8).
    reqs = [
        TrafficLightRequirement(
            requirement="r1",
            resume_evidence="",
            match_percent=60,
            difference_comment="",
        ),
        *[
            TrafficLightRequirement(
                requirement=f"r{i}",
                resume_evidence="",
                match_percent=0,
                difference_comment="",
            )
            for i in range(2, 10)
        ],
    ]

    # По текущей формуле должно получиться 1:
    # raw = ((0+0.5*1)*(0+1) + 0.01*8) / (9*9) * 100 ~= 0.716 -> round => 1.
    assert service._calculate_color_score_percent(reqs) == 1


def test_generate_candidate_traffic_light_uses_parsed_requirements(monkeypatch) -> None:
    service = TrafficLightService(txt_folder="txt")
    llm_raw = _build_llm_raw_fixture()

    def fake_call(*_args, **_kwargs):
        return llm_raw

    monkeypatch.setattr(service.llm, "call", fake_call)

    tl_candidate, llm_raw_out = service.generate_candidate_traffic_light(
        request_text="Python requirement",
        candidate_prj_exp="some project exp",
        candidate_id="1",
        candidate_name="Иван Иванов",
        title="Python Developer",
        location="Томск",
        resume_url=None,
    )

    assert tl_candidate.id == "1"
    assert tl_candidate.candidate_name == "Иван Иванов"
    assert len(tl_candidate.requirements) == 9
    assert tl_candidate.color_score_percent == 1
    assert tl_candidate.debug_llm_raw == llm_raw
    assert llm_raw_out == llm_raw
    assert isinstance(tl_candidate.debug_prompt, str) and tl_candidate.debug_prompt.strip()


def test_generate_candidate_traffic_light_coerces_match_percent_percent_string(monkeypatch) -> None:
    service = TrafficLightService(txt_folder="txt")
    llm_raw = _build_llm_raw_fixture_with_match_percent("60%")

    def fake_call(*_args, **_kwargs):
        return llm_raw

    monkeypatch.setattr(service.llm, "call", fake_call)

    tl_candidate, _ = service.generate_candidate_traffic_light(
        request_text="Python requirement",
        candidate_prj_exp="some project exp",
        candidate_id="1",
        candidate_name="Иван Иванов",
        title="Python Developer",
        location="Томск",
        resume_url=None,
    )

    assert len(tl_candidate.requirements) == 9
    assert tl_candidate.requirements[0].match_percent == 60
    assert tl_candidate.color_score_percent == 1

def test_generate_candidate_traffic_light_parses_markdown_string(monkeypatch) -> None:
    service = TrafficLightService(txt_folder="txt")
    llm_raw = _build_llm_raw_fixture_markdown_string()

    def fake_call(*_args, **_kwargs):
        return llm_raw

    monkeypatch.setattr(service.llm, "call", fake_call)

    tl_candidate, _ = service.generate_candidate_traffic_light(
        request_text="Python requirement",
        candidate_prj_exp="some project exp",
        candidate_id="1",
        candidate_name="Иван Иванов",
        title="Python Developer",
        location="Томск",
        resume_url=None,
    )

    assert len(tl_candidate.requirements) == 9
    assert tl_candidate.color_score_percent == 1


def test_generate_candidate_traffic_light_handles_unexpected_llm_raw_shape(monkeypatch) -> None:
    service = TrafficLightService(txt_folder="txt")
    llm_raw = []

    def fake_call(*_args, **_kwargs):
        return llm_raw

    monkeypatch.setattr(service.llm, "call", fake_call)

    tl_candidate, llm_raw_out = service.generate_candidate_traffic_light(
        request_text="Python requirement",
        candidate_prj_exp="some project exp",
        candidate_id="1",
        candidate_name="Иван Иванов",
        title="Python Developer",
        location="Томск",
        resume_url=None,
    )

    assert tl_candidate.requirements == []
    assert tl_candidate.color_score_percent == 0
    assert llm_raw_out == llm_raw

