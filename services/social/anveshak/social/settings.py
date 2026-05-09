from pydantic_settings import BaseSettings
from typing import Optional


class SocialSettings(BaseSettings):
    postgres_url: str = "postgresql://anveshak:anveshak@localhost:5432/anveshak"
    redis_url: str = "redis://localhost:6379"

    # Telegram
    telegram_api_id: Optional[int] = None
    telegram_api_hash: Optional[str] = None
    telegram_session_string: Optional[str] = None
    telegram_adapter_enabled: bool = False

    # Reddit
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: str = "Anveshak OSINT Platform/1.0"
    reddit_adapter_enabled: bool = False

    # Bluesky
    bluesky_handle: Optional[str] = None
    bluesky_password: Optional[str] = None
    bluesky_adapter_enabled: bool = False
    bluesky_daily_call_cap: int = 7200          # Bluesky free API limit: 7200 calls/day

    # X/Twitter — pay-per-use
    x_bearer_token: Optional[str] = None
    x_adapter_enabled: bool = False
    x_adapter_mode: str = "polling"           # polling | stream (stream requires Enterprise)
    x_monthly_read_cap: int = 40000           # $200/month budget cap at $0.005/read
    x_poll_interval_s: int = 900              # 15 minutes

    poll_interval_s: int = 900  # default for all adapters

    # Circuit breaker — per-adapter failure tracking
    social_circuit_breaker_threshold: int = 5   # consecutive failures before opening
    social_circuit_breaker_cooldown_s: int = 900  # 15 min cooldown before probe

    # Prometheus metrics HTTP server port (8A.17)
    metrics_port: int = 8002  # matches SOCIAL_PORT in compose.yml

    # Phase 4: media download settings
    media_storage_root: str = "/app/media"   # shared volume with vision service (str for simplicity)
    media_max_size_mb: int = 50
    log_level: str = "INFO"
    model_config = {"env_prefix": "", "case_sensitive": False, "env_ignore_empty": True}


settings = SocialSettings()
