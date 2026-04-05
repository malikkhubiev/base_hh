"""Сборка XLSX для workflow (поиск / светофор / экспорт)."""

from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any

try:
    import xlsxwriter  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional dependency
    xlsxwriter = None  # type: ignore[assignment]


def xlsxwriter_available() -> bool:
    return xlsxwriter is not None


def build_search_excel_bytes(
    *,
    request_text: str,
    found_counts: dict[str, int] | None,
    candidates_by_level_raw: dict[str, list[Any]],
    traffic_light_candidates: list[Any],
    started_at: datetime,
    bool_finished_at: datetime,
    hh_finished_at: datetime,
    finished_at: datetime,
    ran_traffic_light: bool,
) -> tuple[bytes, str]:
    """
    Формирует книгу Excel: лист «Запрос», при наличии данных — «Кандидаты HH», при наличии оценок — «Светофор».
    """
    if xlsxwriter is None:
        raise RuntimeError("xlsxwriter is not installed")

    hh_candidates: list[dict] = []
    for items in candidates_by_level_raw.values():
        for it in items or []:
            if isinstance(it, dict):
                hh_candidates.append(it)

    duration_sec = (finished_at - started_at).total_seconds()
    bool_duration_sec = (bool_finished_at - started_at).total_seconds()
    hh_duration_sec = (hh_finished_at - bool_finished_at).total_seconds()
    tl_duration_sec = (finished_at - hh_finished_at).total_seconds() if ran_traffic_light else 0.0

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})

    sheet_req = workbook.add_worksheet("Запрос")
    bold = workbook.add_format({"bold": True})
    tl_green_fmt = workbook.add_format({"bg_color": "#DDF8E7", "border": 1, "align": "center"})
    tl_yellow_fmt = workbook.add_format({"bg_color": "#FEEAC3", "border": 1, "align": "center"})
    tl_red_fmt = workbook.add_format({"bg_color": "#FFB3B3", "border": 1, "align": "center"})

    row = 0
    sheet_req.write(row, 0, "Запрос:", bold)
    sheet_req.write(row, 1, request_text or "")
    row += 2

    total_found = sum(int(v or 0) for v in (found_counts or {}).values())
    sheet_req.write(row, 0, "Кандидатов в выборке:", bold)
    sheet_req.write(row, 1, total_found)
    row += 1

    sheet_req.write(row, 0, "Общее время выполнения:", bold)
    sheet_req.write(
        row,
        1,
        f"{int(duration_sec // 60)} min {int(duration_sec % 60)} s | "
        f"{started_at.strftime('%d.%m.%Y %H:%M:%S')} ... {finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
    )
    row += 2

    sheet_req.write(row, 0, "Время выполнения булевого запроса:", bold)
    sheet_req.write(
        row,
        1,
        f"{int(bool_duration_sec // 60)} min {int(bool_duration_sec % 60)} s | "
        f"{started_at.strftime('%d.%m.%Y %H:%M:%S')} ... {bool_finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
    )
    row += 1
    sheet_req.write(row, 0, "Время поиска в HH.ru:", bold)
    sheet_req.write(
        row,
        1,
        f"{int(hh_duration_sec // 60)} min {int(hh_duration_sec % 60)} s | "
        f"{bool_finished_at.strftime('%d.%m.%Y %H:%M:%S')} ... {hh_finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
    )
    row += 1
    sheet_req.write(row, 0, "Время построения Светофора:", bold)
    if ran_traffic_light:
        sheet_req.write(
            row,
            1,
            f"{int(tl_duration_sec // 60)} min {int(tl_duration_sec % 60)} s | "
            f"{hh_finished_at.strftime('%d.%m.%Y %H:%M:%S')} ... {finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
        )
    else:
        sheet_req.write(
            row,
            1,
            f"0 min 0 s | {hh_finished_at.strftime('%d.%m.%Y %H:%M:%S')} ... {hh_finished_at.strftime('%d.%m.%Y %H:%M:%S')} "
            f"(не выполнялось)",
        )
    row += 2

    if hh_candidates:
        sheet_hh = workbook.add_worksheet("Кандидаты HH")
        first_keys = [
            "id",
            "first_name",
            "last_name",
            "title",
            "alternate_url",
            "url",
            "age",
            "area",
            "salary",
            "experience",
            "skills",
            "tags",
            "created_at",
            "updated_at",
        ]
        all_keys: list[str] = []
        seen: set[str] = set()
        for k in first_keys:
            if k == "employer":
                continue
            if any(isinstance(c, dict) and k in c for c in hh_candidates):
                all_keys.append(k)
                seen.add(k)
        for c in hh_candidates:
            if not isinstance(c, dict):
                continue
            for k in c.keys():
                if k == "employer" or k in seen:
                    continue
                all_keys.append(k)
                seen.add(k)
        headers = all_keys
        for col, h in enumerate(headers):
            sheet_hh.write(0, col, h, bold)
        r = 1
        for c in hh_candidates:
            for col, key in enumerate(headers):
                val = c.get(key)
                if val is None:
                    out = ""
                elif isinstance(val, (dict, list)):
                    out = json.dumps(val, ensure_ascii=False)
                else:
                    out = str(val)
                sheet_hh.write(r, col, out)
            r += 1

    if traffic_light_candidates:
        sheet_tl = workbook.add_worksheet("Светофор")
        headers_tl = ["Кандидат", "Локация", "Позиция", "Ссылка", "Итог +"]
        for col, h in enumerate(headers_tl):
            sheet_tl.write(0, col, h, bold)
        r = 1
        for c in traffic_light_candidates:
            name = getattr(c, "candidate_name", "") or getattr(c, "id", "")
            location = getattr(c, "location", "") or ""
            title = getattr(c, "title", "") or ""
            resume_url = getattr(c, "resume_url", "") or ""
            score_raw = getattr(c, "color_score_percent", 0) or 0
            try:
                score = float(score_raw)
            except (TypeError, ValueError):
                score = 0.0
            score_percent = f"{int(round(score))}%"
            sheet_tl.write(r, 0, str(name))
            sheet_tl.write(r, 1, str(location))
            sheet_tl.write(r, 2, str(title))
            sheet_tl.write(r, 3, resume_url)
            if score >= 60:
                score_fmt = tl_green_fmt
            elif score >= 40:
                score_fmt = tl_yellow_fmt
            else:
                score_fmt = tl_red_fmt
            sheet_tl.write(r, 4, score_percent, score_fmt)
            r += 1

    workbook.close()
    output.seek(0)
    filename = f"hh_search_{started_at.strftime('%Y%m%d_%H%M%S')}.xlsx"
    return output.getvalue(), filename
