from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.clients.llm_client import LLMClient
from app.core.settings import settings
from app.models.schemas import TrafficLightCandidate, TrafficLightRequirement
from app.services.prompts import PromptService


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

    def _parse_json_from_llm(self, llm_raw: dict[str, Any]) -> dict[str, Any]:
        # В проекте для булевых запросов извлекают llm_response["response"].
        # Для светофора LLM часто возвращает вид: {"markdown": {...}}.
        response_obj = llm_raw.get("response", llm_raw)

        if isinstance(response_obj, dict):
            # Если LLM оборачивает полезные данные в markdown-поле — распакуем.
            markdown = response_obj.get("markdown")
            if isinstance(markdown, dict):
                return markdown
            return response_obj

        if isinstance(response_obj, str):
            txt = response_obj.strip()
            # Удаляем возможные Markdown-кодфенсы вокруг JSON.
            txt = re.sub(r"^```[a-zA-Z]*\\s*", "", txt)
            txt = re.sub(r"```\\s*$", "", txt)
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

    def _mock_requirements(self) -> tuple[list[TrafficLightRequirement], dict[str, Any]]:
        # Для локальной проверки/интерфейса можно поднять детерминированный ответ.
        # Файл лежит в корне репозитория: todo/llm_svetofor_response.json
        candidates = [
            Path("todo") / "llm_svetofor_response.json",
            Path(__file__).resolve().parents[3] / "todo" / "llm_svetofor_response.json",
        ]
        last_err: Exception | None = None
        for p in candidates:
            try:
                if p.exists():
                    data = json.loads(p.read_text(encoding="utf-8"))
                    items = data.get("requirements", {}).get("items", [])
                    requirements = [
                        TrafficLightRequirement(
                            requirement=it.get("requirement", ""),
                            resume_evidence=it.get("resume_evidence", ""),
                            match_percent=int(it.get("match_percent", 0)),
                            difference_comment=it.get("difference_comment", ""),
                        )
                        for it in items
                    ]
                    return requirements, data
            except Exception as e:  # pragma: no cover
                last_err = e
        raise FileNotFoundError("Mock traffic light response not found") from last_err

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
        mock_llm: bool = False,
    ) -> tuple[TrafficLightCandidate, Any | None]:
        prompt = self.build_prompt(request_text=request_text, candidate_prj_exp=candidate_prj_exp)

        if mock_llm:
            requirements, llm_raw = self._mock_requirements()
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
        llm_raw = self.llm.call(prompt_text=prompt, iteration=0, model="YandexGPT\pro")
        if not llm_raw:
            requirements: list[TrafficLightRequirement] = []
        else:
            data = self._parse_json_from_llm(llm_raw)
            items = data.get("requirements", {}).get("items", [])
            requirements = [
                TrafficLightRequirement(
                    requirement=str(it.get("requirement", "")),
                    resume_evidence=str(it.get("resume_evidence", "")),
                    match_percent=int(it.get("match_percent", 0)),
                    difference_comment=str(it.get("difference_comment", "")),
                )
                for it in items
            ]

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

