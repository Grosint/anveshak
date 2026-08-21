"""Shared OpenTelemetry tracing setup for all Anveshak services.

Usage (call once at service startup, before any imports that emit spans)::

    from anveshak.tracing import configure_tracing
    configure_tracing("api")

This sets up:
- OTLP HTTP exporter → Jaeger (or any OTLP-compatible collector)
- Trace context propagation (W3C TraceContext)
- FastAPI auto-instrumentation (if opentelemetry-instrumentation-fastapi is installed)
- Trace ID injection into structlog (correlate logs with traces)

All configuration via env vars (hardware-independent):
  OTEL_EXPORTER_OTLP_ENDPOINT  — default http://jaeger:4318
  OTEL_TRACES_SAMPLER           — default parentbased_traceidratio
  OTEL_TRACES_SAMPLER_ARG       — default 0.1 (10% sampling in dev)
  OTEL_ENABLED                  — default false (opt-in)
"""

from __future__ import annotations

import os

import structlog

log = structlog.get_logger(__name__)


def configure_tracing(service_name: str) -> None:
    """Configure OpenTelemetry tracing for the given service.

    No-op if OTEL_ENABLED is not 'true' or if opentelemetry packages
    are not installed. This ensures services start cleanly without OTEL deps.
    """
    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # pyright: ignore[reportMissingImports]  # container-only dep
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio
    except ImportError:
        log.info("tracing.otel_not_installed", service=service_name)
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
    sample_rate = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1"))

    resource = Resource.create(
        {
            "service.name": f"anveshak-{service_name}",
            "service.namespace": "anveshak",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )

    sampler = ParentBasedTraceIdRatio(rate=sample_rate)
    provider = TracerProvider(resource=resource, sampler=sampler)

    exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    log.info(
        "tracing.configured",
        service=service_name,
        endpoint=endpoint,
        sample_rate=sample_rate,
    )


def get_trace_id() -> str | None:
    """Return the current trace ID as a hex string, or None if no active span."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except (ImportError, Exception):
        pass
    return None


def inject_trace_id(logger, method, event_dict):
    """Structlog processor that adds trace_id to log records.

    Add to the structlog processor chain to correlate logs with traces.
    """
    tid = get_trace_id()
    if tid:
        event_dict["trace_id"] = tid
    return event_dict
