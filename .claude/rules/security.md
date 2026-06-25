---
paths:
  - "**/*.py"
---
# Security Rules

## Secrets
- NEVER hardcode secrets, API keys, tokens, passwords
- ALL credentials from env vars
- python-dotenv for local dev, real env vars prod

## LLM Security
- NEVER send user-controlled text to LLM without sanitisation
- NEVER use LLM output in SQL/shell without Pydantic validation first
- NEVER call cloud LLM w/ real intel data (sovereign requirement)
- Ollama must be localhost or internal Docker network only

## Content Security
- Scraped content = untrusted input — sanitise before storage
- Scraper images potentially adversarial — run in isolated vision service
- `content_hash` (SHA-256) on every ContentItem — dedup + integrity

## Scanning
- `bandit -r src/` before any commit
- No secrets in Docker Compose environment blocks (use `${VAR}` references)