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
        json={"request_text": "", "query_override": "(python)"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "(python)"
    assert body["llm_raw"] is None


def test_search_endpoint_and_no_professional_roles(monkeypatch):
    from app.api.routes import workflow

    def fake_search(self, query, *, search_plan, search_plan_meta, source_text, area_id, per_page, **kwargs):
        assert "professional_roles" not in (query or "")
        return (
            1,
            [{"id": "1", "title": "Python Dev", "skills": [], "tags": []}],
            "(python)",
            "https://hh.example/search",
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
            "(python)",
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


def test_search_empty_request_text_returns_400():
    client = TestClient(app)
    res = client.post("/api/search", json={"request_text": "", "candidates_limit": 20})
    assert res.status_code == 400


def test_search_candidates_limit_caps_per_page_to_200(monkeypatch):
    from app.api.routes import workflow

    def fake_search(self, query, *, search_plan, search_plan_meta, source_text, area_id, per_page, min_needed, **kwargs):
        # candidates_limit=200 -> per_page=min(200, 200*3)=200
        assert min_needed == 200
        assert per_page == 200
        return (
            0,
            [],
            query,
            "https://hh.example/search",
            [],
        )

    monkeypatch.setattr(workflow.HHSearchService, "search_counts_and_candidates", fake_search)
    monkeypatch.setattr(
        workflow,
        "_run_query_generation",
        lambda **kwargs: (
            "(python)",
            {"raw": "ok"},
            [("Этап 1", "(python)")],
            [{"stage": "Этап 1", "query": "(python)"}],
            datetime.utcnow(),
            datetime.utcnow(),
        ),
    )
    client = TestClient(app)
    res = client.post("/api/search", json={"request_text": "Python", "candidates_limit": 200})
    assert res.status_code == 200


def test_search_candidate_fields_match_ui_table_contract(monkeypatch):
    """
    Проверяем, что /api/search возвращает поля Candidate ровно в том виде,
    который отображается таблицей UI (см. ui.py), и соответствует letter.txt.

    UI читает:
    - id, title
    - area (dict -> name/id)
    - alternate_url/url
    - salary (dict; UI умеет показывать amount/currency или fallback JSON)
    - experience (как пришло из HH search)
    - experience_full (list[dict] из HH resume; может отсутствовать/None)
    - skills/tags (list; если мусор — сервер нормализует в [])
    - first_name/last_name
    """
    from app.api.routes import workflow

    now = datetime.utcnow()

    def fake_search(self, query, *, search_plan, search_plan_meta, source_text, area_id, per_page, min_needed, **kwargs):
        assert per_page == 60
        assert min_needed == 20
        return (
            1,
            [
                {
                    "id": "1",
                    "title": "Python Dev",
                    "url": "https://hh.example/resume/1",
                    "alternate_url": "https://hh.example/alt/1",
                    "created_at": "2020-01-01T00:00:00+00:00",
                    "updated_at": "2020-01-02T00:00:00+00:00",
                    "age": 30,
                    "area": {"id": "113", "name": "Россия"},
                    "employer": {"name": "ACME"},
                    "salary": {"amount": 100000, "currency": "RUR"},
                    "experience": {"total_months": 48, "text": "3–6 лет"},
                    "experience_full": [
                        {"start": "2020-01-01", "end": "2021-01-01", "company": "ACME", "position": "Dev"}
                    ],
                    "skills": "NOT_A_LIST",
                    "tags": None,
                    "first_name": "Иван",
                    "last_name": "Иванов",
                    # лишнее поле не должно попасть в ответ
                    "unexpected_field": "should_not_leak",
                }
            ],
            "(python)",
            "https://hh.example/search",
            [],
        )

    monkeypatch.setattr(workflow.HHSearchService, "search_counts_and_candidates", fake_search)
    monkeypatch.setattr(
        workflow,
        "_run_query_generation",
        lambda **kwargs: (
            "(python)",
            {"raw": "ok"},
            [("Этап 1", "(python)")],
            [{"stage": "Этап 1", "query": "(python)"}],
            now,
            now,
        ),
    )

    client = TestClient(app)
    res = client.post("/api/search", json={"request_text": "Python", "candidates_limit": 20})
    assert res.status_code == 200
    body = res.json()
    assert body["found_count"] == 1
    assert isinstance(body.get("candidates"), list) and len(body["candidates"]) == 1
    c = body["candidates"][0]

    # Базовые поля (letter.txt Candidate)
    assert c["id"] == "1"
    assert c["title"] == "Python Dev"
    assert c["url"] == "https://hh.example/resume/1"
    assert c["alternate_url"] == "https://hh.example/alt/1"
    assert c["created_at"] == "2020-01-01T00:00:00+00:00"
    assert c["updated_at"] == "2020-01-02T00:00:00+00:00"
    assert c["age"] == 30
    assert c["area"]["name"] == "Россия"
    assert c["employer"]["name"] == "ACME"
    assert c["salary"]["amount"] == 100000
    assert c["experience"]["total_months"] == 48
    assert isinstance(c["experience_full"], list) and c["experience_full"][0]["company"] == "ACME"
    assert c["first_name"] == "Иван"
    assert c["last_name"] == "Иванов"

    # Нормализация на API стороне: skills/tags должны стать списками.
    assert c["skills"] == []
    assert c["tags"] == []

    # Лишние поля не должны протечь из HH в публичный контракт.
    assert "unexpected_field" not in c

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
            "(python)",
            {"raw": "ok"},
            2,
            [
                {"id": "1", "title": "Python Dev", "skills": [], "tags": []},
                {"id": "2", "title": "Backend Dev", "skills": [], "tags": []},
            ],
            "(python)",
            "https://hh.example/search",
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

    def fake_search(self, query, *, search_plan, search_plan_meta, source_text, area_id, per_page, **kwargs):
        call_no["n"] += 1
        if call_no["n"] == 1:
            count = 10
        elif call_no["n"] == 2:
            count = 15
        else:
            count = 12
        stage_attempts = [{"stage": f"Этап {i}", "query": "(python)", "query_with_exclusion": "(python)", "found": count, "collected": count, "target": per_page, "enough": count >= per_page, "web_url": "https://hh.example/search"} for i in range(40)]
        return (
            count,
            [{"id": str(i), "title": "Python Dev", "skills": [], "tags": []} for i in range(1, count + 1)],
            "(python)",
            "https://hh.example/search",
            stage_attempts,
        )

    monkeypatch.setattr(workflow.HHSearchService, "search_counts_and_candidates", fake_search)
    monkeypatch.setattr(
        workflow,
        "_run_query_generation",
        lambda **kwargs: (
            "(python)",
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
