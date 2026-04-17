from pydantic_settings import BaseSettings


class AnalystSettings(BaseSettings):
    postgres_url: str = "postgresql://anveshak:anveshak@localhost:5433/anveshak"
    redis_url: str = "redis://localhost:6379"
    ollama_host: str = "http://ollama:11434"

    # NLP — hardware-controlled, see hardware.md
    spacy_en_model: str = "en_core_web_md"
    spacy_ru_model: str = "ru_core_news_md"
    spacy_zh_model: str = "zh_core_web_md"

    # Translation — hardware-controlled, see hardware.md
    # NLLB-200 translates non-English articles to English before NLP/embedding.
    # Upgrade: facebook/nllb-200-1.3B or facebook/nllb-200-3.3B on GPU.
    translation_enabled: bool = True
    translation_model: str = "facebook/nllb-200-distilled-600M"
    translation_max_chars: int = 1500    # truncate before translation (Chinese chars ≈ 1 token each)
    translation_max_tokens: int = 512    # max output tokens per translation call

    # Embeddings — hardware-controlled, see hardware.md
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # LLM — hardware-controlled, see hardware.md
    # Single model handles cluster labelling. All input text is English (post-translation).
    # Upgrade path: qwen2.5:72b on RTX 4090 — see hardware.md
    ollama_model: str = "qwen2:7b"
    llm_max_tokens: int = 512

    # Clustering
    hdbscan_min_cluster_size: int = 3
    hdbscan_min_samples: int = 2

    # Credibility auto-update (deepfake drop — 7.3, 7.4)
    credibility_update_interval_s: int = 86400  # 24h
    credibility_min_auto_drop: float = 10.0     # minimum drop delta to write audit log

    # Cross-verification boost (7.1) — hardware-controlled, see hardware.md
    credibility_high_threshold: float = 60.0    # min score for a source to be "high credibility"
    credibility_cross_verify_boost: float = 5.0 # pts added per cross-verification pass
    credibility_min_auto_boost: float = 1.0     # minimum boost delta to write audit log (separate from drops)

    # Contradiction scoring (7.2)
    credibility_contradiction_drop: float = 5.0       # pts subtracted per contradiction pass
    credibility_noise_ratio_threshold: float = 0.6    # fraction of unclustered items to trigger drop
    credibility_contradiction_min_items: int = 5      # source must have >= N items to be evaluated

    # Signal engine
    signal_check_interval_s: int = 300  # check every 5 minutes

    # Historical backfill — criterion 2.9
    backfill_similarity_threshold: float = 0.85  # cosine similarity floor; see hardware.md

    # Prometheus metrics HTTP server port (8A.17)
    metrics_port: int = 8004  # matches ANALYST_PORT in compose.yml

    log_level: str = "INFO"
    model_config = {"env_prefix": "", "case_sensitive": False}


settings = AnalystSettings()
