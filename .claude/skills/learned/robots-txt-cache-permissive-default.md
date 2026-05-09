# robots.txt Enforcement with Caching

## Pattern
Cache parsed `RobotFileParser` per domain with 1-hour TTL. Permissive default:
unreachable robots.txt → allow (not block). Skip `.onion` URLs entirely.

## Why
- Per-URL robots.txt fetch adds ~200ms latency; caching amortizes to near-zero
- Restrictive default (block on fetch failure) silently drops legitimate content
- Dark web has no robots.txt standard — bypass avoids spurious blocks
- `urllib.robotparser` is stdlib — no extra dependency

## Implementation
```python
_robots_cache: dict[str, tuple[RobotFileParser | None, float]] = {}
_ROBOTS_CACHE_TTL = 3600

async def check_robots_allowed(url: str) -> bool:
    if not settings.respect_robots_txt: return True
    if parsed.netloc.endswith(".onion"): return True
    # Check cache by domain, fetch if miss, parse, cache (domain, monotonic_time)
    # None parser in cache = unreachable → allow
```

## How to apply
Call `check_robots_allowed(url)` before every clearnet fetch. Wire into both
primary (`_process`) and fallback (`_process_fallback`) code paths.

## Files
- `services/scraper/anveshak/scraper/fetch.py` — implementation
- `tests/unit/test_scraper_robots.py` — 6 tests
