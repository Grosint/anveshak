# Data Contracts — Frontend-Backend Shape Mismatches

5 learned instincts. All data flowing between layers.

## SQL Alias = API Contract

Raw `dict(row)` from SQL — column alias IS field name frontend receives.
TypeScript interfaces don't validate runtime — mismatches produce `undefined` silently.

Checklist for SQL alias changes:
1. Check frontend TypeScript interface consuming endpoint
2. Every SQL alias must match interface field name exactly
3. Renaming: update SELECT alias, HAVING, ORDER BY — all references
See: `learned/sql-alias-frontend-contract.md`

## Mock Shape Must Match Unwrapped Return

Mock return value must match shape code actually unpacks — not wrapper.
Function returns `r.data` (unwrapped dict) → mock returns `dict`, not `[dict]`.
JOIN adds columns → expand fake_row dicts. Signature changes → grep all test mocks.
See: `learned/mock-shape-unwrap-mismatch.md`

## JSONB Double-Encoding

JSONB columns arrive double-encoded as strings through multiple serialization layers (asyncpg → dict → JSON response → frontend parse).
Always parse defensively: `typeof val === 'string' ? JSON.parse(val) : val`
See: `learned/double-encoded-jsonb-frontend.md`

## Route Param Names Must Match Exactly

React Router `:trackerId` in route definition must match `useParams<{ trackerId: string }>()`.
Mismatch → `undefined` — queries disabled, blank page, no error.
See: `learned/react-router-param-name-match.md`

## External Library Label Names

spaCy, HuggingFace use abbreviated labels differing from English names (FAC not FACILITY, GPE not Country).
Verify against stored data before writing filters:
```sql
SELECT entity_type, COUNT(*) FROM extracted_entities GROUP BY entity_type;
```
See: `learned/spacy-entity-type-naming.md`, `learned/hf-model-label-order-verification.md`