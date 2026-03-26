from __future__ import annotations

import json
import re
from pathlib import Path

from app.models.schemas import TrafficLightRequirement
from app.services.traffic_light_service import TrafficLightService


def _load_llm_raw_from_right_response() -> dict:
    """
    `todo/right_response.txt` содержит текст "Ответ агента (raw)" и затем JSON.
    Для тестов вытаскиваем JSON-часть.
    """
    repo_root = Path(__file__).resolve().parents[1]
    p = repo_root / "todo" / "right_response.txt"
    txt = p.read_text(encoding="utf-8")

    m = re.search(r"\{[\s\S]*\}\s*$", txt)
    assert m, "Не удалось найти JSON в todo/right_response.txt"
    return json.loads(m.group(0))


def test_parse_json_from_llm_unwraps_markdown() -> None:
    service = TrafficLightService(txt_folder="txt")
    llm_raw = _load_llm_raw_from_right_response()

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
    llm_raw = _load_llm_raw_from_right_response()

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
        mock_llm=False,
    )

    assert tl_candidate.id == "1"
    assert tl_candidate.candidate_name == "Иван Иванов"
    assert len(tl_candidate.requirements) == 9
    assert tl_candidate.color_score_percent == 1
    assert tl_candidate.debug_llm_raw == llm_raw
    assert llm_raw_out == llm_raw
    assert isinstance(tl_candidate.debug_prompt, str) and tl_candidate.debug_prompt.strip()

