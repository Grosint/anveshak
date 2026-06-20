# SQL Alias Must Match Frontend Interface

## Pattern
When an API endpoint returns raw SQL rows (`dict(row)`) to the frontend,
the SQL column alias IS the API contract. If the frontend TypeScript interface
expects `count: number` but SQL aliases as `co_occurrence_count`, the field
arrives as `undefined` — silently, with no type error at build time.

## Context
Intelligence Graph showed "undefinedx" on every edge label. Root cause:
`SQL_ENTITY_COOCCURRENCE` aliased `COUNT(...) AS co_occurrence_count` but
frontend `EntityEdge` interface expected `count`. TypeScript doesn't validate
runtime API responses.

## Rule
When returning raw `dict(row)` from SQL, the SQL alias is the field name.
Match it exactly to the frontend interface. Or map fields explicitly in
the endpoint before returning.

Checklist when adding/changing SQL aliases:
1. Check the frontend TypeScript interface that consumes this endpoint
2. Ensure every SQL alias matches the interface field name exactly
3. If renaming: update SQL alias, HAVING, ORDER BY — all references

## Anti-pattern
```python
# BAD — endpoint returns raw rows, alias doesn't match frontend
edges = [dict(r) for r in rows]
return {"edges": edges}  # edge has "co_occurrence_count", frontend reads "count"
```

## Correct pattern
```python
# GOOD — alias matches frontend interface
SQL = """SELECT ... COUNT(...) AS count ..."""  # matches EntityEdge.count
```
