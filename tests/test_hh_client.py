from __future__ import annotations

from app.clients.hh_client import HHClient


def test_build_api_params_maps_period() -> None:
    c = HHClient(token_url="http://x", token_source="ssp")
    p = c._build_api_params("query", {"period": ["0"], "professional_roles": ["96"]}, 10)
    assert p["period"] == ["0"]
    assert p["professional_role"] == ["96"]


def test_api_to_url_params_renames_keys() -> None:
    c = HHClient(token_url="http://x", token_source="ssp")
    u = c._api_to_url_params({"per_page": 20, "period": ["0"], "text": "x"})
    assert "items_on_page" in u
    assert "search_period" in u


def test_compact_items_skips_non_dict() -> None:
    c = HHClient(token_url="http://x", token_source="ssp")
    out = c._compact_items([None, "bad", {"id": "1", "title": "t"}])
    assert len(out) == 1
    assert out[0]["id"] == "1"
