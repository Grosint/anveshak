"""Prometheus metrics for the Vision service (8A.10–8A.12, 8A.19).

Uses an isolated CollectorRegistry so this module can be imported alongside
other service metrics modules in the same test process without name conflicts.
"""
from prometheus_client import CollectorRegistry, Counter, Histogram

# 8A.18 — isolated registry prevents cross-service duplicate registration
REGISTRY = CollectorRegistry()

# 8A.10 — analyses by type
vision_analyses_total = Counter(
    "vision_analyses_total",
    "Vision analyses completed",
    ["analysis_type"],  # yolo | deepfake_face | deepfake_video | clip
    registry=REGISTRY,
)

# 8A.11 — per-analysis latency
vision_analysis_duration_seconds = Histogram(
    "vision_analysis_duration_seconds",
    "Duration of a vision analysis pass",
    ["analysis_type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0],
    registry=REGISTRY,
)

# 8A.12 — deepfake score distribution (buckets aligned to decision thresholds)
vision_deepfake_score = Histogram(
    "vision_deepfake_score",
    "Deepfake probability scores (0.0–1.0) from the detector",
    buckets=[0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 1.0],
    registry=REGISTRY,
)

# 8A.19 — ARQ job failures
arq_jobs_failed_total = Counter(
    "arq_jobs_failed_total",
    "ARQ jobs that failed after all retries",
    ["job_name"],
    registry=REGISTRY,
)
