from __future__ import annotations

from app.services.prompts import PromptService


def test_prompt_service_reads_txt() -> None:
    ps = PromptService(txt_folder="txt", output_folder="logs")
    t = ps.get_default_request_text()
    assert isinstance(t, str) and len(t) > 0
