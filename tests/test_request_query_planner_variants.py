from app.services.request_query_planner import RequestQueryPlanner


def test_required_variants_remove_one_then_two_in_order():
    planner = RequestQueryPlanner(llm_url="http://fake", llm_token_param="?token=fake")
    variants = planner._build_required_variants(["(a)", "(b)", "(c)"])

    assert "(a)" in variants[0] and "(b)" in variants[0] and "(c)" in variants[0]
    # убрать 1: сначала без (a)
    assert variants[1] == "(((b)) AND ((c)))"
    assert variants[2] == "(((a)) AND ((c)))"
    assert variants[3] == "(((a)) AND ((b)))"
    # убрать 2
    assert variants[4] == "((c))"
    assert variants[5] == "((b))"
    assert variants[6] == "((a))"
    assert variants[-1] == "((a))"


def test_search_plan_splits_wrapped_llm_expression_into_stages(monkeypatch):
    planner = RequestQueryPlanner(llm_url="http://fake", llm_token_param="?token=fake")

    def fake_call(*, prompt_text: str, iteration: int):
        return {"response": "(((Python) AND (React) AND (Vue)))"}

    monkeypatch.setattr(planner.llm, "call", fake_call)
    monkeypatch.setattr(planner.prompts, "get_system_prompt_text", lambda: "SYS")
    monkeypatch.setattr(planner.prompts, "get_user_prompt_text", lambda: "USER {vac_reqs}")

    result = planner.build("# Обязательно:\n- Python\n- React\n- Vue")
    stages = [name for name, query in result.search_plan]

    assert stages[0] == "Этап 1: обязательные"
    assert len(result.search_plan) == 7
    assert "React" in result.search_plan[0][1] and "Vue" in result.search_plan[0][1]
    assert result.search_plan[-1][1] != ""
    assert "широкий" not in stages[-1]


def test_clause_list_unwraps_outer_parens():
    planner = RequestQueryPlanner(llm_url="http://fake", llm_token_param="?token=fake")
    expr = "(((Python) AND (React) AND (Vue)))"
    clauses = planner._clause_list_from_required(expr, [])
    assert len(clauses) == 3
    assert clauses[0] == "Python"
    assert clauses[1] == "React"
    assert clauses[2] == "Vue"
