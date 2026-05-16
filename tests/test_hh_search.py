from app.services.hh_search import HHSearchService


def test_search_counts_accumulates_in_order_until_min_then_caps_display(monkeypatch):
    service = HHSearchService(token_url="http://fake", token_source="ssp")
    stage_payloads = {
        "Этап A": [{"id": str(i)} for i in range(1, 17)],
        "Этап B": [{"id": str(i)} for i in range(17, 20)],
        "Этап C": [{"id": str(i)} for i in range(20, 87)],
    }

    def fake_search(query, *, filters, per_page, level_name, iteration):
        return 1000, list(stage_payloads.get(level_name, []))

    monkeypatch.setattr(service.hh, "search", fake_search)
    monkeypatch.setattr(service.hh, "build_web_search_url", lambda **kwargs: "https://hh.example/search")

    plan = [("Этап A", "q1"), ("Этап B", "q2"), ("Этап C", "q3")]
    _, items, _, _, attempts = service.search_counts_and_candidates(
        "q1",
        search_plan=plan,
        source_text="Python",
        area_id=113,
        per_page=60,
        min_needed=20,
    )

    assert len(attempts) == 3
    assert attempts[0]["collected"] == 16
    assert attempts[1]["collected"] == 19
    assert attempts[1]["enough"] is False
    assert attempts[2]["collected"] == 60
    assert attempts[2]["enough"] is True
    assert len(items) == 60
    assert [c["id"] for c in items[:3]] == ["1", "2", "3"]
    assert items[-1]["id"] == "60"


def test_search_counts_runs_all_stages_until_min_needed(monkeypatch):
    service = HHSearchService(token_url="http://fake", token_source="ssp")
    calls: list[str] = []

    def fake_search(query, *, filters, per_page, level_name, iteration):
        calls.append(level_name)
        idx = len(calls)
        return 100, [{"id": str(idx), "title": f"Dev {idx}"}]

    monkeypatch.setattr(service.hh, "search", fake_search)
    monkeypatch.setattr(service.hh, "build_web_search_url", lambda **kwargs: "https://hh.example/search")

    plan = [
        ("Этап 1", "(a) AND (b) AND (c)"),
        ("Этап 2", "(a) AND (b)"),
        ("Этап 3", "(a)"),
    ]
    found, items, _, _, attempts = service.search_counts_and_candidates(
        "(a) AND (b) AND (c)",
        search_plan=plan,
        source_text="Python",
        area_id=113,
        per_page=10,
        min_needed=3,
    )

    assert found == 100
    assert len(items) == 3
    assert [c["id"] for c in items] == ["1", "2", "3"]
    assert len(attempts) == 3
    assert all(a["enough"] is False for a in attempts[:2])
    assert attempts[-1]["enough"] is True


def test_search_counts_does_not_stop_before_min_even_with_many_stages(monkeypatch):
    service = HHSearchService(token_url="http://fake", token_source="ssp")
    stage_count = {"n": 0}

    def fake_search(query, *, filters, per_page, level_name, iteration):
        stage_count["n"] += 1
        return 1, [{"id": str(stage_count["n"]), "title": "Dev"}]

    monkeypatch.setattr(service.hh, "search", fake_search)
    monkeypatch.setattr(service.hh, "build_web_search_url", lambda **kwargs: "https://hh.example/search")

    plan = [(f"Этап {i}", f"(q{i})") for i in range(1, 51)]
    _, items, _, _, attempts = service.search_counts_and_candidates(
        plan[0][1],
        search_plan=plan,
        source_text="Python",
        area_id=113,
        per_page=60,
        min_needed=20,
    )

    assert stage_count["n"] == 20
    assert len(items) == 20
    assert len(attempts) == 20
