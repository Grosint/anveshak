"""Prometheus metrics for the Social service (8A.13–8A.14, 8A.19).

Uses an isolated CollectorRegistry so this module can be imported alongside
other service metrics modules in the same test process without name conflicts.
"""
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# 8A.18 — isolated registry prevents cross-service duplicate registration
REGISTRY = CollectorRegistry()

# 8A.13 — items collected per platform
social_items_collected_total = Counter(
    "social_items_collected_total",
    "Content items collected from social platforms",
    ["platform"],  # telegram | reddit | bluesky | x
    registry=REGISTRY,
)

# 8A.14 — adapter-level errors
social_adapter_errors_total = Counter(
    "social_adapter_errors_total",
    "Social adapter errors",
    ["platform", "error_type"],
    registry=REGISTRY,
)

# 8A.19 — ARQ job failures
arq_jobs_failed_total = Counter(
    "arq_jobs_failed_total",
    "ARQ jobs that failed after all retries",
    ["job_name"],
    registry=REGISTRY,
)

# Per-platform API call count
social_api_calls_total = Counter(
    "social_api_calls_total",
    "Total API calls made to social platforms",
    ["platform"],
    registry=REGISTRY,
)

# Rate limit events per platform
social_rate_limit_total = Counter(
    "social_rate_limit_total",
    "Rate limit events detected per platform",
    ["platform"],
    registry=REGISTRY,
)

# Poll duration per adapter
social_poll_duration_seconds = Histogram(
    "social_poll_duration_seconds",
    "Duration of adapter poll cycle in seconds",
    ["platform"],
    registry=REGISTRY,
)

# Quota remaining per adapter (for Bluesky daily cap, X monthly cap)
social_quota_remaining = Gauge(
    "social_quota_remaining",
    "Remaining API quota for rate-limited adapters",
    ["adapter"],
    registry=REGISTRY,
)
