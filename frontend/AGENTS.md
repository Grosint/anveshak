# Frontend and API Data Contracts

Applies to `frontend/**/*.ts`, `frontend/**/*.tsx`, and `services/api/**/*.py`.
Repo-wide rules are in [../AGENTS.md](../AGENTS.md).
React, theming, and component patterns are in the `frontend-patterns` skill.

8 notes covering data flowing between layers, plus how this code is structured and linted.

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
Never call `JSON.parse` directly, since it returns `any` and defeats type checking.
Use `parseJsonObject` from `src/lib/json.ts`, which unwraps the extra encoding layer
and returns `Record<string, unknown>` for null, malformed JSON, and non-objects alike.
Read individual fields out of it with `asText` or `asNumber` from `src/lib/scalar.ts`.
See: `.agents/skills/learned/references/double-encoded-jsonb-frontend.md`

## Route param names must match exactly

A React Router `:trackerId` in the route definition must match `useParams<{ trackerId: string }>()`.
A mismatch yields `undefined`, which disables queries and gives a blank page with no error.
See: `.agents/skills/learned/references/react-router-param-name-match.md`

## Failed API calls

Every route in `services/api` reports a failure as `{"detail": "..."}`.
Read it with `apiErrorDetail(error, fallback)` and `apiErrorStatus(error)` from
`src/lib/apiError.ts` rather than reaching into `err.response.data.detail` inline.
Both take `unknown`, because a rejected promise carries no type, and both read the
error structurally, so a plain object from a test mock works the same as an `AxiosError`.

## Context files export one thing

A file that exports a provider component must export nothing else, or Vite's fast
refresh falls back to a full page reload on every edit.
Each context is therefore split in two: `contexts/AuthContext.tsx` holds `AuthProvider`
alone, and `contexts/auth.ts` holds the context object, the `useAuth` hook and the
plain helpers. Same shape for `ws`, `theme` and `provenance`.
A test mocking a hook mocks the lowercase module (`contexts/auth`), not the provider file.

## Linting

`npx eslint .` in `frontend/`, or `make lint-frontend` from the repo root.
The config is `frontend/eslint.config.mjs`, ESLint 10 flat config with type-aware
`typescript-eslint` rules over `src/`, so a new `any` leaking out of an untyped API
call is an error rather than a silent hole.
Tests under `src/test/` sit outside `tsconfig.json`, so they get syntax-only linting.

## External library label names

spaCy and HuggingFace use abbreviated labels that differ from English names, such as FAC rather than FACILITY and GPE rather than Country.
Verify against stored data before writing filters:

```sql
SELECT entity_type, COUNT(*) FROM extracted_entities GROUP BY entity_type;
```

See: `.agents/skills/learned/references/spacy-entity-type-naming.md`, `.agents/skills/learned/references/hf-model-label-order-verification.md`
