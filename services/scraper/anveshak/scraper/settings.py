from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class ScraperSettings(BaseSettings):
    postgres_url: str = "postgresql://anveshak:anveshak@localhost:5433/anveshak"
    redis_url: str = "redis://localhost:6379"

    scraper_default_delay_s: float = 2.0
    scraper_concurrency: int = 5  # criteria 1.8 — asyncio semaphore size
    scraper_request_timeout_s: int = 30  # criteria 1.7 — per-URL fetch timeout
    scraper_poll_interval_s: int = 900  # 15 minutes between polling sweeps
    respect_robots_txt: bool = True
    # A redirect chain is walked hop by hop, each hop revalidated, so this
    # bounds how long an outlet can keep a worker walking before we give up.
    scraper_max_redirects: int = 5
    # Page-level address guard inside the Crawl4AI browser. Off only where a
    # deployment relies on egress policy instead; see ADR 0005.
    scraper_browser_address_guard: bool = True
    tor_proxy_url: Optional[str] = None  # criteria 1.10 — e.g. socks5://127.0.0.1:9050

    # Dark web (.onion) scraping — routed through Tor SOCKS5 proxy
    darkweb_tor_proxy_url: str = "socks5://tor-proxy:9050"
    darkweb_request_timeout_s: int = 90  # Tor adds latency; 3x the default web timeout
    darkweb_concurrency: int = 2  # lower than web to avoid Tor circuit exhaustion
    darkweb_follow_links: bool = False  # safety — no recursive crawling on .onion
    darkweb_media_download: bool = False  # Phase 1: no media download from .onion sites

    # Phase 4: media download settings
    media_storage_root: Path = Path("/app/media")  # shared volume with vision service
    media_max_size_mb: int = 50  # per-file download cap
    media_download_enabled: bool = True  # set False to disable media ingestion

    # Prometheus metrics HTTP server port (8A.17)
    metrics_port: int = 8001  # matches SCRAPER_PORT in compose.yml

    # ARQ job timeout — must be > (num_sources * scraper_request_timeout_s / concurrency)
    scraper_job_timeout_s: int = 300  # 5 min total budget per scrape job

    # RSS feed settings
    rss_max_items_per_fetch: int = 20  # cap items per feed per poll cycle
    rss_full_text_min_chars: int = 200  # fetch full article if summary shorter than this

    # Archive Backfill — historic discovery and body fetch (issue #44)
    # Page cap on a feed walk. The backstop, not the stop condition: a walk ends
    # on a repeated page or on reaching the window long before it reaches this.
    archive_backfill_max_feed_pages: int = 40
    # Entries read per archive page. Distinct from rss_max_items_per_fetch,
    # which caps what one live poll cycle should collect.
    archive_backfill_max_items_per_page: int = 100
    # Bounds an operator-run Backfill, which takes hours at the per-domain gap.
    # An ARQ job wrapping this needs its own timeout; scraper_job_timeout_s is
    # 300 seconds and would expire long before this number is reached.
    archive_backfill_max_urls_per_outlet: int = 5000
    # Shortest body accepted as an article. Distinct from
    # rss_full_text_min_chars, which decides whether a feed body needs a fetch.
    archive_backfill_body_min_chars: int = 200
    # Archive rehydration when the publisher returns a client error.
    archive_backfill_enabled: bool = True
    archive_backfill_cdx_url: str = "https://web.archive.org/cdx/search/cdx"
    archive_backfill_base_url: str = "https://web.archive.org/web"
    # Gap that separates a feed's real publication run from its evergreen items.
    archive_backfill_feed_depth_max_gap_days: int = 30

    # Recursive scraping — follow article links from fetched pages
    scraper_follow_links: bool = True  # enable depth-1 link following
    scraper_max_links_per_page: int = 100  # cap followed links per source page
    scraper_follow_same_domain: bool = True  # only follow same-domain links

    # Per-domain politeness delay — prevents WAF/rate-limit blocks
    scraper_per_domain_delay_s: float = 1.5  # min gap between requests to same domain
    scraper_per_domain_jitter_s: float = 0.5  # ± random jitter added to delay

    # URL-level visited tracking via Redis — avoids re-fetching same articles
    scraper_url_seen_ttl_s: int = 86400  # 24 hours
    scraper_url_seen_enabled: bool = True  # set False to disable URL dedup

    log_level: str = "INFO"
    model_config = {"env_prefix": "", "case_sensitive": False}


settings = ScraperSettings()
