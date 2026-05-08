from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.clients.llm_client import LLMClient
from app.core.tracing import trace_step
from app.utils.file_manager import FileManager

logger = logging.getLogger(__name__)


class QueryGenerator:
    def _prepare_for_json(self, text: str) -> str:
        text = (text or "").replace("\n", " ").replace("\r", " ").replace("\t", " ")
        text = re.sub(r"\s+", " ", text).strip()
        text = text.replace("\\", "\\\\")
        text = text.replace('"', '\\"')
        return text

    def _normalize_lines(self, text: str) -> str:
        parts = [p.strip() for p in re.split(r"(?:\n|;)+", text or "") if p.strip()]
        out: list[str] = []
        for item in parts:
            s = item
            if not s.startswith("-"):
                s = f"- {s}"
            if not s.endswith(";"):
                s = f"{s};"
            out.append(s)
        return "\n".join(out)

    """Генерирует один итоговый булевый запрос через LLM."""

    def __init__(self, llm_url: str, llm_token_param: str, txt_folder: str = "txt", output_folder: str = "logs"):
        self.fm = FileManager(txt_folder=txt_folder, output_folder=output_folder)
        self.llm = LLMClient(llm_url=llm_url, token_param=llm_token_param)

        self.system_prompt = self.fm.read_txt("system_prompt.txt")
        self.user_prompt_template = self.fm.read_txt("user_prompt.txt")

    def _build_prompt(
        self,
        request_text: str,
        *,
        prompt_override: str | None = None,
    ) -> str:
        template = prompt_override if prompt_override is not None else f"{self.system_prompt}\n\n{self.user_prompt_template}"
        return template.format(vac_reqs=request_text).strip()

    def generate(
        self,
        request_text: str,
        *,
        prompt_override: str | None = None,
    ) -> tuple[str, Any | None]:
        trace_step(
            logger,
            "query_generator",
            "generate.start",
            request_preview=(request_text or "")[:400],
            has_prompt_override=prompt_override is not None,
        )
        prepared_for_json = self._prepare_for_json(request_text)
        normalized_for_llm = self._normalize_lines(prepared_for_json)
        prompt = self._build_prompt(
            normalized_for_llm,
            prompt_override=prompt_override,
        )
        llm_raw = self.llm.call(prompt_text=prompt, iteration=0)
        if not llm_raw:
            trace_step(logger, "query_generator", "generate.empty_llm_response")
            return "", None

        queries = self.llm.extract_queries(llm_raw)
        if not queries:
            trace_step(logger, "query_generator", "generate.extract_queries_failed", llm_keys=list(llm_raw.keys()) if isinstance(llm_raw, dict) else None)
            return "", llm_raw

        # Берём любой непустой запрос (модель LLMClient может возвращать разные форматы).
        picked = ""
        if isinstance(queries, dict):
            for v in queries.values():
                if isinstance(v, str) and v.strip():
                    picked = v.strip()
                    break
                if v is not None:
                    picked = json.dumps(v, ensure_ascii=False)
                    break
        elif isinstance(queries, str):
            picked = queries.strip()
        trace_step(logger, "query_generator", "generate.ok", query_len=len(picked or ""))
        return picked, llm_raw

