# Pattern: New DB Function → Mock in All Test Callers

## When to load: adding a new query function to a service's db module

---

## Problem

When you add a new async DB function (e.g. `db.fetch_topic_location_entities()`),
any existing test that patches the entire `db` module with `patch("service.worker.db")`
will get a `MagicMock` for the new function. If the code `await`s it, you get:

```
TypeError: object MagicMock can't be used in 'await' expression
```

This breaks tests that previously passed — even though your logic is correct.

---

## The Fix

After adding any new `async def` to a db module, immediately grep for all tests
that mock that db module and add the new function:

```bash
grep -rn "mock_db_mod\." tests/unit/test_<service>*.py
```

Then add:
```python
mock_db_mod.new_function = AsyncMock(return_value=<sensible_default>)
```

---

## Checklist When Adding a DB Function

1. Write the SQL constant + async function in `db/__init__.py`
2. Use it in the worker/route
3. **Immediately** search for all tests mocking that db module:
   ```bash
   grep -rn 'patch.*worker.db' tests/
   ```
4. Add `AsyncMock(return_value=...)` for your new function in every match
5. Run `make test` to confirm

---

## Common Default Return Values

| Return type | Default mock value |
|-------------|-------------------|
| `list[str]` | `[]` |
| `list[dict]` | `[]` |
| `dict` | `{}` |
| `bool` | `True` or `False` depending on happy path |
| `None` (side effect) | `AsyncMock()` |
| `int` | `0` |

---

## Why This Keeps Happening

Python's `patch()` replaces the entire module object. `MagicMock` auto-creates
attributes on access, but returns a synchronous `MagicMock` — not an awaitable.
Only `AsyncMock` returns a coroutine when called.

---

## Also Watch: SQL Assertion Tests

Tests that assert on SQL string content (e.g. `assert "ORDER BY X" in SQL_QUERY`)
break when you add table aliases or JOINs. Use substring matching that's resilient
to prefix changes:

```python
# Fragile:
assert "ORDER BY credibility_score ASC" in normalised

# Resilient:
assert "CREDIBILITY_SCORE ASC" in normalised.upper()
```

---

## Implementation reference
- `tests/unit/test_reporter_immutability.py` — 3 patches added for `fetch_topic_location_entities`
- `tests/unit/test_sources_api_filters.py` — relaxed SQL assertion
