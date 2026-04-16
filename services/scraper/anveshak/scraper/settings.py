from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class ScraperSettings(BaseSettings):
    postgres_url: str = "postgresql://anveshak:anveshak@localhost:5433/anveshak"
    redis_url: str = "redis://localhost:6379"

    scraper_default_delay_s: float = 2.0
    scraper_concurrency: int = 5                   # criteria 1.8 — asyncio semaphore size
    scraper_request_timeout_s: int = 30            # criteria 1.7 — per-URL fetch timeout
    scraper_poll_interval_s: int = 900             # 15 minutes between polling sweeps
    respect_robots_txt: bool = True
    tor_proxy_url: Optional[str] = None            # criteria 1.10 — e.g. socks5://127.0.0.1:9050

    # Phase 4: media download settings
    media_storage_root: Path = Path("/app/media")  # shared volume with vision service
    media_max_size_mb: int = 50                    # per-file download cap
    media_download_enabled: bool = True            # set False to disable media ingestion

    # Prometheus metrics HTTP server port (8A.17)
    metrics_port: int = 8001  # matches SCRAPER_PORT in compose.yml

    # RSS feed settings
    rss_max_items_per_fetch: int = 20       # cap items per feed per poll cycle
    rss_full_text_min_chars: int = 200      # fetch full article if summary shorter than this

    log_level: str = "INFO"
    model_config = {"env_prefix": "", "case_sensitive": False}


settings = ScraperSettings()
