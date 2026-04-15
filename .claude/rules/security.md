---
paths:
  - "**/*.py"
---
# Security Rules

## Secrets
- NEVER hardcode secrets, API keys, tokens, or passwords
- ALL credentials from environment variables
- Use python-dotenv for local dev, real env vars for production

## LLM Security
- NEVER send user-controlled text to LLM without sanitisation
- NEVER use LLM output in SQL/shell without Pydantic validation first
- NEVER call a cloud LLM endpoint with real intelligence data (sovereign requirement)
- Ollama must be localhost or internal Docker network only

## Content Security
- Scraped content is untrusted input — always sanitise before storage
- Images from scraper are potentially adversarial — run in isolated vision service
- content_hash (SHA-256) on every ContentItem — deduplication and integrity

## Scanning
- bandit -r src/ before any commit
- No secrets in Docker Compose environment blocks (use ${VAR} references)
