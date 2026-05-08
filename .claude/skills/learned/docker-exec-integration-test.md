# Docker Exec Integration Test Pattern

## When this applies
Testing real scraping, adapter, or ML pipeline code that depends on container
dependencies (Crawl4AI/Chromium, Tor proxy, ML models, etc.).

## The pattern
Host orchestrator → docker cp → docker exec → JSON stdout → colored table.

```
scripts/test_scrape.py          (host: orchestrator + table printer)
  ├─ docker cp → scraper:/tmp/  (copy test script into container)
  ├─ docker exec scraper python /tmp/test_scrape_sources.py → JSON
  ├─ docker cp → social:/tmp/
  ├─ docker exec social python /tmp/test_scrape_social.py → JSON
  └─ merge JSON, print table, exit code
```

## Why not run on host?
- Crawl4AI needs Chromium (only in scraper image)
- Tor proxy is at `tor-proxy:9050` (Docker network only)
- Social adapters need env vars injected by compose
- Running inside containers = identical to production

## Container script rules
1. **Import real code** — `from anveshak.scraper.rss import fetch_rss_items`
2. **Output JSON to stdout** — single `[{...}, {...}]` array
3. **Suppress logs** — `os.environ["LOG_LEVEL"] = "ERROR"` + redirect stderr
4. **Set HOME** — `os.environ["HOME"] = "/tmp"` (Crawl4AI needs writable HOME)
5. **Use sys.__stdout__** — bypass any stdout capture:
   ```python
   sys.stderr = io.TextIOWrapper(open(os.devnull, "wb"), write_through=True)
   sys.__stdout__.write(json.dumps(results) + "\n")
   sys.__stdout__.flush()
   ```

## Host script rules
1. **docker cp** before **docker exec** (script may not exist in image)
2. **Find JSON with rfind("[")** — skip any log lines that leak to stdout
3. **Timeout per container** — 600s for scraper (Crawl4AI slow), 120s for social
4. **Never crash on one failure** — wrap each container exec in try/except

## Makefile target
```makefile
test-scrape:
	@$(COMPOSE) cp scripts/test_scrape_sources.py scraper:/tmp/test_scrape_sources.py
	@$(COMPOSE) cp scripts/test_scrape_social.py social:/tmp/test_scrape_social.py
	@$(UV) python scripts/test_scrape.py
```
