"""Prometheus metrics for the Scraper service (8A.2–8A.4, 8A.19).

Uses an isolated CollectorRegistry so this module can be imported alongside
other service metrics modules in the same test process without name conflicts.
"""
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# 8A.18 — isolated registry prevents cross-service duplicate registration
REGISTRY = CollectorRegistry()

# 8A.2 — items successfully inserted per topic + platform
scraper_items_fetched_total = Counter(
    "scraper_items_fetched_total",
    "Content items fetched and inserted into the DB",
    ["topic_id", "source_platform"],
    registry=REGISTRY,
)

# 8A.3 — fetch-level errors (network, parse, timeout)
scraper_fetch_errors_total = Counter(
    "scraper_fetch_errors_total",
    "URL fetch errors by error type",
    ["error_type"],
    registry=REGISTRY,
)

# 8A.4 — per-URL fetch latency histogram (10 buckets, 0.1–30 s)
scraper_fetch_duration_seconds = Histogram(
    "scraper_fetch_duration_seconds",
    "Time to fetch a single URL",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0],
    registry=REGISTRY,
)

# 8A.19 — ARQ job failures (incremented in on_job_result hook)
arq_jobs_failed_total = Counter(
    "arq_jobs_failed_total",
    "ARQ jobs that failed after all retries",
    ["job_name"],
    registry=REGISTRY,
)

# Dark web — per-URL fetch latency via Tor (higher buckets than clearnet)
scraper_darkweb_fetch_duration_seconds = Histogram(
    "scraper_darkweb_fetch_duration_seconds",
    "Time to fetch a single .onion URL via Tor",
    buckets=[1.0, 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 75.0, 90.0],
    registry=REGISTRY,
)

# Circuit breaker events — tripped (source went down) and recovered
scraper_circuit_breaker_total = Counter(
    "scraper_circuit_breaker_total",
    "Circuit breaker state transitions",
    ["event"],  # "tripped" or "recovered"
    registry=REGISTRY,
)

# Sources skipped due to circuit breaker (down status)
scraper_sources_skipped_total = Counter(
    "scraper_sources_skipped_total",
    "Sources skipped by circuit breaker (health_status=down)",
    ["platform"],
    registry=REGISTRY,
)

# Pipeline funnel — content quality gate outcomes
scraper_content_quality_total = Counter(
    "scraper_content_quality_total",
    "Content items by quality gate outcome",
    ["quality", "gate"],
    registry=REGISTRY,
)

# Pipeline funnel — URLs skipped due to Redis seen-tracking
scraper_url_seen_skip_total = Counter(
    "scraper_url_seen_skip_total",
    "URLs skipped due to Redis seen-tracking",
    registry=REGISTRY,
)

# Pipeline funnel — article links discovered per source page
scraper_links_discovered = Histogram(
    "scraper_links_discovered",
    "Article links discovered per source page",
    buckets=[0, 1, 5, 10, 25, 50, 100],
    registry=REGISTRY,
)
