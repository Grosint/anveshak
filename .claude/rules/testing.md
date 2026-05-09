---
paths:
  - "**/*.py"
---
# Testing Rules

- pytest as test framework
- Tests MUST pass on CPU with default medium/nano/cpu config
- Never assume GPU availability in tests
- 80%+ coverage on all new service code
- pytest.mark.unit — no external dependencies
- pytest.mark.integration — requires running Docker Compose services
- pytest.mark.e2e — full demo arc, requires seeded data

## Hardware in Tests
- Mock Ollama responses in unit tests (never call real Ollama)
- Mock vision model inference in unit tests
- Use httpx.MockTransport for external API calls
- Integration tests use real PostgreSQL and Redis (Docker Compose)

## ML Test Data — Embedding Realism

- Test embeddings must be L2-normalized (sentence-transformers outputs unit vectors)
- Use seeded RNG, perturb base vectors with controlled noise
  Calibration: 0.02 noise (tight clusters), 0.03 (realistic), 0.05 (broad topics)
- Golden test data: write content in supported languages with pre-decided expected outputs
  Use fuzzy keyword matching (3 out of 5, not 5/5) — NLLB translation is non-deterministic
  See: `learned/test-embedding-realism.md`, `learned/golden-test-data-ml-pipeline.md`

## DB Module Mocking

- When adding a new async DB function, grep all tests mocking that module and add
  `AsyncMock()` for the new function — `await` on a plain MagicMock raises TypeError
- Use `side_effect=[row1, row2]` (not `return_value`) for functions making multiple
  sequential DB fetches that return different column schemas
- When SQL JOINs change, expand fake_row dicts to include new columns
  See: `learned/new-db-func-mock-all-callers.md`, `learned/mock-sequential-db-calls.md`
