# Data Contracts — Frontend-Backend Shape Mismatches

Consolidated from 5 learned instincts. These apply to all data flowing between layers.

## SQL Alias = API Contract

When returning raw `dict(row)` from SQL, the column alias IS the field name the frontend receives.
TypeScript interfaces don't validate runtime API responses — mismatches produce `undefined` silently.

Checklist when adding/changing SQL aliases:
1. Check the frontend TypeScript interface that consumes the endpoint
2. Ensure every SQL alias matches the interface field name exactly
3. If renaming: update SELECT alias, HAVING, ORDER BY — all references
See: `learned/sql-alias-frontend-contract.md`

## Mock Shape Must Match Unwrapped Return

Mock return value must match the shape the code actually unpacks — not a wrapper.
If function returns `r.data` (unwrapped dict), mock must return `dict`, not `[dict]`.
When JOIN changes add columns, expand fake_row dicts to include new columns.
When function signature changes, grep all test mocks and update.
See: `learned/mock-shape-unwrap-mismatch.md`

## JSONB Double-Encoding

JSONB columns can arrive double-encoded as strings when passed through multiple
serialization layers (asyncpg → dict → JSON response → frontend parse).
Always parse defensively: `typeof val === 'string' ? JSON.parse(val) : val`
See: `learned/double-encoded-jsonb-frontend.md`

## Route Param Names Must Match Exactly

React Router `:trackerId` in route definition must match `useParams<{ trackerId: string }>()`.
Mismatch produces `undefined` — all queries disabled, blank page, no error.
See: `learned/react-router-param-name-match.md`

## External Library Label Names

spaCy, HuggingFace, and other ML libraries use abbreviated labels that differ
from common English names (FAC not FACILITY, GPE not Country).
Always verify against actual stored data before writing filters:
```sql
SELECT entity_type, COUNT(*) FROM extracted_entities GROUP BY entity_type;
```
See: `learned/spacy-entity-type-naming.md`, `learned/hf-model-label-order-verification.md`
