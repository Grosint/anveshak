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

## Mock Shape Must Match Reality

- Mock return value must match the shape the code actually unpacks — not a wrapper
  around it. If the function returns `dict`, mock must return `dict` (not `[dict]`).
- Common mismatch: API returns `r.data` (unwrapped) but mock returns `[{...}]` (wrapped)
- When JOIN changes add columns, expand fake_row dicts to include new columns
- When function signature changes (new param), grep all test mocks for that function
  and add the new param — stale mocks cause `TypeError` at runtime
  See: `learned/mock-shape-unwrap-mismatch.md`

## Test-Reality Seams (A→cache→B Boundaries)

- Unit tests pass but integration breaks at service boundaries. Identify and test seams:
  scraper→DB→analyst, analyst→DB→reporter, API→WebSocket→frontend, etc.
- Frontend seams: React Query `queryKey` prefix matching, optimistic mutation rollback,
  WebSocket invalidation. See: `learned/frontend-seam-testing.md`
- ML pipeline seams: test with real models inside containers via `docker exec`.
  Host orchestrator + container-side script pattern. See: `learned/docker-exec-integration-test.md`
- Characterization tests: pin existing behavior before refactoring — prevents regressions
  on code you don't fully understand. See: `learned/characterization-testing-existing-code.md`

## Test Database Safety

- Hard-block tests from production DB: `if "test" not in POSTGRES_URL: pytest.exit()`
  See: `learned/pytest-exit-safety-guard.md`
- Use separate `anveshak_test` DB in same postgres container — pool-based tests
  can't use transaction rollback. See: `learned/test-db-same-container-isolation.md`
- FK teardown order matters: delete in reverse dependency order (13 tables).
  See: `learned/fk-cascade-teardown-order.md`
