# Scraping Patterns

## When to load: any task involving web crawling, content extraction, or open-web ingestion

> See also: `.claude/skills/learned/cross-service-delivery-loop.md` — pattern for delivering DB-written events to WebSocket clients across service boundaries
> See also: `.claude/skills/learned/websocket-auth-pattern.md` — JWT auth on WebSocket endpoints (Depends() does not work; use query param)

---

### Crawl4AI async crawler
```python
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

async def scrape_url(url: str) -> str:
    config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        word_count_threshold=100,     # skip stub pages
        exclude_external_links=True,
        process_iframes=False,
    )
    async with AsyncWebCrawler(config=config) as crawler:
        result = await crawler.arun(url=url, config=run_config)
        return result.markdown  # clean markdown text
```

### trafilatura for HTML → clean text
```python
import trafilatura

def extract_clean_text(html: str) -> str | None:
    return trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
    )
```

### Language detection (route to correct spaCy model)
```python
from langdetect import detect

SPACY_MODELS = {
    "en": settings.SPACY_EN_MODEL,   # from settings: en_core_web_md or en_core_web_trf
    "ru": settings.SPACY_RU_MODEL,
    "zh": settings.SPACY_ZH_MODEL,
}

def detect_and_route(text: str) -> str:
    lang = detect(text[:500])  # detect on first 500 chars
    return SPACY_MODELS.get(lang, SPACY_MODELS["en"])
```

### Rate limiting (mandatory per domain)
```python
from asyncio import sleep
from urllib.parse import urlparse

DOMAIN_DELAYS = {
    "default": settings.SCRAPER_DEFAULT_DELAY_S,  # from settings, default 2.0
}

async def rate_limited_fetch(url: str):
    domain = urlparse(url).netloc
    delay = DOMAIN_DELAYS.get(domain, DOMAIN_DELAYS["default"])
    await sleep(delay)
    return await scrape_url(url)
```

### robots.txt compliance (mandatory)
```python
from urllib.robotparser import RobotFileParser

async def is_allowed(url: str, user_agent: str = "Anveshak/1.0") -> bool:
    rp = RobotFileParser()
    rp.set_url(f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt")
    rp.read()
    return rp.can_fetch(user_agent, url)
```

### Content deduplication
```python
import hashlib

def compute_content_hash(clean_text: str) -> str:
    normalised = " ".join(clean_text.lower().split())
    return hashlib.sha256(normalised.encode()).hexdigest()
```
