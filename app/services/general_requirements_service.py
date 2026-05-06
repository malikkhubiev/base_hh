from __future__ import annotations

import logging
from typing import Any

from app.clients.llm_client import LLMClient
from app.core.settings import settings
from app.core.tracing import trace_step
from app.services.prompts import PromptService

logger = logging.getLogger(__name__)


class GeneralRequirementsService:
    def __init__(self, txt_folder: str = "txt") -> None:
        self.prompt_service = PromptService(txt_folder=txt_folder)
        self.llm = LLMClient(llm_url=settings.llm_url, token_param=settings.llm_token_param)

    def build_prompt(self, *, cust_req_text: str, candidate_prj_exp: str) -> str:
        template = self.prompt_service.get_general_requirements_prompt_template()
        return template.replace("${custReqText}", cust_req_text or "").replace("${candidatePrjExp}", candidate_prj_exp or "")

    def generate_candidate_review(
        self,
        *,
        cust_req_text: str,
        candidate_prj_exp: str,
        candidate_id: str,
        candidate_name: str,
    ) -> tuple[str, str, Any | None]:
        """
        Returns (review_text, prompt, llm_raw).
        LLM output is treated as plain text (no JSON parsing).
        """
        trace_step(
            logger,
            "general_requirements",
            "generate_candidate_review.start",
            candidate_id=candidate_id,
            candidate_name=candidate_name,
            prj_exp_len=len(candidate_prj_exp or ""),
            cust_req_len=len(cust_req_text or ""),
        )
        prompt = self.build_prompt(cust_req_text=cust_req_text, candidate_prj_exp=candidate_prj_exp)
        llm_raw = self.llm.call(prompt_text=prompt, iteration=0, model="YandexGPT\\pro")
        review_text = ""
        if llm_raw is None:
            review_text = ""
        elif isinstance(llm_raw, str):
            review_text = llm_raw
        elif isinstance(llm_raw, dict) and isinstance(llm_raw.get("response"), str):
            review_text = llm_raw["response"]
        else:
            try:
                review_text = str(llm_raw)
            except Exception:
                review_text = ""
        trace_step(logger, "general_requirements", "generate_candidate_review.done", candidate_id=candidate_id)
        return review_text, prompt, llm_raw

