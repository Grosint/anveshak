Run the appropriate test layer based on what changed. Argument: $ARGUMENTS

## If no argument provided (auto-detect mode):

1. Run `git diff --name-only` to find changed files (staged + unstaged)
2. Map changed files to test commands:
   - `services/*/clean.py`, `normalise.py`, `rss.py`, `clustering.py` → `make test-unit`
   - `services/*/db/`, `services/*/jobs.py`, `services/*/main.py` → `make test-unit` then `make test-integration`
   - `sdk/` model changes → `make test-unit` then `make test-contract`
   - `infra/`, `docker-compose`, `.env` → `make test-smoke`
   - `tests/unit/` → `make test-unit`
   - `tests/integration/` → `make test-integration`
   - `tests/e2e/` → `make test-e2e`
   - No changes → `make test-unit` (sanity check)
3. Run the command(s) and report results

## If argument provided (explicit mode):

| Argument | Command |
|----------|---------|
| `unit` | `make test-unit` |
| `integration` | `make test-integration` |
| `contract` | `make test-contract` |
| `scrape` | `make test-scrape` |
| `e2e` | `make test-e2e` |
| `smoke` | `make test-smoke` |
| `ci` | `make test-ci` |
| `all` | `make test-all` |
| `fast` | `make test-fast` |
| `coverage` | `make test-coverage` |
| `vector` | `make test-vector` |

## After running:

1. Report: ✓ passed count, ✗ failed count with file:line, coverage %
2. If any test fails: read the failing test and the code it tests, diagnose the root cause
3. Never silently skip failures
