from __future__ import annotations

from unittest.mock import MagicMock

from app.services.query_generator import QueryGenerator


def test_build_prompt_formats_user_template(tmp_path) -> None:
    txt = tmp_path / "txt"
    txt.mkdir()
    (txt / "system_prompt.txt").write_text("SYS", encoding="utf-8")
    (txt / "user_prompt.txt").write_text("REQ: {vac_reqs}", encoding="utf-8")

    gen = QueryGenerator(llm_url="http://x", llm_token_param="?", txt_folder=str(txt), output_folder=str(tmp_path / "logs"))
    prompt = gen._build_prompt("hello world")
    assert "SYS" in prompt
    assert "REQ: hello world" in prompt


def test_generate_returns_empty_when_llm_returns_none(tmp_path) -> None:
    txt = tmp_path / "txt"
    txt.mkdir()
    for name in ("system_prompt.txt", "user_prompt.txt"):
        (txt / name).write_text("x", encoding="utf-8")

    gen = QueryGenerator(llm_url="http://x", llm_token_param="?", txt_folder=str(txt), output_folder=str(tmp_path / "logs"))
    gen.llm = MagicMock()
    gen.llm.call.return_value = None

    queries, raw = gen.generate("vacancy")
    assert queries["Уровень 1"] == ""
    assert raw is None
