---
name: dotenv-inline-comment-int-fields
description: Inline comments on integer env vars cause pydantic-settings ValidationError at startup — move comment to its own line
type: feedback
---

# .env Inline Comments Break Integer Fields in pydantic-settings

## Rule

Never put inline comments on integer (or any non-string) env var lines. Move the comment to the line above.

**Why:** `python-dotenv` and `pydantic-settings` include everything after the `=` as the value string — including `# comment text`. When pydantic tries to coerce that string to `int` or `float`, it raises a `ValidationError: unable to parse string as an integer`. The service fails to start. No warning, no fallback — hard crash at import time.

```ini
# WRONG — pydantic reads '40000               # 40,000 reads = ~$200/month. Adjust.'
X_MONTHLY_READ_CAP=40000               # 40,000 reads = ~$200/month. Adjust.

# CORRECT
# 40,000 reads = ~$200/month. Adjust to your budget.
X_MONTHLY_READ_CAP=40000
```

## How to apply

- When writing `.env` or `.env.example`, put all inline comments for numeric fields on a separate line above.
- String fields (e.g. `POSTGRES_URL=...`) tolerate inline comments only if the string value doesn't contain `#`. To be safe, use same rule for all fields.
- After any `.env` change, run `docker compose config` (or `python -c "from settings import Settings; Settings()"`) to validate before restarting containers.

## What triggered this

`EMBEDDING_DIMENSIONS` and `X_MONTHLY_READ_CAP` both had inline comments. API container crashed at startup with `pydantic_core.ValidationError: 2 validation errors for Settings`. Took a full container log read to diagnose.
