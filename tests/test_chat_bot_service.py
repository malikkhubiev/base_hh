from __future__ import annotations

import pytest

from app.services.chat_bot_service import ChatBotService


def test_parse_resume_hash_direct() -> None:
    assert ChatBotService.parse_resume_hash("abc123def") == "abc123def"


def test_parse_resume_hash_from_url() -> None:
    url = "https://hh.ru/resume/xyz789?foo=1"
    assert ChatBotService.parse_resume_hash(url) == "xyz789"


def test_parse_resume_hash_empty() -> None:
    with pytest.raises(ValueError):
        ChatBotService.parse_resume_hash("   ")


def test_coerce_reply_text_dict() -> None:
    assert ChatBotService._coerce_reply_text({"response": {"reply_text": " hi "}}) == "hi"


def test_pick_text_from_message() -> None:
    assert ChatBotService._pick_text_from_message_text_payload({"text": " m "}) == "m"
