"""Контекст трассировки запроса и безопасное пошаговое логирование."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from contextvars import ContextVar, Token
from typing import Any

trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)

_SENSITIVE_KEY_RE = re.compile(
    r"(token|secret|password|authorization|api_?key|bearer|credential|access_token|refresh_token)",
    re.I,
)


def app_trace_enabled() -> bool:
    """Полные шаги в логах на уровне INFO (без включения DEBUG у всех библиотек)."""
    return os.getenv("APP_TRACE", "").strip().lower() in ("1", "true", "yes", "on")


def get_trace_id() -> str | None:
    return trace_id_ctx.get()


def set_trace_id(trace_id: str | None) -> Token[str | None]:
    return trace_id_ctx.set(trace_id)


def reset_trace_id(token: Token[str | None]) -> None:
    trace_id_ctx.reset(token)


def new_trace_id() -> str:
    return str(uuid.uuid4())


def _redact_key(key: str) -> bool:
    return bool(_SENSITIVE_KEY_RE.search(key))


def safe_json_value(
    val: Any,
    *,
    max_str: int = 4000,
    max_depth: int = 8,
    _depth: int = 0,
) -> Any:
    """Сериализация значений для лога: ограничение глубины/размера, скрытие чувствительных ключей."""
    if _depth > max_depth:
        return "<max_depth>"
    if val is None or isinstance(val, (bool, int, float)):
        return val
    if isinstance(val, str):
        if len(val) > max_str:
            return val[:max_str] + f"...<len={len(val)}>"
        return val
    if isinstance(val, bytes):
        return f"<bytes len={len(val)}>"
    if isinstance(val, dict):
        out: dict[str, Any] = {}
        for k, v in list(val.items())[:100]:
            ks = str(k)
            if _redact_key(ks):
                out[ks] = "<redacted>"
            else:
                out[ks] = safe_json_value(v, max_str=max_str, max_depth=max_depth, _depth=_depth + 1)
        if len(val) > 100:
            out["<truncated_dict_entries>"] = len(val) - 100
        return out
    if isinstance(val, (list, tuple, set)):
        seq = list(val)[:80]
        out_list = [
            safe_json_value(x, max_str=max_str, max_depth=max_depth, _depth=_depth + 1) for x in seq
        ]
        if len(val) > 80:
            out_list.append(f"<truncated list, total={len(val)}>")
        return out_list
    try:
        s = repr(val)
    except Exception:
        s = f"<{type(val).__name__}>"
    return s[:max_str]


def trace_payload(**kwargs: Any) -> str:
    try:
        return json.dumps(safe_json_value(kwargs), ensure_ascii=False)
    except Exception:
        return repr(kwargs)


def trace_step(logger: logging.Logger, phase: str, message: str, **data: Any) -> None:
    """Один шаг пайплайна: фаза, сообщение, именованные значения (с безопасной сериализацией)."""
    parts = [f"[{phase}] {message}"]
    if data:
        parts.append(trace_payload(**data))
    text = " | ".join(parts)
    level = logging.INFO if app_trace_enabled() else logging.DEBUG
    logger.log(level, "%s", text)


class TraceContextFilter(logging.Filter):
    """Подмешивает trace_id в запись лога (для формата %(trace_id)s)."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        tid = get_trace_id()
        record.trace_id = tid or "-"  # type: ignore[attr-defined]
        return True


def install_trace_context_filter() -> None:
    """Вешаем фильтр на handlers корня: так trace_id попадает в строку для всех логгеров."""
    root = logging.getLogger()
    for h in root.handlers:
        if not any(isinstance(f, TraceContextFilter) for f in getattr(h, "filters", [])):
            h.addFilter(TraceContextFilter())
