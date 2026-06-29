# Identifier Type Wiring Checklist

## Problem
Adding a new identifier type (e.g., FACEBOOK_HANDLE) requires updating 13 files
across 4 layers. Missing any one silently breaks: frontend shows raw type string,
partial index misses rows, reports omit the type, pipeline health reports gaps.

## Checklist — all required for each new identifier type

### Backend (5 files)
1. `services/analyst/anveshak/analyst/identifiers.py` — extraction logic
2. `services/api/anveshak/api/db/identifiers.py` — IDENTIFIER_TYPES tuple (drives SQL fragment)
3. `services/analyst/anveshak/analyst/scheduler.py` — _ENGINE_C_TYPES tuple
4. `scripts/pipeline_health.py` — ENGINE_C_IDENTIFIER_TYPES tuple
5. `services/reporter/anveshak/reporter/rag.py` — display label dict

### Migration (1 file)
6. `services/api/migrations/versions/0XX_*.py` — partial index on extracted_entities

### Frontend (6 files)
7. `frontend/src/api/identifiers.ts` — IdentifierType union
8. `frontend/src/pages/Identifiers.tsx` — IDENTIFIER_TYPES array + TypeBadge colorMap
9. `frontend/src/components/search/IdentifierSearch.tsx` — IDENTIFIER_TYPES array + TypeBadge colorMap
10. `frontend/src/components/workspace/EntityGraph.tsx` — ID_STYLES dict
11. `frontend/src/components/workspace/OverviewTab.tsx` — TYPE_COLORS + TYPE_SHORT dicts
12. `frontend/src/components/workspace/TopIdentifiers.tsx` — TYPE_SHORT dict

### Tests (1 file)
13. `tests/unit/test_identifiers.py` — extraction tests + update all-types test

## Verification
```bash
# Grep for the new type across all registries:
grep -r 'NEW_TYPE' services/api/anveshak/api/db/identifiers.py \
  services/analyst/anveshak/analyst/scheduler.py \
  scripts/pipeline_health.py \
  frontend/src/api/identifiers.ts \
  frontend/src/pages/Identifiers.tsx \
  frontend/src/components/search/IdentifierSearch.tsx

# TypeScript compile check:
cd frontend && npx tsc --noEmit

# Unit tests:
uv run pytest tests/unit/test_identifiers.py -v
```

## Why this matters
- Missing from IDENTIFIER_TYPES → SQL fragment excludes it from queries → invisible in API
- Missing from frontend → raw string like "FACEBOOK_HANDLE" shown instead of "Facebook"
- Missing from partial index → full table scan instead of index lookup
- Missing from pipeline_health → health check reports false gap
