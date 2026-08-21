"""Prometheus metrics for the Anveshak API gateway.

Uses an isolated CollectorRegistry so this module can be imported in the same
test process alongside other service metrics without name conflicts.

Exposed at GET /metrics via make_asgi_app(registry=REGISTRY).
"""

from prometheus_client import CollectorRegistry, Counter, Gauge

# Isolated registry — prevents duplicate-registration errors in tests
REGISTRY = CollectorRegistry()

# Total HTTP requests handled by the API, broken down by method, route, and
# response status code. Route uses the FastAPI path template (e.g.
# /api/v1/sources/{source_id}) rather than the resolved URL to keep
# cardinality manageable.
api_requests_total = Counter(
    "api_requests_total",
    "Total API HTTP requests by method, route template, and status code",
    ["method", "route", "status_code"],
    registry=REGISTRY,
)

# Authentication failures — useful for detecting brute-force or token-reuse attacks
api_auth_failures_total = Counter(
    "api_auth_failures_total",
    "JWT authentication failures by reason",
    ["reason"],  # invalid_token | expired | missing
    registry=REGISTRY,
)

# Real-time WebSocket connections open at any given moment (signal delivery)
api_websocket_connections = Gauge(
    "api_websocket_connections",
    "Current active WebSocket connections for signal delivery",
    registry=REGISTRY,
)

# ARQ jobs dispatched via API routes — gives a per-type view of job creation rate
api_arq_enqueues_total = Counter(
    "api_arq_enqueues_total",
    "ARQ jobs enqueued by the API gateway by job type",
    ["job_type"],  # generate_report | run_vision_analysis | scrape_topic
    registry=REGISTRY,
)
