from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from app.clients.llm_client import LLMClient
from app.services.prompts import PromptService

BLOCK_REQUIRED = "Обязательно"
BLOCK_DESIRABLE = "Желательно"
BLOCK_TASKS = "Задачи"
KNOWN_BLOCKS = (BLOCK_REQUIRED, BLOCK_DESIRABLE, BLOCK_TASKS)


@dataclass
class PlannedQueries:
    query: str
    search_plan: list[tuple[str, str]]
    search_plan_meta: list[dict[str, Any]]
    llm_raw: Any | None


class RequestQueryPlanner:
    def __init__(self, llm_url: str, llm_token_param: str) -> None:
        self.llm = LLMClient(llm_url=llm_url, token_param=llm_token_param)
        self.prompts = PromptService()

    def build(self, request_text: str, *, prompt_override: str | None = None) -> PlannedQueries:
        source = request_text or ""
        blocks = self._split_blocks(source)
        required_lines = self._normalize_lines(blocks.get(BLOCK_REQUIRED, []))
        required_expr, required_llm_response = self._extract_bool_list(BLOCK_REQUIRED, required_lines, prompt_override=prompt_override)
        search_plan, search_plan_meta = self._build_search_plan(required_expr, "", "", source_lines=required_lines)
        return PlannedQueries(
            query=search_plan[0][1] if search_plan else "",
            search_plan=search_plan,
            search_plan_meta=search_plan_meta,
            llm_raw=required_llm_response,
        )

    def _split_blocks(self, source_text: str) -> dict[str, list[str]]:
        original = (source_text or "").strip()
        line_source = [line.strip() for line in re.split(r"(?:\n|;)+", original) if line.strip()]
        header_pattern = re.compile(r"^#\s*(Обязательно|Желательно|Задачи)\s*:?\s*(.*)$", re.IGNORECASE)
        current_block: str | None = None
        has_hash_headers = bool(re.search(r"#", original))

        blocks: dict[str, list[str]] = {k: [] for k in KNOWN_BLOCKS}
        for raw_line in re.split(r"\n+", original):
            line = raw_line.strip()
            if not line:
                continue
            m = header_pattern.match(line)
            if m:
                normalized = m.group(1).capitalize()
                if normalized == "Обязательно":
                    current_block = BLOCK_REQUIRED
                elif normalized == "Желательно":
                    current_block = BLOCK_DESIRABLE
                else:
                    current_block = BLOCK_TASKS
                inline_text = (m.group(2) or "").strip()
                if inline_text:
                    blocks[current_block].append(inline_text)
                continue
            if current_block:
                blocks[current_block].append(line)

        if not has_hash_headers or not blocks[BLOCK_REQUIRED]:
            return {
                BLOCK_REQUIRED: line_source,
                BLOCK_DESIRABLE: [],
                BLOCK_TASKS: [],
            }
        return blocks

    def _normalize_lines(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        for line in lines:
            s = (line or "").strip()
            if not s:
                continue
            s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
            s = re.sub(r"\s+", " ", s).strip()
            if not s.startswith("-"):
                s = f"- {s}"
            if not s.endswith(";"):
                s = f"{s};"
            s = s.replace("\\", "\\\\")
            s = s.replace('"', '\\"')
            out.append(s)
        return out

    def _extract_bool_lists_parallel(self, block_lines: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {
            name: {
                "expression": "",
                "llm_response": None,
                "input_lines": list(lines or []),
                "normalized_lines": [],
                "prompt_template": "",
                "prompt_rendered": "",
            }
            for name, lines in block_lines.items()
        }
        with ThreadPoolExecutor(max_workers=len(KNOWN_BLOCKS)) as executor:
            futures = {
                block_name: executor.submit(self._extract_bool_list, block_name, lines)
                for block_name, lines in block_lines.items()
            }
            for block_name, future in futures.items():
                expression, llm_response, debug_data = future.result()
                expr = expression.replace('"', '')
                expr = expr.replace("'", '')
                expr = expr.replace('«', '')
                expr = expr.replace('»', '')
                expr = expr.replace('„', '')
                expr = expr.replace('“', '')
                expression = expr.replace('”', '')
                results[block_name] = {
                    "expression": expression,
                    "llm_response": llm_response,
                    "input_lines": list(block_lines.get(block_name, [])),
                    "normalized_lines": debug_data["normalized_lines"],
                    "prompt_template": debug_data["prompt_template"],
                    "prompt_rendered": debug_data["prompt_rendered"],
                }
        return results

    def _extract_bool_list(self, block_name: str, lines: list[str], *, prompt_override: str | None = None) -> tuple[str, Any | None]:
        normalized = self._normalize_lines(lines)
        system_prompt = self.prompts.get_system_prompt_text().strip()
        user_prompt_template = self.prompts.get_user_prompt_text()
        template = prompt_override if prompt_override is not None else f"{system_prompt}\n\n{user_prompt_template}".strip()
        prompt_rendered = template.format(vac_reqs=chr(10).join(normalized))
        if not normalized:
            return "", None
        raw = self.llm.call(prompt_text=prompt_rendered, iteration=0)
        response_text = self._extract_response_text(raw)
        if response_text is None:
            raise ValueError(f"LLM вернул пустой ответ для блока: {block_name}. raw={raw!r}")
        if isinstance(response_text, str) and not response_text.strip():
            raise ValueError(f"LLM вернул пустую строку для блока: {block_name}. raw={raw!r}")
        expression = self._extract_bool_expression(response_text)
        if not expression:
            raise ValueError(f"LLM не вернул валидное булево выражение для блока: {block_name}")
        return expression, raw

    def _extract_response_text(self, raw: Any) -> str | list[Any] | dict[str, Any] | None:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, list):
            return raw
        if not isinstance(raw, dict):
            return None
        response = raw.get("response")
        if isinstance(response, str):
            return response
        if isinstance(response, (list, dict)):
            return response
        markdown = raw.get("markdown")
        if isinstance(markdown, str):
            return markdown
        if isinstance(markdown, (list, dict)):
            return markdown
        if isinstance(response, dict):
            nested_response = response.get("response")
            if isinstance(nested_response, str):
                return nested_response
            if isinstance(nested_response, (list, dict)):
                return nested_response
            nested_markdown = response.get("markdown")
            if isinstance(nested_markdown, str):
                return nested_markdown
            if isinstance(nested_markdown, (list, dict)):
                return nested_markdown
        return None

    def _extract_bool_expression(self, text: str | list[Any] | dict[str, Any]) -> str:
        if isinstance(text, dict):
            if isinstance(text.get("query"), str):
                return text["query"].strip()
            if isinstance(text.get("bool"), str):
                return text["bool"].strip()
            return ""
        if isinstance(text, list):
            parts = [str(x).strip() for x in text if str(x).strip()]
            return " AND ".join(f"({x})" for x in parts)
        raw = text.strip()
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, flags=re.IGNORECASE)
        if fenced:
            raw = fenced.group(1).strip()
        if raw.startswith("{") or raw.startswith("["):
            try:
                data = json.loads(raw)
            except Exception:
                return raw
            return self._extract_bool_expression(data)
        return raw

    def _join_group(self, bools: list[str], operator: str) -> str:
        if not bools:
            return ""
        if len(bools) == 1:
            return f"({bools[0]})"
        glue = f" {operator} "
        return "(" + glue.join(f"({item})" for item in bools) + ")"

    def _replace_and_with_or(self, expression: str) -> str:
        if not expression:
            return ""
        return re.sub(r"\bAND\b", "OR", expression, flags=re.IGNORECASE)

    def _unwrap_outer_parens(self, expression: str) -> str:
        expr = (expression or "").strip()
        while len(expr) >= 2 and expr[0] == "(" and expr[-1] == ")":
            depth = 0
            wraps_whole = True
            for i, ch in enumerate(expr):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0 and i != len(expr) - 1:
                        wraps_whole = False
                        break
            if wraps_whole and depth == 0:
                expr = expr[1:-1].strip()
                continue
            break
        return expr

    def _clause_list_from_required(self, required: str, source_lines: list[str]) -> list[str]:
        expr = self._unwrap_outer_parens(required)
        clauses = self._split_top_level(expr, "AND") if expr else []
        clauses = [self._unwrap_outer_parens(c).strip() for c in clauses if c and c.strip()]
        if len(clauses) <= 1 and len(source_lines) > 1:
            # LLM иногда возвращает одну скобочную кашу — тогда режем по исходным пунктам требований.
            clauses = [self._unwrap_outer_parens(line.lstrip("- ").rstrip(";").strip()) for line in source_lines if line.strip()]
        return [c for c in clauses if c]

    def _split_top_level(self, expression: str, operator: str) -> list[str]:
        op = f" {operator.upper()} "
        parts: list[str] = []
        depth = 0
        start = 0
        i = 0
        expr = expression.strip()
        upper_expr = expr.upper()
        while i < len(expr):
            ch = expr[i]
            if ch == "(":
                depth += 1
            elif ch == ")" and depth > 0:
                depth -= 1
            if depth == 0 and upper_expr[i : i + len(op)] == op:
                parts.append(expr[start:i].strip())
                i += len(op)
                start = i
                continue
            i += 1
        tail = expr[start:].strip()
        if tail:
            parts.append(tail)
        return [p for p in parts if p]

    def _build_search_plan(
        self,
        required: str,
        desirable: str,
        tasks: str,
        *,
        source_lines: list[str] | None = None,
    ) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
        required_clauses = self._clause_list_from_required(required, source_lines or [])
        required_variants = self._build_required_variants(required_clauses) if required_clauses else ([required] if required else [])

        plan: list[tuple[str, str]] = []
        meta: list[dict[str, Any]] = []

        def add(label: str, parts: list[str], blocks: dict[str, str]) -> None:
            parts = [p for p in parts if p]
            if not parts:
                return
            if len(parts) == 1:
                query = parts[0]
            elif len(parts) == 2:
                query = f"{parts[0]} AND ({parts[1]})"
            else:
                query = f"{parts[0]} AND ({' OR '.join(parts[1:])})"
            if any(existing == query for _, existing in plan):
                return
            plan.append((label, query))
            meta.append({"stage": label, "query": query})

        base_required = required_variants[0] if required_variants else ""
        add(
            "Этап 1: обязательные",
            [base_required, desirable, tasks],
            {BLOCK_REQUIRED: base_required, BLOCK_DESIRABLE: desirable, BLOCK_TASKS: tasks},
        )
        for remove_count, req_variant in enumerate(required_variants[1:], start=1):
            add(
                f"Этап 1.{remove_count}: убрать {remove_count} обяз.",
                [req_variant, desirable, tasks],
                {BLOCK_REQUIRED: req_variant, BLOCK_DESIRABLE: desirable, BLOCK_TASKS: tasks},
            )
        return plan, meta

    def _build_required_variants(self, clauses: list[str]) -> list[str]:
        """
        Варианты ослабления в text: все требования, затем убрать 1, затем 2, …
        Последний этап — одно оставшееся требование (text не пустеет).
        """
        clauses = [c.strip() for c in clauses if c.strip()]
        if not clauses:
            return []
        if len(clauses) == 1:
            return [self._join_group([clauses[0]], "AND")]

        variants: list[str] = []
        total = len(clauses)
        seen: set[str] = set()
        indices = list(range(total))

        for remove_count in range(0, total):
            keep_count = total - remove_count
            for combo in self._combinations(indices, keep_count):
                expr = self._join_group([clauses[i] for i in combo], "AND")
                if not expr or expr in seen:
                    continue
                seen.add(expr)
                variants.append(expr)
        return variants

    def _combinations(self, items: list[int], k: int) -> list[tuple[int, ...]]:
        if k <= 0:
            return []
        if k >= len(items):
            return [tuple(items)]
        result: list[tuple[int, ...]] = []

        def backtrack(start: int, path: list[int]) -> None:
            if len(path) == k:
                result.append(tuple(path))
                return
            remaining = k - len(path)
            for idx in range(start, len(items) - remaining + 1):
                path.append(items[idx])
                backtrack(idx + 1, path)
                path.pop()

        backtrack(0, [])
        # Сначала снимаем требования с меньшими индексами (0, 1, 2, …).
        return sorted(result, key=lambda tpl: tuple(i for i in items if i not in tpl))
