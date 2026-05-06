from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


def test_prompt_endpoints(monkeypatch):
    from app.api.routes import workflow

    monkeypatch.setattr(workflow.PromptService, "get_default_request_text", lambda self: "REQ")
    monkeypatch.setattr(workflow.PromptService, "get_system_prompt_text", lambda self: "SYS")
    monkeypatch.setattr(workflow.PromptService, "get_user_prompt_text", lambda self: "USR")
    client = TestClient(app)

    assert client.get("/api/default_request").text == "REQ"
    assert client.get("/api/system_prompt").text == "SYS"
    assert client.get("/api/user_prompt").text == "USR"


def test_generate_queries_with_override_skips_llm():
    client = TestClient(app)
    res = client.post(
        "/api/generate_queries",
        json={"request_text": "", "queries_override": {"Основной": "(python)"}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["queries"]["Основной"] == "(python)"
    assert body["llm_raw"] is None


def test_search_endpoint_and_no_professional_roles(monkeypatch):
    from app.api.routes import workflow

    def fake_search(self, queries, *, search_plan, search_plan_meta, source_text, area_id, per_page, **kwargs):
        assert "professional_roles" not in queries
        return (
            {"Основной": 1},
            {"Основной": [{"id": "1", "title": "Python Dev", "skills": [], "tags": []}]},
            {"Основной": "(python)"},
            {"Основной": "https://hh.example/search"},
            "(python)",
            [
                {
                    "stage": "Этап 1",
                    "query": "(python)",
                    "query_with_exclusion": "(python)",
                    "found": 1,
                    "collected": 1,
                    "target": per_page,
                    "enough": True,
                    "web_url": "https://hh.example/search",
                }
            ],
        )

    monkeypatch.setattr(workflow.HHSearchService, "search_counts_and_candidates", fake_search)
    monkeypatch.setattr(
        workflow,
        "_run_query_generation",
        lambda **kwargs: (
            {"Основной": "(python)"},
            {"raw": "ok"},
            [("Этап 1", "(python)")],
            [{"stage": "Этап 1", "query": "(python)"}],
            datetime.utcnow(),
            datetime.utcnow(),
        ),
    )
    client = TestClient(app)
    res = client.post(
        "/api/search",
        json={"request_text": "Python", "candidates_limit": 20},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["final_boolean_query"] == "(python)"
    assert body["found_count"] == 1
    assert body["candidates"][0]["id"] == "1"


def test_traffic_light_endpoint(monkeypatch):
    from app.api.routes import workflow
    from app.models.schemas import TrafficLightCandidate

    async def fake_collect(hh, payload, candidates_for_tl, **kwargs):
        return [
            TrafficLightCandidate(
                id="1",
                candidate_name="Иванов Иван",
                title="Python Dev",
                location="Томск",
                resume_url="https://hh.ru/resume/1",
                color_score_percent=90,
                requirements=[],
            )
        ]

    monkeypatch.setattr(workflow, "_collect_traffic_light_candidates", fake_collect)
    client = TestClient(app)
    res = client.post(
        "/api/traffic_light",
        json={
            "request_text": "Python",
            "candidates": [{"id": "1", "title": "Python Dev"}, {"id": "2", "title": "Backend Dev"}],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["traffic_light_candidates"][0]["color_score_percent"] == 90
    assert len(body["traffic_light_candidates"]) == 2
    assert body["traffic_light_candidates"][1]["id"] == "2"
    assert body["traffic_light_candidates"][1]["color_score_percent"] == 0


def test_svetofor_keeps_only_scored_candidates(monkeypatch):
    from app.api.routes import workflow
    from app.models.schemas import TrafficLightCandidate

    def fake_run_search_with_restarts(*, payload, request_text, area_id):
        assert payload.candidates_limit == 20
        now = datetime.utcnow()
        return (
            {"Основной": "(python)"},
            {"raw": "ok"},
            {"Основной": 2},
            {
                "Основной": [
                    {"id": "1", "title": "Python Dev", "skills": [], "tags": []},
                    {"id": "2", "title": "Backend Dev", "skills": [], "tags": []},
                ]
            },
            {"Основной": "(python)"},
            {"Основной": "https://hh.example/search"},
            "(python)",
            [{"block": "Обязательно", "expression": "(python)"}],
            [],
            now,
            now,
            now,
            1,
            0,
        )

    async def fake_collect(hh, payload, candidates_for_tl, **kwargs):
        return [
            TrafficLightCandidate(
                id="1",
                candidate_name="Иванов Иван",
                title="Python Dev",
                location="Томск",
                resume_url="https://hh.ru/resume/1",
                color_score_percent=90,
                requirements=[],
            )
        ]

    monkeypatch.setattr(workflow, "_run_search_with_restarts", fake_run_search_with_restarts)
    monkeypatch.setattr(workflow, "_collect_traffic_light_candidates", fake_collect)

    client = TestClient(app)
    res = client.post(
        "/api/svetofor",
        json={
            "request_text": "Python",
            "candidates_limit": 20,
            "svetofor_top_x": 20,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["traffic_light_candidates"]) == 1
    assert body["traffic_light_candidates"][0]["id"] == "1"
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["id"] == "1"


def test_search_uses_best_result_when_iteration_limit_reached(monkeypatch):
    from app.api.routes import workflow

    call_no = {"n": 0}

    def fake_search(self, queries, *, search_plan, search_plan_meta, source_text, area_id, per_page, **kwargs):
        call_no["n"] += 1
        if call_no["n"] == 1:
            count = 10
        elif call_no["n"] == 2:
            count = 15
        else:
            count = 12
        stage_attempts = [{"stage": f"Этап {i}", "query": "(python)", "query_with_exclusion": "(python)", "found": count, "collected": count, "target": per_page, "enough": count >= per_page, "web_url": "https://hh.example/search"} for i in range(40)]
        return (
            {"Основной": count},
            {"Основной": [{"id": str(i), "title": "Python Dev", "skills": [], "tags": []} for i in range(1, count + 1)]},
            {"Основной": "(python)"},
            {"Основной": "https://hh.example/search"},
            "(python)",
            stage_attempts,
        )

    monkeypatch.setattr(workflow.HHSearchService, "search_counts_and_candidates", fake_search)
    monkeypatch.setattr(
        workflow,
        "_run_query_generation",
        lambda **kwargs: (
            {"Основной": "(python)"},
            {"raw": "ok"},
            [("Этап 1", "(python)")],
            [{"stage": "Этап 1", "query": "(python)"}],
            datetime.utcnow(),
            datetime.utcnow(),
        ),
    )
    client = TestClient(app)
    res = client.post(
        "/api/search",
        json={"request_text": "Python", "candidates_limit": 20},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["candidates"]) == 15
    assert body["found_count"] == 15
    assert body["total_iterations"] == 100
