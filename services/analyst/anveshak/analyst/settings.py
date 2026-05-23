from pydantic_settings import BaseSettings


class AnalystSettings(BaseSettings):
    postgres_url: str = "postgresql://anveshak:anveshak@localhost:5433/anveshak"
    redis_url: str = "redis://localhost:6379"
    ollama_host: str = "http://ollama:11434"

    # NLP — hardware-controlled, see hardware.md
    # English-only NER. Non-English content is translated to English by NLLB first.
    spacy_en_model: str = "en_core_web_md"

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

    # Clustering — Leiden community detection on blended similarity graph
    clustering_similarity_threshold: float = 0.70  # min blended similarity to form an edge in the graph
    clustering_min_cluster_size: int = 2            # communities smaller than this are discarded
    clustering_window_days: int = 30      # only cluster content from last N days (0 = no filter)
    cluster_archive_after_days: int = 90  # archive clusters older than N days
    cluster_assign_threshold: float = 0.70  # cosine sim to assign new item to existing cluster
    entity_blend_weight: float = 0.3        # weight of entity similarity in distance matrix (0=embedding only, 1=entity only)
    minhash_num_perm: int = 128             # MinHash permutations (higher=more accurate, slower)

    # Label staleness detection
    label_staleness_change_threshold: float = 0.30  # re-label if >30% items changed

    # Credibility auto-update (deepfake drop — 7.3, 7.4)
    credibility_update_interval_s: int = 86400  # 24h
    credibility_deepfake_drop: float = 1.0      # pts subtracted per high-risk deepfake item
    credibility_min_auto_drop: float = 1.0      # minimum drop delta to write audit log (noise filter)

    # Cross-verification boost (7.1) — hardware-controlled, see hardware.md
    credibility_high_threshold: float = 60.0    # min score for a source to be "high credibility"
    credibility_cross_verify_boost: float = 5.0 # pts added per cross-verification pass
    credibility_min_auto_boost: float = 1.0     # minimum boost delta to write audit log (separate from drops)

    # Contradiction scoring (7.2)
    credibility_contradiction_drop: float = 5.0       # pts subtracted per contradiction pass
    credibility_noise_ratio_threshold: float = 0.6    # fraction of unclustered items to trigger drop
    credibility_contradiction_min_items: int = 5      # source must have >= N items to be evaluated

    # Content quality gate — skip embedding for boilerplate/nav text
    content_min_length: int = 100           # min clean_text chars to embed
    content_min_unique_word_ratio: float = 0.4  # unique words / total words
    content_max_punctuation_ratio: float = 0.3  # punctuation chars / total chars

    # Topic relevance gate — filter irrelevant content before clustering
    # Cosine similarity floor between content embedding and topic query embedding.
    # Per-topic override via topics.topic_relevance_threshold (auto-calibrated).
    # Global default is fallback for topics with < min_items scored content.
    topic_relevance_threshold: float = 0.35

    # Auto-calibration of per-topic relevance thresholds
    # Runs periodically, computes percentile of score distribution per topic,
    # and sets topics.topic_relevance_threshold so ~60% of content survives.
    relevance_calibration_interval_s: int = 21600       # 6 hours
    relevance_calibration_target_pct: float = 0.40      # percentile cutoff (keep top 60%)
    relevance_calibration_floor: float = 0.08           # never accept pure noise
    relevance_calibration_ceiling: float = 0.50         # never filter everything
    relevance_calibration_min_items: int = 20           # skip topics with too few scored items

    # Near-duplicate detection (semantic dedup)
    near_duplicate_similarity_threshold: float = 0.95  # cosine similarity floor
    near_duplicate_batch_size: int = 200  # max items to compare per topic per run

    # pgvector HNSW index — migration-only params, see hardware.md
    hnsw_m: int = 16                  # max connections per layer
    hnsw_ef_construction: int = 64    # build-time search width

    # Signal engine
    signal_check_interval_s: int = 300  # check every 5 minutes

    # Sentiment shift signal — fires when avg compound drops sharply
    sentiment_shift_threshold: float = 0.3    # min compound drop to trigger signal
    sentiment_shift_window_hours: int = 24    # recent window to compare
    sentiment_shift_baseline_days: int = 7    # baseline average window

    # Cross-topic cluster convergence
    cross_topic_similarity_threshold: float = 0.85  # centroid cosine similarity
    cross_topic_check_interval_s: int = 900         # 15 minutes (0 = disabled)
    cross_topic_max_pairs: int = 50                  # max convergence pairs per cycle

    # Historical backfill — criterion 2.9
    backfill_similarity_threshold: float = 0.85  # cosine similarity floor; see hardware.md
    backfill_interval_s: int = 600  # continuous backfill interval (0 = disabled)

    # Content archive + retention (0 = disabled, keep forever in PostgreSQL)
    # Items older than N days AND already clustered are archived to disk, then deleted.
    content_retention_days: int = 0
    content_archive_root: str = "/app/media/archive"

    # Scheduler throttling — max topics per clustering cycle (0 = unlimited)
    max_topics_per_cycle: int = 0

    # Prometheus metrics HTTP server port (8A.17)
    metrics_port: int = 8004  # matches ANALYST_PORT in compose.yml

    log_level: str = "INFO"
    model_config = {"env_prefix": "", "case_sensitive": False}


settings = AnalystSettings()
