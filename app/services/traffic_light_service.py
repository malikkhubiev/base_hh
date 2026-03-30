from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.clients.llm_client import LLMClient
from app.core.settings import settings
from app.models.schemas import TrafficLightCandidate, TrafficLightRequirement
from app.services.prompts import PromptService

logger = logging.getLogger(__name__)


class TrafficLightService:
    """
    Строит "Светофор-таблицу" для кандидата:
    - формирует prompt из traffic_light_prompt.txt
    - вызывает LLM (ожидается JSON формата из task.md)
    - извлекает requirements.items
    - считает ColorScore
    """

    def __init__(self, txt_folder: str = "txt") -> None:
        self.prompt_service = PromptService(txt_folder=txt_folder)
        self.llm = LLMClient(llm_url=settings.llm_url, token_param=settings.llm_token_param)

    def build_prompt(self, *, request_text: str, candidate_prj_exp: str) -> str:
        template = self.prompt_service.get_traffic_light_prompt_template()
        # В шаблоне используются плейсхолдеры вида ${custReqText} и ${candidatePrjExp}
        return (
            template.replace("${custReqText}", request_text)
            .replace("${candidatePrjExp}", candidate_prj_exp)
        )

    def _parse_json_from_llm(self, llm_raw: Any) -> dict[str, Any]:
        # В проекте для булевых запросов извлекают llm_response["response"].
        # Для светофора LLM часто возвращает вид: {"markdown": {...}}.
        response_obj = llm_raw.get("response", llm_raw) if isinstance(llm_raw, dict) else llm_raw

        if isinstance(response_obj, dict):
            # Если LLM оборачивает полезные данные в markdown-поле — распакуем.
            markdown = response_obj.get("markdown")
            if isinstance(markdown, dict):
                return markdown
            # Некоторые обертки возвращают markdown как строку с кодфенсами и JSON внутри.
            if isinstance(markdown, str):
                response_obj = markdown
            else:
                return response_obj

        if isinstance(response_obj, str):
            txt = response_obj.strip()
            # Удаляем возможные Markdown-кодфенсы вокруг JSON.
            txt = re.sub(r"^```[a-zA-Z]*\s*", "", txt)
            txt = re.sub(r"```\s*$", "", txt)
            # Иногда LLM может вернуть текст с JSON внутри; вытащим подстроку.
            if not (txt.startswith("{") and txt.endswith("}")):
                start = txt.find("{")
                end = txt.rfind("}")
                if start != -1 and end != -1 and end > start:
                    txt = txt[start : end + 1]
            try:
                return json.loads(txt)
            except json.JSONDecodeError:
                # Ещё одна попытка: вытащить первый { и последний } независимо от окончания.
                start = txt.find("{")
                end = txt.rfind("}")
                if start != -1 and end != -1 and end > start:
                    return json.loads(txt[start : end + 1])
                raise

        raise ValueError("Unsupported LLM response shape for traffic light")

    def _coerce_match_percent(self, value: Any) -> int:
        """
        LLM может вернуть match_percent как число, строку ("60") или с % ("60%").
        Приводим к int в диапазоне 0..100 и не падаем на мусоре.
        """
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            try:
                return max(0, min(100, int(round(float(value)))))
            except Exception:
                return 0
        if isinstance(value, str):
            # Забираем первое число (например "60%" -> 60).
            m = re.search(r"(\d{1,3})", value)
            if not m:
                return 0
            try:
                return max(0, min(100, int(m.group(1))))
            except Exception:
                return 0
        return 0

    def _calculate_color_score_percent(self, requirements: list[TrafficLightRequirement]) -> int:
        b = sum(1 for it in requirements if int(it.match_percent) >= 70)
        c = sum(1 for it in requirements if 30 <= int(it.match_percent) <= 69)
        d = sum(1 for it in requirements if int(it.match_percent) < 30)

        total = b + c + d
        if total <= 0:
            return 0

        raw = ((b + 0.5 * c) * (b + c) + 0.01 * d) / (total * total) * 100.0
        # Округляем до целого процента; формально задача ожидает диапазон 1..100.
        return max(1, min(100, int(round(raw))))

    def generate_candidate_traffic_light(
        self,
        *,
        request_text: str,
        candidate_prj_exp: str,
        candidate_id: str,
        candidate_name: str,
        title: str | None = None,
        location: str | None = None,
        resume_url: str | None = None,
    ) -> tuple[TrafficLightCandidate, Any | None]:
        prompt = self.build_prompt(request_text=request_text, candidate_prj_exp=candidate_prj_exp)

        llm_raw = self.llm.call(prompt_text=prompt, iteration=0, model="YandexGPT\\pro")
        requirements: list[TrafficLightRequirement] = []
        if llm_raw:
            try:
                data = self._parse_json_from_llm(llm_raw)
                items = data.get("requirements", {}).get("items", [])
                if isinstance(items, list):
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        requirements.append(
                            TrafficLightRequirement(
                                requirement=str(it.get("requirement", "")),
                                resume_evidence=str(it.get("resume_evidence", "")),
                                match_percent=self._coerce_match_percent(it.get("match_percent")),
                                difference_comment=str(it.get("difference_comment", "")),
                            )
                        )
            except Exception:
                # Если LLM вернул неожиданную форму/битый match_percent — не валим весь светофор,
                # просто оставим requirements пустыми (color_score_percent станет 0).
                logger.exception("Failed to parse traffic light LLM response")

        color_score_percent = self._calculate_color_score_percent(requirements)
        return (
            TrafficLightCandidate(
                id=candidate_id,
                candidate_name=candidate_name,
                title=title,
                location=location,
                resume_url=resume_url,
                color_score_percent=color_score_percent,
                requirements=requirements,
                candidate_prj_exp=candidate_prj_exp,
                debug_prompt=prompt,
                debug_llm_raw=llm_raw,
            ),
            llm_raw,
        )

