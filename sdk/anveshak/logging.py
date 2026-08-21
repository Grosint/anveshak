"""Shared structured logging configuration for all Anveshak services.

Call ``configure_logging(service_name)`` once at process startup, before any
log calls are made. After this, all ``structlog.get_logger()`` loggers emit:

- **Production** (ENVIRONMENT=production): newline-delimited JSON — each line
  is a valid JSON object suitable for ingestion by Promtail → Loki.
- **Development** (any other ENVIRONMENT value): ColourConsoleRenderer output
  for human readability.

Mandatory fields injected automatically into every log record:
    service     — the service name passed to configure_logging()
    environment — value of the ENVIRONMENT env var (default: production)
    level       — log level string (info, warning, error, …)
    timestamp   — ISO 8601 UTC timestamp

Usage::

    from anveshak.logging import configure_logging
    configure_logging("scraper")
    import structlog
    log = structlog.get_logger(__name__)
    log.info("scraper.ready", port=8001)

JSON log line emitted in production::

    {"timestamp": "2026-04-16T12:00:00.123456Z", "level": "info",
     "logger": "anveshak.scraper.main", "event": "scraper.ready",
     "service": "scraper", "environment": "production", "port": 8001}
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog


def configure_logging(service: str) -> None:
    """Configure structlog for the named service.

    Args:
        service: Short service identifier, e.g. ``"api"``, ``"scraper"``,
                 ``"analyst"``. Stamped as the ``service`` field on every
                 log record — used by Loki label selectors.
    """
    environment: str = os.getenv("ENVIRONMENT", "production")
    log_level_name: str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level: int = getattr(logging, log_level_name, logging.INFO)

    # Processors applied to every log event before rendering.
    # Order matters: contextvars first so downstream processors see them.
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _inject_service_fields(service, environment),
    ]

    if environment == "production":
        # Loki-compatible: one JSON object per line, no colour codes
        final_renderer: Any = structlog.processors.JSONRenderer()
    else:
        # Developer-friendly: coloured key=value output
        final_renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            final_renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Silence chatty third-party loggers that pollute Loki with noise
    for _noisy in (
        "httpx",
        "httpcore",
        "asyncio",
        "arq",
        "multipart",
        "uvicorn.access",
        "charset_normalizer",
        "PIL",
        "urllib3",
    ):
        logging.getLogger(_noisy).setLevel(logging.WARNING)


def _inject_service_fields(service: str, environment: str):
    """Return a structlog processor that stamps ``service`` and ``environment``."""

    def _processor(logger: Any, method: str, event_dict: dict) -> dict:  # noqa: ANN001
        event_dict.setdefault("service", service)
        event_dict.setdefault("environment", environment)
        return event_dict

    return _processor
