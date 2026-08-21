# Compose Dead Env Var Cleanup

## When to load: migrating algorithms, removing features, or auditing compose config

---

## Pattern: Algorithm migration leaves dead env vars in compose

When migrating from one algorithm to another (e.g., HDBSCAN → Leiden), the
`settings.py` fields change but the compose `environment:` block keeps the old
var names. Pydantic `BaseSettings` silently ignores unknown env vars, so:

- Old vars (`HDBSCAN_MIN_CLUSTER_SIZE`) pass through compose but are never read
- New vars (`CLUSTERING_SIMILARITY_THRESHOLD`) fall back to code defaults
- Everything "works" but config is misleading and tuning the old vars has no effect

## Pattern: Orphaned feature vars from removed adapters

When a feature/adapter is removed from code but not from compose, the vars remain
as dead config. Example: `INSTAGRAM_USERNAME` was in compose but no Instagram
adapter existed in `services/social/anveshak/social/adapters/`.

## Audit checklist (after any algorithm migration or feature removal)

1. Grep compose for the old var names — remove or replace them
2. Grep `.env.example` — update or remove old vars
3. Check if any vars in compose have no corresponding field in `settings.py`
4. Check if any `settings.py` fields are missing from compose (the reverse gap)

## Why this matters

An operator tuning `HDBSCAN_MIN_CLUSTER_SIZE=5` in `.env` thinks they're affecting
clustering behavior. The value passes to the container, appears in `docker exec env`,
but is silently ignored. No error, no warning. Only a code audit reveals the disconnect.
