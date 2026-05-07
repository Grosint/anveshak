# Test Runner

## When to load: after writing or modifying any Python code, or when user runs /test

Run the appropriate test layer based on what changed. Always show formatted results.

---

### Auto-detect mode (`/test` with no args):

1. Run `git diff --name-only` to find changed files since last commit
2. Map changed files to test layers:

| Changed path pattern | Test command |
|---------------------|-------------|
| `services/*/clean.py`, `normalise.py`, `rss.py`, `clustering.py` | `make test-unit` |
| `services/*/db/`, `services/*/jobs.py`, `services/*/main.py` | `make test-unit` then `make test-integration` |
| `sdk/` (Pydantic models, schemas) | `make test-unit` then `make test-contract` |
| `infra/`, `docker-compose`, `.env` | `make test-smoke` |
| `tests/unit/` | `make test-unit` |
| `tests/integration/` | `make test-integration` |
| `tests/e2e/` | `make test-e2e` |
| No changes detected | `make test-unit` (sanity check) |

3. Run the mapped command(s)
4. Parse output and report:
   - Total: passed / failed / skipped / time
   - Each failure: `file_path::test_name:line_number` + assertion message
   - Coverage: per-module % with warning if any module < 80%

### Explicit modes:

- `/test unit` → `make test-unit`
- `/test integration` → `make test-integration`
- `/test contract` → `make test-contract`
- `/test scrape` → `make test-scrape`
- `/test e2e` → `make test-e2e`
- `/test smoke` → `make test-smoke`
- `/test ci` → `make test-ci` (unit + contract + integration, with 80% gate)
- `/test all` → `make test-all`
- `/test fast` → `make test-fast` (parallel unit with pytest-xdist)
- `/test coverage` → `make test-coverage` (full report with missing lines)
- `/test vector` → `make test-vector`

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
