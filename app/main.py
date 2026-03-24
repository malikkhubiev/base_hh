from fastapi import FastAPI

from app.api.router import api_router
from app.core.logging import setup_logging
from app.core.settings import settings


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title=settings.app_name)
    app.include_router(api_router)
    return app


app = create_app()

