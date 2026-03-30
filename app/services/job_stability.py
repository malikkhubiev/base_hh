from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


def _now_year_month() -> tuple[int, int]:
    dt = datetime.now(timezone.utc)
    return dt.year, dt.month


def _parse_year_month(value: Any) -> tuple[int, int] | None:
    """
    Extract (year, month) from various HH-ish date strings.
    Examples: "2020-05", "05.2020", "2020/05", "2020-5".
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    # Common "YYYY-MM" / "YYYY.MM" patterns.
    m = re.search(r"(19\d{2}|20\d{2})[.\-/](0?[1-9]|1[0-2])", s)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Common "MM.YYYY" patterns.
    m = re.search(r"(0?[1-9]|1[0-2])[.\-/](19\d{2}|20\d{2})", s)
    if m:
        return int(m.group(2)), int(m.group(1))

    # Fallback: try first 6 chars if they look like YYYYMM.
    if len(s) >= 6 and s[:6].isdigit():
        y = int(s[:4])
        mo = int(s[4:6])
        if 1 <= mo <= 12:
            return y, mo

    return None


def _is_present_end(value: Any) -> bool:
    if value is None:
        return True
    s = str(value).strip().lower()
    if not s:
        return True
    return any(
        phrase in s
        for phrase in [
            "по настоящее",
            "по наст.",
            "настоящее время",
            "сейчас",
            "present",
            "current",
            "ongoing",
            "не указ",
        ]
    )


def _months_between(start: tuple[int, int], end: tuple[int, int]) -> int:
    return (end[0] - start[0]) * 12 + (end[1] - start[1])


def candidate_passes_job_stability(
    experience_list: list[dict[str, Any]] | None,
    *,
    min_stay_months: int,
    allowed_short_jobs: int,
    jump_mode: str,
    max_not_employed_months: int,
) -> bool:
    """
    Implements filters from `todo.txt`:
    - reject if candidate has "too many" short job stays
    - reject if last job end is older than max_not_employed_months
    """
    if not experience_list:
        return True

    now_y, now_m = _now_year_month()

    # Compute durations for each experience entry.
    durations_months: list[int | None] = []
    for it in experience_list:
        if not isinstance(it, dict):
            durations_months.append(None)
            continue
        start_parsed = _parse_year_month(it.get("start"))
        end_parsed: tuple[int, int] | None = None
        end_raw = it.get("end")
        if _is_present_end(end_raw):
            end_parsed = (now_y, now_m)
        else:
            end_parsed = _parse_year_month(end_raw)

        if start_parsed is None or end_parsed is None:
            durations_months.append(None)
            continue

        dur = _months_between(start_parsed, end_parsed)
        durations_months.append(max(0, dur))

    short_flags: list[bool] = [
        (d is not None and d < min_stay_months) for d in durations_months
    ]

    # Count short jobs.
    short_total = sum(1 for f in short_flags if f)

    if jump_mode == "consecutive":
        max_consecutive = 0
        cur = 0
        for f in short_flags:
            if f:
                cur += 1
                max_consecutive = max(max_consecutive, cur)
            else:
                cur = 0
        if max_consecutive > allowed_short_jobs:
            return False
    else:
        # "total" / "вообще прыгун"
        if short_total > allowed_short_jobs:
            return False

    # "Maximum not employed" check uses the most recent job ("последнее место работы")
    # interpreted as the entry with the latest parsed start date.
    best_idx = None
    best_start: tuple[int, int] | None = None
    for idx, it in enumerate(experience_list):
        if not isinstance(it, dict):
            continue
        start_parsed = _parse_year_month(it.get("start"))
        if start_parsed is None:
            continue
        if best_start is None or start_parsed > best_start:
            best_start = start_parsed
            best_idx = idx

    last_job = experience_list[best_idx] if best_idx is not None else experience_list[0]
    end_raw = last_job.get("end") if isinstance(last_job, dict) else None
    if not _is_present_end(end_raw) and max_not_employed_months is not None:
        end_parsed = _parse_year_month(end_raw)
        if end_parsed is not None:
            months_ago = _months_between(end_parsed, (now_y, now_m))
            if months_ago > max_not_employed_months:
                return False

    return True

