import logging
import os

from app.core.tracing import install_trace_context_filter


def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    fmt = "%(asctime)s - %(levelname)s - [trace=%(trace_id)s] - %(name)s - %(message)s"
    if not root.handlers:
        logging.basicConfig(level=log_level, format=fmt)
    else:
        root.setLevel(log_level)
        formatter = logging.Formatter(fmt)
        for h in root.handlers:
            h.setLevel(log_level)
            h.setFormatter(formatter)
    install_trace_context_filter()

