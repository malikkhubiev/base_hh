from __future__ import annotations

import json
import logging
from typing import Any

from app.clients.llm_client import LLMClient
from app.utils.file_manager import FileManager

logger = logging.getLogger(__name__)


class QueryGenerator:
    """Генерирует булевы запросы трех уровней через LLM."""

    def __init__(self, llm_url: str, llm_token_param: str, txt_folder: str = "txt", output_folder: str = "logs"):
        self.fm = FileManager(txt_folder=txt_folder, output_folder=output_folder)
        self.llm = LLMClient(llm_url=llm_url, token_param=llm_token_param)

        self.system_prompt = self.fm.read_txt("system_prompt.txt")
        self.user_prompt_template = self.fm.read_txt("user_prompt.txt")

    def _build_prompt(
        self,
        request_text: str,
        *,
        system_prompt_override: str | None = None,
        user_prompt_override: str | None = None,
    ) -> str:
        user_template = user_prompt_override if user_prompt_override is not None else self.user_prompt_template
        user_prompt = user_template.format(vac_reqs=request_text)
        system_prompt = system_prompt_override if system_prompt_override is not None else self.system_prompt
        return f"{system_prompt}\n\n{user_prompt}"

    def _fallback_queries(self, request_text: str) -> dict[str, str]:
        # Простая эвристика: берем ключевые слова из текста вакансии.
        keywords = []
        for line in request_text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Берем первую смысловую часть до скобок.
            keywords.append(line.split("(")[0].strip(" ;."))
        base = "Python"
        tail = " OR ".join([k for k in keywords if k and "Python" not in k][:20])
        if tail:
            q1 = f"{base} AND ({tail})"
        else:
            q1 = base
        return {
            "Уровень 1": q1,
            "Уровень 2": q1,
            "Уровень 3": q1,
        }

    def generate(
        self,
        request_text: str,
        *,
        system_prompt_override: str | None = None,
        user_prompt_override: str | None = None,
        mock: bool = False,
    ) -> tuple[dict[str, str], Any | None]:
        if mock:
            logger.info("Using mock LLM queries")
            return self._fallback_queries(request_text), None

        prompt = self._build_prompt(
            request_text,
            system_prompt_override=system_prompt_override,
            user_prompt_override=user_prompt_override,
        )
        llm_raw = self.llm.call(prompt_text=prompt, iteration=0)
        if not llm_raw:
            return self._fallback_queries(request_text), None

        queries = self.llm.extract_queries(llm_raw)
        if not queries:
            return self._fallback_queries(request_text), llm_raw

        # Нормализация: гарантируем наличие всех трех уровней.
        for k in ["Уровень 1", "Уровень 2", "Уровень 3"]:
            if k not in queries:
                queries[k] = queries.get("Уровень 2") or queries.get("Уровень 1") or "Python"

        # Приводим значения к строкам для стабильного контракта API.
        safe: dict[str, str] = {}
        for k, v in queries.items():
            safe[k] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)

        return safe, llm_raw

