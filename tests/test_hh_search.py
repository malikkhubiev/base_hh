from __future__ import annotations

from app.services.hh_search import EXCLUSION, HHSearchService


def test_add_exclusion_wraps() -> None:
    svc = HHSearchService(token_url="http://test/token", token_source="ssp")
    q = "python AND django"
    out = svc.add_exclusion(q)
    assert q in out
    assert EXCLUSION.split()[0] == "NOT"


def test_map_professional_roles_finds_python() -> None:
    svc = HHSearchService(token_url="http://test/token", token_source="ssp")
    roles = svc._map_professional_roles("Senior Python developer backend")
    assert "96" in roles


def test_build_search_filters_default_area() -> None:
    svc = HHSearchService(token_url="http://test/token", token_source="ssp")
    f = svc._build_search_filters(source_text="java developer", area_id=None, professional_roles=None)
    assert f["professional_roles"]


def test_is_managerial_detects_lead() -> None:
    svc = HHSearchService(token_url="http://test/token", token_source="ssp")
    assert svc._is_managerial_position("Team lead developer") is True
    assert svc._is_managerial_position("Python разработчик") is False
