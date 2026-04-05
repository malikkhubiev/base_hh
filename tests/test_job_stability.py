from __future__ import annotations

from unittest.mock import patch

from app.services.job_stability import candidate_passes_job_stability


def test_empty_experience_passes() -> None:
    assert candidate_passes_job_stability(
        None,
        min_stay_months=3,
        allowed_short_jobs=2,
        jump_mode="total",
        max_not_employed_months=6,
    )


def test_consecutive_short_jobs_fail() -> None:
    exp = [
        {"start": "2020-01", "end": "2020-03"},
        {"start": "2020-04", "end": "2020-05"},
        {"start": "2020-06", "end": "2020-07"},
    ]
    ok = candidate_passes_job_stability(
        exp,
        min_stay_months=12,
        allowed_short_jobs=1,
        jump_mode="consecutive",
        max_not_employed_months=120,
    )
    assert ok is False


@patch("app.services.job_stability._now_year_month")
def test_not_employed_too_long(mock_now) -> None:
    mock_now.return_value = (2026, 4)
    exp = [
        {"start": "2015-01", "end": "2018-01"},
    ]
    ok = candidate_passes_job_stability(
        exp,
        min_stay_months=1,
        allowed_short_jobs=10,
        jump_mode="total",
        max_not_employed_months=12,
    )
    assert ok is False
