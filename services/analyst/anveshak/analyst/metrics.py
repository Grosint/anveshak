"""Prometheus metrics for the Analyst service (8A.5–8A.9, 8A.19).

Uses an isolated CollectorRegistry so this module can be imported alongside
other service metrics modules in the same test process without name conflicts.
"""
from prometheus_client import CollectorRegistry, Counter, Histogram

# 8A.18 — isolated registry prevents cross-service duplicate registration
REGISTRY = CollectorRegistry()

# 8A.5 — NLP jobs processed by outcome
analyst_nlp_jobs_total = Counter(
    "analyst_nlp_jobs_total",
    "NLP pipeline jobs processed",
    ["status"],  # success | failed
    registry=REGISTRY,
)

# 8A.6 — per-item NLP latency
analyst_nlp_duration_seconds = Histogram(
    "analyst_nlp_duration_seconds",
    "End-to-end NLP pipeline duration per content item",
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0],
    registry=REGISTRY,
)

# 8A.7 — clusters created per topic
analyst_clusters_created_total = Counter(
    "analyst_clusters_created_total",
    "Narrative clusters created by Leiden community detection",
    ["topic_id"],
    registry=REGISTRY,
)

# 8A.8 — signals fired by severity
analyst_signals_fired_total = Counter(
    "analyst_signals_fired_total",
    "Intelligence signals fired",
    ["severity"],  # HIGH | MEDIUM | LOW
    registry=REGISTRY,
)

# 8A.9 — credibility score changes
analyst_credibility_changes_total = Counter(
    "analyst_credibility_changes_total",
    "Source credibility score changes",
    ["direction"],  # up | down
    registry=REGISTRY,
)

# Topic relevance score distribution — calibrate threshold via histogram
analyst_relevance_score = Histogram(
    "analyst_topic_relevance_score",
    "Topic relevance score distribution",
    buckets=[0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.70, 0.90, 1.0],
    registry=REGISTRY,
)

# Per-topic auto-calibrated relevance threshold
from prometheus_client import Gauge

analyst_topic_threshold = Gauge(
    "analyst_topic_relevance_threshold",
    "Auto-calibrated relevance threshold per topic",
    ["topic_id", "topic_name"],
    registry=REGISTRY,
)

# 8A.19 — ARQ job failures
arq_jobs_failed_total = Counter(
    "arq_jobs_failed_total",
    "ARQ jobs that failed after all retries",
    ["job_name"],
    registry=REGISTRY,
)
