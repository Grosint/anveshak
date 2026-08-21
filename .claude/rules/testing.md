---
paths:
  - "**/*.py"
---
# Testing Rules

- pytest framework
- Tests MUST pass on CPU w/ default medium/nano/cpu config
- Never assume GPU in tests
- 80%+ coverage on new service code
- pytest.mark.unit — no external deps
- pytest.mark.integration — requires running Docker Compose
- pytest.mark.e2e — full demo arc, requires seeded data

## Hardware in Tests
- Mock Ollama responses in unit tests (never call real Ollama)
- Mock vision model inference in unit tests
- `httpx.MockTransport` for external API calls
- Integration tests use real PostgreSQL + Redis (Docker Compose)

## ML Test Data — Embedding Realism

- Test embeddings must be L2-normalized (sentence-transformers outputs unit vectors)
- Seeded RNG, perturb base vectors w/ controlled noise
  Calibration: 0.02 (tight clusters), 0.03 (realistic), 0.05 (broad topics)
- Golden test data: content in supported languages w/ pre-decided expected outputs
  Fuzzy keyword matching (3/5, not 5/5) — NLLB translation non-deterministic
  See: `.claude/skills/learned/test-embedding-realism.md`, `.claude/skills/learned/golden-test-data-ml-pipeline.md`

## DB Module Mocking

- New async DB function → grep all tests mocking that module, add
  `AsyncMock()` — `await` on plain MagicMock raises TypeError
- `side_effect=[row1, row2]` (not `return_value`) for functions making multiple
  sequential DB fetches w/ different column schemas
- SQL JOINs change → expand fake_row dicts w/ new columns
  See: `.claude/skills/learned/new-db-func-mock-all-callers.md`, `.claude/skills/learned/mock-sequential-db-calls.md`

## Mock Shape Must Match Reality

- Mock return value must match shape code actually unpacks — not wrapper.
  Function returns `dict` → mock returns `dict` (not `[dict]`).
- Common mismatch: API returns `r.data` (unwrapped) but mock returns `[{...}]` (wrapped)
- JOIN adds columns → expand fake_row dicts
- Function signature changes (new param) → grep all test mocks, add new param — stale mocks cause `TypeError`
  See: `.claude/skills/learned/mock-shape-unwrap-mismatch.md`

## Test-Reality Seams (A→cache→B Boundaries)

- Unit tests pass but integration breaks at service boundaries. Test seams:
  scraper→DB→analyst, analyst→DB→reporter, API→WebSocket→frontend
- Frontend seams: React Query `queryKey` prefix matching, optimistic mutation rollback,
  WebSocket invalidation. See: `.claude/skills/learned/frontend-seam-testing.md`
- ML pipeline seams: test w/ real models inside containers via `docker exec`.
  Host orchestrator + container-side script. See: `.claude/skills/learned/docker-exec-integration-test.md`
- Characterization tests: pin existing behavior before refactoring — prevents regressions
  on code you don't fully understand. See: `.claude/skills/learned/characterization-testing-existing-code.md`

## Test Database Safety

- Hard-block tests from production DB: `if "test" not in POSTGRES_URL: pytest.exit()`
  See: `.claude/skills/learned/pytest-exit-safety-guard.md`
- Separate `anveshak_test` DB in same postgres container — pool-based tests
  can't use transaction rollback. See: `.claude/skills/learned/test-db-same-container-isolation.md`
- FK teardown order matters: delete in reverse dependency order (13 tables).
  See: `.claude/skills/learned/fk-cascade-teardown-order.md`