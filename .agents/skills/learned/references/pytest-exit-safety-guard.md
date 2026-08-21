# pytest.exit() Safety Guard for Database Targeting

## Problem
Tests defaulting to the production database URL via environment variable
inheritance. Even with a separate test DB configured, a misconfigured
`POSTGRES_TEST_URL` or a CI pipeline passing `POSTGRES_URL` could route
tests back to production.

## Solution
Session-scoped autouse fixture that hard-blocks execution:

```python
@pytest.fixture(scope="session", autouse=True)
def _refuse_production_db():
    if POSTGRES_URL.rstrip("/").endswith("/anveshak") and "_test" not in POSTGRES_URL:
        pytest.exit(
            "SAFETY: Integration tests targeting production database. "
            f"URL: {POSTGRES_URL}. Set POSTGRES_TEST_URL.",
            returncode=1,
        )
```

## Why pytest.exit() instead of pytest.skip() or assert?
- `pytest.skip()` → tests are silently skipped, CI shows green, nobody notices
- `assert` / `pytest.fail()` → only fails the guard test, other tests still run
- `pytest.exit()` → kills the ENTIRE session immediately with returncode=1, CI fails loud

## When to use this pattern
Any test suite that touches shared mutable state (databases, message queues,
external APIs with side effects). The guard should check for the **production**
identifier and refuse, rather than checking for the test identifier and allowing.
Deny-by-default is safer than allow-by-match.
