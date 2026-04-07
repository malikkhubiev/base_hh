import logging
import time
from typing import Callable

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.logging import setup_logging
from app.core.settings import settings
from app.core.tracing import (
    app_trace_enabled,
    get_trace_id,
    new_trace_id,
    reset_trace_id,
    set_trace_id,
    trace_step,
)

logger = logging.getLogger(__name__)
_http_logger = logging.getLogger("app.http")


class TraceRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):  # type: ignore[override]
        trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
        var_token = set_trace_id(trace_id)
        t0 = time.perf_counter()
        body_preview: str | None = None
        if app_trace_enabled() and request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()

                async def receive() -> dict:
                    return {"type": "http.request", "body": body, "more_body": False}

                request = Request(request.scope, receive)
                if body:
                    body_preview = body[:8192].decode("utf-8", errors="replace")
            except Exception as exc:
                body_preview = f"<body_read_error {exc!r}>"

        trace_step(
            _http_logger,
            "http",
            "request.start",
            method=request.method,
            path=request.url.path,
            query=dict(request.query_params) if request.query_params else None,
            client=request.client.host if request.client else None,
            body_preview=body_preview,
        )
        try:
            response = await call_next(request)
            ms = round((time.perf_counter() - t0) * 1000, 2)
            trace_step(
                _http_logger,
                "http",
                "request.done",
                status_code=response.status_code,
                duration_ms=ms,
            )
            return response
        except Exception:
            ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.exception(
                "request.failed trace_id=%s path=%s duration_ms=%s",
                get_trace_id(),
                request.url.path,
                ms,
            )
            trace_step(_http_logger, "http", "request.exception", duration_ms=ms)
            raise
        finally:
            reset_trace_id(var_token)


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(TraceRequestMiddleware)
    app.include_router(api_router)
    return app


app = create_app()
