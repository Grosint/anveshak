# SQL Parameter Count Must Match All Callers

## Pattern

When adding a column to a SQL INSERT constant (e.g., `$8` for org_id), grep for ALL callers of that constant and update them. The SQL constant and every `conn.execute(SQL_CONSTANT, ...)` call must have matching parameter counts.

## Pitfall

In this session, `SQL_INSERT_AUDIT_LOG` was updated from 7 to 8 params ($8 = org_id) but the two callers (`apply_credibility_drop` and `apply_credibility_boost`) still passed 7. This would crash at runtime with `asyncpg.exceptions.DataError: wrong number of parameters`. Code review caught it before deployment.

## How to apply

After modifying any SQL constant:
```bash
# Find all callers
grep -rn "SQL_INSERT_AUDIT_LOG" services/
```
Then verify each caller passes the correct number of arguments. For new required params, add them with a default (`org_id: str | None = None`) to maintain backward compatibility with existing callers.
