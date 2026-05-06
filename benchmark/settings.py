"""Benchmark-specific configuration.

Reads from environment variables with BENCHMARK_ prefix.
Falls back to same DB as the running Anveshak instance.
"""
from pydantic_settings import BaseSettings


class BenchmarkSettings(BaseSettings):
    # Database — same as analyst/api services
    postgres_url: str = "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak"
    redis_url: str = "redis://localhost:6379"

    # Benchmark execution
    analyse_timeout_s: int = 1800  # 30 min max for all embeddings on CPU
    poll_interval_s: int = 5       # check embedding completion every 5s
    signal_threshold: int = 3      # ISC threshold for benchmark topics
    min_cluster_size: int = 2      # lower than production (3) for small fixture sets

    # Paths
    corpus_dir: str = "benchmark/corpus"
    results_dir: str = "benchmark/results"
    docs_template: str = "docs/accuracy_benchmark.md"

    model_config = {"env_prefix": "BENCHMARK_"}


settings = BenchmarkSettings()
