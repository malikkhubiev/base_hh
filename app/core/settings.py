from __future__ import annotations

import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "HH Optimizer UI"

    llm_url: str = Field(default_factory=lambda: os.getenv("LLM_URL", "http://int-srv:8085/metrics/ecm/gpt"))
    llm_token_param: str = Field(default_factory=lambda: os.getenv("LLM_TOKEN_PARAM", "?token=DebugEcmTest"))
    hh_token_url: str = Field(default_factory=lambda: os.getenv("HH_TOKEN_URL", "http://int-srv:8085/metrics/hh/accessToken"))
    hh_oauth_token_url: str = Field(default_factory=lambda: os.getenv("HH_OAUTH_TOKEN_URL", "https://hh.ru/oauth/token"))

    # Token source:
    # - ssp_soft: token from internal endpoint
    # - base: OAuth token via client credentials
    default_token_source: str = Field(default_factory=lambda: os.getenv("DEFAULT_TOKEN_SOURCE", "ssp_soft"))
    base_client_id: str | None = Field(default_factory=lambda: os.getenv("BASE_CLIENT_ID"))
    base_client_secret: str | None = Field(default_factory=lambda: os.getenv("BASE_CLIENT_SECRET"))

    use_mock_llm: bool = Field(default_factory=lambda: os.getenv("USE_MOCK_LLM", "false").lower() == "true")
    use_mock_hh: bool = Field(default_factory=lambda: os.getenv("USE_MOCK_HH", "false").lower() == "true")

    area_id: int = Field(default_factory=lambda: int(os.getenv("AREA_ID", "113")))
    professional_roles: list[str] = Field(
        default_factory=lambda: [r.strip() for r in os.getenv("PROFESSIONAL_ROLES", "96,113").split(",") if r.strip()]
    )


settings = Settings()

