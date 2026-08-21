# OpenTelemetry Opt-In Tracing

## When to load: adding distributed tracing to a service without making it a hard dependency

---

## Pattern

Tracing is a no-op by default. Enabled via env var. Packages are optional — missing imports are caught gracefully.

```python
# sdk/tracing.py
def configure_tracing(service_name: str) -> None:
    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        return  # No-op — zero overhead

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        # ... setup provider, exporter, sampler ...
    except ImportError:
        log.info("tracing.otel_not_installed")
        return  # Graceful degradation

def get_trace_id() -> str | None:
    """Returns current trace ID or None if tracing is disabled."""
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.trace_id:
            return format(ctx.trace_id, '032x')
    except Exception:
        pass
    return None

def inject_trace_id(logger, method, event_dict):
    """structlog processor: adds trace_id to every log line."""
    tid = get_trace_id()
    if tid:
        event_dict["trace_id"] = tid
    return event_dict
```

**Compose: opt-in via profile**
```yaml
jaeger:
  image: jaegertracing/all-in-one:1.57
  profiles:
    - tracing  # Only starts with: docker compose --profile tracing up
```

**Env vars:**
```bash
OTEL_ENABLED=false                              # Default: off
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318  # Only matters when enabled
OTEL_TRACES_SAMPLER_ARG=0.1                     # 10% dev, 1% prod
```

**Why:** Zero overhead in production unless explicitly enabled. No mandatory dependency. trace_id correlation in logs enables log→trace→log navigation in Grafana.
