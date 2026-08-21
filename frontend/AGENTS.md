# Frontend and API Data Contracts

Applies to `frontend/**/*.ts`, `frontend/**/*.tsx`, and `services/api/**/*.py`.
Repo-wide rules are in [../AGENTS.md](../AGENTS.md).
React, theming, and component patterns are in the `frontend-patterns` skill.

5 learned instincts covering all data flowing between layers.

## SQL alias is the API contract

Raw `dict(row)` from SQL means the column alias IS the field name the frontend receives.
TypeScript interfaces don't validate at runtime, so mismatches produce `undefined` silently.

Checklist for SQL alias changes:

1. Check the frontend TypeScript interface consuming the endpoint
2. Every SQL alias must match the interface field name exactly
3. When renaming, update the SELECT alias, HAVING, and ORDER BY, meaning all references

See: `.agents/skills/learned/references/sql-alias-frontend-contract.md`

## Mock shape must match unwrapped return

The mock return value must match the shape the code actually unpacks, not a wrapper.
A function returning `r.data` (an unwrapped dict) needs a mock returning `dict`, not `[dict]`.
A JOIN adding columns means expanding fake_row dicts, and a signature change means grepping all test mocks.
See: `.agents/skills/learned/references/mock-shape-unwrap-mismatch.md`

## JSONB double-encoding

JSONB columns arrive double-encoded as strings through multiple serialization layers:
asyncpg, then dict, then JSON response, then frontend parse.
Always parse defensively: `typeof val === 'string' ? JSON.parse(val) : val`
See: `.agents/skills/learned/references/double-encoded-jsonb-frontend.md`

## Route param names must match exactly

A React Router `:trackerId` in the route definition must match `useParams<{ trackerId: string }>()`.
A mismatch yields `undefined`, which disables queries and gives a blank page with no error.
See: `.agents/skills/learned/references/react-router-param-name-match.md`

## External library label names

spaCy and HuggingFace use abbreviated labels that differ from English names, such as FAC rather than FACILITY and GPE rather than Country.
Verify against stored data before writing filters:

```sql
SELECT entity_type, COUNT(*) FROM extracted_entities GROUP BY entity_type;
```

See: `.agents/skills/learned/references/spacy-entity-type-naming.md`, `.agents/skills/learned/references/hf-model-label-order-verification.md`
