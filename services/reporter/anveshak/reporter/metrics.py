"""Prometheus metrics for the Reporter service (8A.15–8A.16, 8A.19).

Uses an isolated CollectorRegistry so this module can be imported alongside
other service metrics modules in the same test process without name conflicts.
"""

from prometheus_client import CollectorRegistry, Counter, Histogram

# 8A.18 — isolated registry prevents cross-service duplicate registration
REGISTRY = CollectorRegistry()

# 8A.15 — report generation jobs by outcome
reporter_jobs_total = Counter(
    "reporter_jobs_total",
    "Report generation ARQ jobs by outcome",
    ["status"],  # success | failed | timeout
    registry=REGISTRY,
)

# 8A.16 — report generation latency (buckets aligned to 300 s ARQ timeout)
reporter_job_duration_seconds = Histogram(
    "reporter_job_duration_seconds",
    "Wall-clock duration of a report generation job",
    buckets=[10.0, 30.0, 60.0, 90.0, 120.0, 180.0, 240.0, 270.0, 300.0],
    registry=REGISTRY,
)

# PDF export operations
reporter_pdf_generations_total = Counter(
    "reporter_pdf_generations_total",
    "PDF export generations completed",
    ["status"],  # success | failed
    registry=REGISTRY,
)

# LLM errors during report generation
reporter_ollama_errors_total = Counter(
    "reporter_ollama_errors_total",
    "Ollama LLM errors encountered during report generation",
    ["error_type"],
    registry=REGISTRY,
)

# 8A.19 — ARQ job failures
arq_jobs_failed_total = Counter(
    "arq_jobs_failed_total",
    "ARQ jobs that failed after all retries",
    ["job_name"],
    registry=REGISTRY,
)
