from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_yaml_is_multi_document() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "openapi.yaml"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "\n---\n" in text
    docs = list(yaml.safe_load_all(text))
    assert len(docs) == 2
    assert docs[0]["info"]["title"] == "HH Optimizer API"
    assert docs[0]["openapi"] == "3.0.3"
    assert docs[1]["openapi"] == "3.0.3"
    assert "paths" in docs[1]
