"""Prometheus metrics for the Social service (8A.13–8A.14, 8A.19).

Uses an isolated CollectorRegistry so this module can be imported alongside
other service metrics modules in the same test process without name conflicts.
"""
from prometheus_client import CollectorRegistry, Counter

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
