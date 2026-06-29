from __future__ import annotations

from pathlib import Path

from app.core.settings import settings


def get_resume_pdf_dir() -> Path:
    directory = Path(settings.resume_pdf_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def resume_pdf_path(resume_id: str) -> Path:
    return get_resume_pdf_dir() / f"{str(resume_id).strip()}.pdf"


def save_resume_pdf(*, resume_id: str, content: bytes) -> Path:
    path = resume_pdf_path(resume_id)
    path.write_bytes(content)
    return path


def resume_pdf_exists(resume_id: str) -> bool:
    path = resume_pdf_path(resume_id)
    return path.is_file() and path.stat().st_size > 0
