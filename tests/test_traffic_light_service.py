from app.services.traffic_light_service import TrafficLightService


class _PromptStub:
    @staticmethod
    def get_traffic_light_prompt_template() -> str:
        return "REQ=${custReqText}\nRES=${candidatePrjExp}"


def _make_service() -> TrafficLightService:
    service = TrafficLightService.__new__(TrafficLightService)
    service.prompt_service = _PromptStub()
    return service


def test_build_prompt_uses_only_required_block():
    service = _make_service()
    request_text = """
# Обязательно
- Python
- FastAPI
# Желательно
- Docker
# Задачи
- Руководить командой
""".strip()
    prompt = service.build_prompt(request_text=request_text, candidate_prj_exp="resume")

    assert "- Python" in prompt
    assert "- FastAPI" in prompt
    assert "Docker" not in prompt
    assert "Руководить командой" not in prompt
    assert "RES=resume" in prompt


def test_build_prompt_falls_back_to_full_text_without_blocks():
    service = _make_service()
    request_text = "Python; FastAPI; Docker"
    prompt = service.build_prompt(request_text=request_text, candidate_prj_exp="resume")

    assert "REQ=Python; FastAPI; Docker" in prompt
