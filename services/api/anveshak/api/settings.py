"""API service settings — all hardware-sensitive values from env vars."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    postgres_url: str = "postgresql+asyncpg://anveshak:anveshak@localhost:5432/anveshak"
    postgres_pool_size: int = 10

    # Redis / ARQ
    redis_url: str = "redis://localhost:6379"

    # Ollama
    ollama_host: str = "http://ollama:11434"
    ollama_report_model: str = "mistral:7b"       # see hardware.md
    ollama_cluster_model: str = "llama3.2:3b"     # see hardware.md
    ollama_keep_alive: str = "5m"                  # see hardware.md
    llm_max_tokens: int = 2048

    # JWT Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480               # 8 hours

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000", "http://frontend:3000"]

    # Security headers
    hsts_enabled: bool = False  # enable when TLS is terminated upstream

    # Drishti bridge
    anveshak_drishti_bridge: bool = False
    drishti_redpanda_bootstrap: Optional[str] = None

    # X/Twitter
    x_adapter_enabled: bool = False
    x_bearer_token: Optional[str] = None
    x_monthly_read_cap: int = 40000

    # Internal service URLs
    analyst_service_url: str = "http://analyse-scheduler:8007"
    phash_duplicate_threshold: int = 8   # Hamming distance for reverse-image search

    # Vision file storage (absorbed from vision container)
    media_storage_root: str = "/app/media"
    vision_max_video_size_mb: int = 500

    # Report PDF serving (absorbed from reporter container)
    report_output_dir: str = "/app/reports"

    # Signal webhook notifications
    signal_webhook_enabled: bool = False
    signal_webhook_url: Optional[str] = None

    # Service
    debug: bool = False
    log_level: str = "INFO"

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
