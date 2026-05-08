# Test Runner

## When to load: after writing or modifying any Python code, or when user runs /test

Run the appropriate test layer based on what changed. Always show formatted results.

---

### Test tiers:

```
make test-unit         → mocked tests, no containers (~10s)
make test-integration  → DB + container model tests (~90s)
make test-e2e          → demo arc + resilience (~2min)
make test              → all three combined
make test-full         → test + coverage 80% gate (pre-release)
make test-scrape       → source connectivity (manual, needs internet)
```

### Auto-detect mode (`/test` with no args):

1. Run `git diff --name-only` to find changed files since last commit
2. Map changed files to test layers:

| Changed path pattern | Test command |
|---------------------|-------------|
| `tests/unit/`, `services/*/clean.py`, `normalise.py`, `clustering.py` | `make test-unit` |
| `tests/integration/`, `services/*/db/`, `services/*/jobs.py` | `make test-unit` then `make test-integration` |
| `services/*/nlp.py`, `services/*/embeddings.py`, `services/*/detectors/` | `make test-unit` then `make test-integration` (container model tests) |
| `sdk/` (Pydantic models, schemas) | `make test-unit` |
| `infra/`, `docker-compose`, `.env`, `Dockerfile` | `make test-integration` |
| `tests/e2e/`, `tests/resilience/` | `make test-e2e` |
| `scripts/test_*_models.py` | `make test-integration` (container tests) |
| No changes detected | `make test-unit` (sanity check) |

3. Run the mapped command(s)
4. Parse output and report:
   - Total: passed / failed / skipped / time
   - Each failure: `file_path::test_name:line_number` + assertion message
   - Coverage: per-module % with warning if any module < 80%

### Explicit modes:

- `/test unit` → `make test-unit`
- `/test integration` → `make test-integration`
- `/test e2e` → `make test-e2e`
- `/test all` → `make test`
- `/test full` → `make test-full`
- `/test scrape` → `make test-scrape`

### On failure:

1. Show the failing test with file:line
2. Read the failing test code and the code it tests
3. Diagnose whether the failure is in:
   - The test itself (fixture, import, setup) → suggest test fix
   - The production code → show what changed and what broke
4. Never silently skip failures

### Output format:

```
━━━━ Test Results ━━━━
✗ FAIL  tests/unit/test_scraper_clean.py::test_nav_removal  line 42
        AssertionError: "Home | About" found in cleaned output

✓ 47 passed  ✗ 1 failed  ⊘ 0 skipped  ⏱ 4.2s

━━━━ Coverage ━━━━
  services/scraper    91%
  services/analyst    87%
  services/vision     76% ⚠ below 80%
  TOTAL               85%
```
