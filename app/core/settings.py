from __future__ import annotations

import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "HH Optimizer UI"

    llm_url: str = Field(default_factory=lambda: os.getenv("LLM_URL", "http://int-srv:8085/metrics/ecm/gpt"))
    llm_token_param: str = Field(default_factory=lambda: os.getenv("LLM_TOKEN_PARAM", "?token=DebugEcmTest"))
    hh_token_url: str = Field(default_factory=lambda: os.getenv("HH_TOKEN_URL", "http://int-srv:8085/metrics/hh/accessToken"))
    # Токен HH всегда берется из внутреннего SSP-эндпоинта.
    token_source: str = "ssp"

    area_id: int = Field(default_factory=lambda: int(os.getenv("AREA_ID", "113")))

    # PostgreSQL (опционально). Пример: postgresql://user:pass@host:5432/dbname
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    # Локальное хранилище PDF резюме HH (скачиваются при просмотре полного резюме).
    resume_pdf_dir: str = Field(default_factory=lambda: os.getenv("RESUME_PDF_DIR", "data/resumes"))

    # Прокси для HH: по умолчанию игнорируем системный HTTP(S)_PROXY (частая причина ProxyError на Windows).
    hh_trust_env_proxy: bool = Field(
        default_factory=lambda: os.getenv("HH_TRUST_ENV_PROXY", "").lower() in ("1", "true", "yes")
    )
    hh_http_proxy: str = Field(default_factory=lambda: os.getenv("HH_HTTP_PROXY", ""))
    hh_https_proxy: str = Field(default_factory=lambda: os.getenv("HH_HTTPS_PROXY", ""))
settings = Settings()

