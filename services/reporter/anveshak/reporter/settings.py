from pydantic_settings import BaseSettings


class ReporterSettings(BaseSettings):
    postgres_url: str = "postgresql://anveshak:anveshak@localhost:5432/anveshak"
    redis_url: str = "redis://localhost:6379"

    # LLM — hardware-controlled, see hardware.md
    # Single model handles report generation. All input text is English (post-translation).
    # Upgrade path: qwen2.5:72b on RTX 4090 — see hardware.md
    ollama_host: str = "http://ollama:11434"
    ollama_model: str = "qwen2:7b"
    llm_max_tokens: int = 2048

    # Analyst service — embedding endpoint (avoids PyTorch in reporter image)
    analyst_service_url: str = "http://analyst-scheduler:8007"

    # RAG
    rag_top_k: int = 10
    rag_similarity_threshold: float = 0.3
    rag_max_context_tokens: int = 4000

    # Reports
    pdf_output_dir: str = "/tmp/anveshak/reports"  # nosec B108 — dev default; overridden by PDF_OUTPUT_DIR env var in production (maps to reporter_output Docker volume)
    report_cache_hours: int = 24  # don't regenerate same report type within 24h

    # LLM retry / timeout
    ollama_report_timeout_s: int = 300
    ollama_retry_max: int = 2

    # Cron intervals
    scheduled_report_check_interval_s: int = 900
    source_warning_check_interval_s: int = 21600
    source_warning_lookback_days: int = 30

    # Geocoder
    geocoder_fuzzy_threshold: int = 2

    port: int = 8005
    metrics_port: int = 8006  # Prometheus HTTP server for the ARQ reporter worker
    log_level: str = "INFO"
    model_config = {"env_prefix": "", "case_sensitive": False}


settings = ReporterSettings()
