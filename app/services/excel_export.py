"""Сборка XLSX для workflow (поиск / светофор / экспорт)."""

from __future__ import annotations

import io
import json
from datetime import datetime
import logging
from typing import Any

from app.core.tracing import trace_step

try:
    import xlsxwriter  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional dependency
    xlsxwriter = None  # type: ignore[assignment]

_log = logging.getLogger(__name__)


def xlsxwriter_available() -> bool:
    return xlsxwriter is not None


def build_search_excel_bytes(
    *,
    request_text: str,
    level_queries: dict[str, str] | None,
    queries_with_exclusions: dict[str, str] | None,
    hh_search_urls: dict[str, str] | None,
    selected_level: str | None,
    found_counts: dict[str, int] | None,
    candidates_by_level_raw: dict[str, list[Any]],
    traffic_light_candidates: list[Any],
    traffic_light_candidates_by_level: dict[str, list[Any]] | None = None,
    started_at: datetime,
    bool_finished_at: datetime,
    hh_finished_at: datetime,
    finished_at: datetime,
    ran_traffic_light: bool,
) -> tuple[bytes, str]:
    """
    Формирует книгу Excel:
    - «Запрос» (полная сводка: исходный запрос, булевы запросы, HH-ссылки, найденные количества, светофор)
    - «Уровень 1/2/3» (кандидаты по каждому уровню отдельно)
    - «Светофор Уровень N» (для выбранного уровня) или несколько листов «Светофор Уровень 1/2/3»
    """
    trace_step(
        _log,
        "excel_export",
        "build_search_excel_bytes.start",
        ran_traffic_light=ran_traffic_light,
        found_counts=found_counts,
        request_preview=(request_text or "")[:200],
    )
    if xlsxwriter is None:
        raise RuntimeError("xlsxwriter is not installed")

    def _level_number(lvl: str | None) -> str | None:
        if not lvl:
            return None
        s = str(lvl)
        # ожидаем форматы "Уровень 1/2/3"
        for n in ("1", "2", "3"):
            if s.strip().endswith(n):
                return n
        return None

    def _sheet_safe_name(name: str) -> str:
        # Excel sheet name max 31 chars, disallow: []:*?/\
        bad = set('[]:*?/\\')
        cleaned = "".join("_" if ch in bad else ch for ch in (name or ""))
        cleaned = cleaned.strip() or "Sheet"
        return cleaned[:31]

    def _tl_get(obj: Any, key: str, default: Any = "") -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    levels = ["Уровень 1", "Уровень 2", "Уровень 3"]
    candidates_by_level: dict[str, list[dict]] = {}
    for lvl in levels:
        out: list[dict] = []
        for it in (candidates_by_level_raw.get(lvl) or []):
            if isinstance(it, dict):
                out.append(it)
        candidates_by_level[lvl] = out

    def _safe_duration_sec(left: datetime, right: datetime) -> float:
        return max(0.0, (right - left).total_seconds())

    def _format_duration(duration_sec: float) -> str:
        if duration_sec < 1:
            return f"{duration_sec:.3f} s"
        mins = int(duration_sec // 60)
        secs = duration_sec - mins * 60
        return f"{mins} min {secs:.3f} s"

    duration_sec = _safe_duration_sec(started_at, finished_at)
    bool_duration_sec = _safe_duration_sec(started_at, bool_finished_at)
    hh_duration_sec = _safe_duration_sec(bool_finished_at, hh_finished_at)
    tl_duration_sec = _safe_duration_sec(hh_finished_at, finished_at) if ran_traffic_light else 0.0
    timings = {
        "total_sec": round(duration_sec, 6),
        "bool_sec": round(bool_duration_sec, 6),
        "hh_sec": round(hh_duration_sec, 6),
        "tl_sec": round(tl_duration_sec, 6),
    }
    has_timing_anomaly = bool_finished_at < started_at or hh_finished_at < bool_finished_at or finished_at < hh_finished_at
    trace_step(
        _log,
        "excel_export",
        "build_search_excel_bytes.timing_breakdown",
        ran_traffic_light=ran_traffic_light,
        anomaly=has_timing_anomaly,
        **timings,
    )
    if has_timing_anomaly:
        trace_step(
            _log,
            "excel_export",
            "build_search_excel_bytes.timing_anomaly",
            started_at=started_at.isoformat(),
            bool_finished_at=bool_finished_at.isoformat(),
            hh_finished_at=hh_finished_at.isoformat(),
            finished_at=finished_at.isoformat(),
        )

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

    # Булевы запросы / запросы с исключениями / HH ссылки
    sheet_req.write(row, 0, "Булевы запросы по уровням", bold)
    row += 1
    sheet_req.write(row, 0, "Уровень", bold)
    sheet_req.write(row, 1, "Булевый запрос", bold)
    sheet_req.write(row, 2, "С исключениями", bold)
    sheet_req.write(row, 3, "Ссылка HH", bold)
    row += 1
    for lvl in levels:
        sheet_req.write(row, 0, lvl)
        sheet_req.write(row, 1, (level_queries or {}).get(lvl, "") if level_queries else "")
        sheet_req.write(row, 2, (queries_with_exclusions or {}).get(lvl, "") if queries_with_exclusions else "")
        sheet_req.write(row, 3, (hh_search_urls or {}).get(lvl, "") if hh_search_urls else "")
        row += 1
    row += 1

    total_found = sum(int(v or 0) for v in (found_counts or {}).values())
    sheet_req.write(row, 0, "Кандидатов в выборке:", bold)
    sheet_req.write(row, 1, total_found)
    row += 1

    sheet_req.write(row, 0, "Найдено по уровням:", bold)
    sheet_req.write(row, 1, json.dumps(found_counts or {}, ensure_ascii=False))
    row += 2

    sheet_req.write(row, 0, "Выбранный уровень (для светофора):", bold)
    sheet_req.write(row, 1, selected_level or "")
    row += 2

    sheet_req.write(row, 0, "Общее время выполнения:", bold)
    sheet_req.write(
        row,
        1,
        f"{_format_duration(duration_sec)} | "
        f"{started_at.strftime('%d.%m.%Y %H:%M:%S')} ... {finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
    )
    row += 2

    sheet_req.write(row, 0, "Время выполнения булевого запроса:", bold)
    sheet_req.write(
        row,
        1,
        f"{_format_duration(bool_duration_sec)} | "
        f"{started_at.strftime('%d.%m.%Y %H:%M:%S')} ... {bool_finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
    )
    row += 1
    sheet_req.write(row, 0, "Время поиска в HH.ru:", bold)
    sheet_req.write(
        row,
        1,
        f"{_format_duration(hh_duration_sec)} | "
        f"{bool_finished_at.strftime('%d.%m.%Y %H:%M:%S')} ... {hh_finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
    )
    row += 1
    if ran_traffic_light:
        sheet_req.write(row, 0, "Время построения Светофора:", bold)
        sheet_req.write(
            row,
            1,
            f"{_format_duration(tl_duration_sec)} | "
            f"{hh_finished_at.strftime('%d.%m.%Y %H:%M:%S')} ... {finished_at.strftime('%d.%m.%Y %H:%M:%S')}",
        )
        row += 2
    else:
        row += 1

    # Листы кандидатов по уровням (вместо одного общего листа)
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

    for lvl in levels:
        lvl_candidates = candidates_by_level.get(lvl) or []
        sheet_lvl = workbook.add_worksheet(lvl)
        sheet_lvl.write(0, 0, "Уровень:", bold)
        sheet_lvl.write(0, 1, lvl)

        if not lvl_candidates:
            sheet_lvl.write(2, 0, "Нет кандидатов", bold)
            continue

        all_keys: list[str] = []
        seen: set[str] = set()
        for k in first_keys:
            if k == "employer":
                continue
            if any(isinstance(c, dict) and k in c for c in lvl_candidates):
                all_keys.append(k)
                seen.add(k)
        for c in lvl_candidates:
            if not isinstance(c, dict):
                continue
            for k in c.keys():
                if k == "employer" or k in seen:
                    continue
                all_keys.append(k)
                seen.add(k)
        headers = all_keys
        header_row = 2
        for col, h in enumerate(headers):
            sheet_lvl.write(header_row, col, h, bold)
        r = header_row + 1
        for c in lvl_candidates:
            for col, key in enumerate(headers):
                val = c.get(key)
                if val is None:
                    out = ""
                elif isinstance(val, (dict, list)):
                    out = json.dumps(val, ensure_ascii=False)
                else:
                    out = str(val)
                sheet_lvl.write(r, col, out)
            r += 1

    def _write_tl_sheet(sheet_name: str, level_label: str | None, items: list[Any]) -> None:
        sheet_tl = workbook.add_worksheet(_sheet_safe_name(sheet_name))
        sheet_tl.write(0, 0, "Светофор для уровня:", bold)
        sheet_tl.write(0, 1, level_label or "")

        headers_tl = ["Кандидат", "Локация", "Позиция", "Ссылка", "Итог +"]
        for col, h in enumerate(headers_tl):
            sheet_tl.write(2, col, h, bold)

        r = 3
        for c in items or []:
            name = _tl_get(c, "candidate_name", "") or _tl_get(c, "id", "")
            location = _tl_get(c, "location", "") or ""
            title = _tl_get(c, "title", "") or ""
            resume_url = _tl_get(c, "resume_url", "") or ""
            score_raw = _tl_get(c, "color_score_percent", 0) or 0
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

    # Светофоры: либо один (старый формат списка), либо несколько (по уровням).
    if traffic_light_candidates_by_level:
        # Пишем только те уровни, которые передали.
        for lvl in levels:
            items = traffic_light_candidates_by_level.get(lvl) or []
            if not items:
                continue
            n = _level_number(lvl) or ""
            _write_tl_sheet(f"Светофор Уровень {n}".strip(), lvl, items)
    else:
        n = _level_number(selected_level) or ""
        _write_tl_sheet(f"Светофор Уровень {n}".strip() if n else "Светофор", selected_level, traffic_light_candidates or [])

    workbook.close()
    output.seek(0)
    filename = f"hh_search_{started_at.strftime('%Y%m%d_%H%M%S')}.xlsx"
    raw = output.getvalue()
    trace_step(
        _log,
        "excel_export",
        "build_search_excel_bytes.done",
        filename=filename,
        bytes=len(raw),
        tl_rows=len(traffic_light_candidates),
    )
    return raw, filename
