from __future__ import annotations

import os
from urllib.parse import quote_plus

from pydantic import BaseModel, Field, computed_field


class Settings(BaseModel):
    app_name: str = "HH Optimizer UI"

    llm_url: str = Field(default_factory=lambda: os.getenv("LLM_URL", "http://int-srv:8085/metrics/ecm/gpt"))
    llm_token_param: str = Field(default_factory=lambda: os.getenv("LLM_TOKEN_PARAM", "?token=DebugEcmTest"))
    hh_token_url: str = Field(default_factory=lambda: os.getenv("HH_TOKEN_URL", "http://int-srv:8085/metrics/hh/accessToken"))
    # Токен HH всегда берется из внутреннего SSP-эндпоинта.
    token_source: str = "ssp"

    area_id: int = Field(default_factory=lambda: int(os.getenv("AREA_ID", "113")))

    db_host: str = Field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: str = Field(default_factory=lambda: os.getenv("DB_PORT", "5432"))
    db_user: str = Field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    db_password: str = Field(default_factory=lambda: os.getenv("DB_PASSWORD", "mysecretpassword"))
    db_name: str = Field(default_factory=lambda: os.getenv("DB_NAME", "fastapi_db"))
    db_ssl_mode: str = Field(default_factory=lambda: os.getenv("DB_SSL_MODE", "disable"))
    database_url_override: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    # Локальное хранилище PDF резюме HH (скачиваются при просмотре полного резюме).
    resume_pdf_dir: str = Field(default_factory=lambda: os.getenv("RESUME_PDF_DIR", "data/resumes"))

    # Прокси для HH: по умолчанию игнорируем системный HTTP(S)_PROXY (частая причина ProxyError на Windows).
    hh_trust_env_proxy: bool = Field(
        default_factory=lambda: os.getenv("HH_TRUST_ENV_PROXY", "").lower() in ("1", "true", "yes")
    )
    hh_http_proxy: str = Field(default_factory=lambda: os.getenv("HH_HTTP_PROXY", ""))
    hh_https_proxy: str = Field(default_factory=lambda: os.getenv("HH_HTTPS_PROXY", ""))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        override = (self.database_url_override or "").strip()
        if override:
            return override
        encoded_password = quote_plus(self.db_password)
        url = f"postgresql://{self.db_user}:{encoded_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        if self.db_ssl_mode != "disable":
            url += f"?sslmode={self.db_ssl_mode}"
        return url


settings = Settings()
