---
name: asyncpg-repository-pattern
description: How to structure db/ repository modules with SQL constants + typed async functions — no ORM
type: feedback
---

# asyncpg Repository Pattern

## When to load: adding or modifying any database query in a service

---

## Structure

Each service has a `db/` package. Each domain gets its own module:

```
services/api/anveshak/api/db/
├── __init__.py
├── pool.py       — connection pool + get_db() FastAPI dependency
├── topics.py     — SQL constants + typed functions for topics domain
├── sources.py    — sources + credibility audit log
├── content.py    — content_items + vector search
├── reports.py    — reports + source_warnings
├── signals.py    — signals lifecycle
├── vision.py     — media_assets + vision_results (API gateway layer)
└── auth.py       — user lookup only
```

---

## Module layout (canonical)

```python
# SQL constants — module-level, named SQL_<VERB>_<NOUN>
SQL_GET_TOPIC = "SELECT * FROM topics WHERE id = $1"

SQL_LIST_TOPICS = """
    SELECT t.id, t.name, ...
    FROM topics t
    LEFT JOIN ...
    GROUP BY t.id
    ORDER BY t.created_at DESC
"""

# Typed async functions — take conn: asyncpg.Connection, return dict or None
async def get_topic(conn: asyncpg.Connection, topic_id: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_GET_TOPIC, topic_id)
    return dict(row) if row else None

async def list_topics(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TOPICS)
    return [dict(r) for r in rows]
```

---

## Rules

**Why not SQLAlchemy ORM:**
- pgvector `<->` / `<=>` operators, JSONB queries, clustering aggregates are awkward or impossible in ORM
- Would drop to raw SQL for 40%+ of queries anyway
- Adds heavy dependency for minimal gain

**Function signatures:**
- Always `conn: asyncpg.Connection` as first arg (not pool — routes get a conn via `Depends(get_db)`)
- Return `dict[str, Any] | None` or `list[dict[str, Any]]` — never raw `asyncpg.Record`
- `dict(row) if row else None` pattern — never return a bare Record to route handlers

**Transactions:**
- Caller opens the transaction: `async with db.transaction():`
- Repository function is called inside — never opens its own transaction
- Exception: reporter/vision `db/` modules take `pool` and acquire conn internally (background workers, no FastAPI Depends)

**SQL naming:**
- `SQL_INSERT_X`, `SQL_GET_X`, `SQL_LIST_X`, `SQL_UPDATE_X`, `SQL_DELETE_X`
- Dynamic SQL (e.g. optional WHERE clauses) lives in the function body as an f-string — never concatenated outside
- Module-level constants for all static SQL (testability — mock connection sees exact SQL)

**Exists/check helpers:**
```python
async def topic_exists(conn, topic_id: str) -> bool:
    row = await conn.fetchrow("SELECT id FROM topics WHERE id = $1", topic_id)
    return row is not None
```
Routes call `topic_exists()` before updates, never inline `fetchrow` for existence checks.

---

## Testing

Mock `asyncpg.Connection` with `unittest.mock.AsyncMock`:

```python
@pytest.fixture
def mock_conn():
    return AsyncMock()

async def test_get_topic_returns_none_when_missing(mock_conn):
    mock_conn.fetchrow.return_value = None
    result = await get_topic(mock_conn, "missing")
    assert result is None

async def test_update_credibility_calls_both_sqls(mock_conn):
    """Audit log rule: must call UPDATE sources AND INSERT INTO credibility_audit_log."""
    await update_credibility(mock_conn, ...)
    assert mock_conn.execute.await_count == 2
    calls = [c[0][0] for c in mock_conn.execute.call_args_list]
    assert any("UPDATE sources" in sql for sql in calls)
    assert any("INSERT INTO credibility_audit_log" in sql for sql in calls)
```

**Why:** No running PostgreSQL needed for unit tests. SQL correctness is verified
by integration tests. Unit tests verify the function calls the right SQL and handles
None correctly.

---

## Pitfall: reporter/vision use pool, not conn

Reporter and vision are background ARQ workers — no FastAPI Depends available.
Their `db/` modules take `pool: asyncpg.Pool` and acquire inside:

```python
async def fetch_report(pool: asyncpg.Pool, report_id: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(SQL_FETCH_REPORT, report_id)
    return dict(row) if row else None
```

API service `db/` modules take `conn` directly. Don't mix the patterns.
