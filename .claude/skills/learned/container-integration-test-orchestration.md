---
title: Container-side integration tests via docker cp + docker exec orchestration
created: 2026-05-08
---

## Problem

Integration tests that depend on ML models (spaCy, YOLO, CLIP, Ollama) can't run on the host
because models only exist inside containers. Installing models on the host tests a code path
that doesn't exist in production.

## Pattern

One `make test-integration` command runs everything:

```makefile
test-integration:
    @_fail=0; \
    # Step 1: Host-side DB tests (only need asyncpg to postgres)
    $(UV) pytest tests/integration/ ... || _fail=1; \
    # Step 2: Copy test script into container, execute
    $(COMPOSE) cp scripts/test_analyst_models.py analyst-worker:/tmp/; \
    $(COMPOSE) exec -T analyst-worker python /tmp/test_analyst_models.py || _fail=1; \
    # Step 3-4: same for vision-worker, reporter-worker
    ...
    exit $$_fail
```

Container-side test scripts follow this structure:
```python
os.environ["LOG_LEVEL"] = "ERROR"          # suppress logs, keep stdout clean
from anveshak.analyst.jobs import analyse_content  # real service code

pool = await asyncpg.create_pool(os.environ["POSTGRES_URL"])  # container env var
# ... run tests, collect JSON results ...
await cleanup(pool, item_ids)             # always clean up test data
sys.__stdout__.write(json.dumps(results)) # JSON output for orchestrator
sys.exit(0 if all_passed else 1)
```

## Key rules

- Test scripts are **not installed in the image** — copied in at test time via `docker cp`
- Use `sys.__stdout__` to bypass any log capture
- Use container env vars (POSTGRES_URL, OLLAMA_HOST) — not host values
- Always clean up test data to avoid polluting the DB
- Use `_fail` variable pattern so all 4 steps run even if one fails

## Which tests go where

| Test needs | Runs on | Why |
|------------|---------|-----|
| DB queries only | Host (pytest) | asyncpg to port-forwarded postgres |
| spaCy, VADER, NLLB | analyst-worker | Models baked in image / volume |
| YOLO, CLIP, deepfake | vision-worker | Models in vision_models volume |
| Ollama LLM | reporter-worker | Ollama network only inside compose |
