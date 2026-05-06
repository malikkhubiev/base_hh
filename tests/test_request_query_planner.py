from app.services.request_query_planner import RequestQueryPlanner


def test_build_uses_only_required_block_for_llm(monkeypatch):
    planner = RequestQueryPlanner(llm_url="http://fake", llm_token_param="?token=fake")
    calls: list[str] = []

    def fake_call(*, prompt_text: str, iteration: int):
        calls.append(prompt_text)
        return {"response": "(python) AND (fastapi)"}

    monkeypatch.setattr(planner.llm, "call", fake_call)
    monkeypatch.setattr(
        planner.prompts,
        "get_system_prompt_text",
        lambda: "SYS",
    )
    monkeypatch.setattr(
        planner.prompts,
        "get_user_prompt_text",
        lambda: "USER {vac_reqs}",
    )

    request = """
# Обязательно:
- Python
- FastAPI
# Желательно:
- Kafka
# Задачи:
- Поддерживать пайплайн
""".strip()

    result = planner.build(request)

    assert len(calls) == 1
    assert "Kafka" not in calls[0]
    assert "Поддерживать пайплайн" not in calls[0]
    assert "Python" in calls[0]
    assert result.queries["Основной"]
    assert result.llm_debug["bool_blocks"]["Желательно"]["expression"] == ""
    assert result.llm_debug["bool_blocks"]["Задачи"]["expression"] == ""
