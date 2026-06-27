"""structlog has been listed in requirements.txt since the original scaffold, never actually
configured anywhere — same "looks present, isn't real" pattern as slowapi was before §18, just
smaller. Wired up for real here, deliberately as an stdlib-logging processor rather than
rewriting the 9 existing `logging.getLogger(name)` call sites to use structlog's own API
directly: every `logger.warning("...", exc)` call across this codebase keeps working exactly
as written, but now renders as structured JSON (timestamp, level, logger name, the message,
and any extra fields) instead of a plain text line — real value, zero call-site risk.

NOTE: written against structlog's documented stdlib-integration API from training knowledge —
not exercised against a live install (no network access in this sandbox). The shape of
`structlog.configure(...)` + `ProcessorFormatter` has been stable for a long time, but verify
it against the pinned version before relying on it, same caveat as every other "real but
sandbox-unverified" piece in this codebase.
"""

import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    """Call once, at process startup (see main.py) — before any other module's
    `logging.getLogger(...)` call actually emits anything, so every log line in the process
    is structured from the first one, not just ones emitted after some arbitrary later point."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Plain-text in development (easier to read while actively coding), real JSON in
    # production (what a log aggregator — Datadog/CloudWatch/whatever — actually wants).
    renderer = structlog.dev.ConsoleRenderer() if settings.app_env == "development" else structlog.processors.JSONRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)

    # Quiet down noisy third-party loggers that would otherwise flood structured output with
    # their own (unstructured) lines — uvicorn's access log is genuinely useful, left as-is.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
