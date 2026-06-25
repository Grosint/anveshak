# Configuration Hygiene

9 learned instincts.

## One Setting, One Purpose

Never reuse one setting for two unrelated purposes. Two contexts with different semantics → two settings, even if values same today.

Example: `credibility_deepfake_drop` (penalty per item) vs `credibility_min_auto_drop`
(noise filter threshold). See: `learned/threshold-and-setting-invariants.md`

## Separate Thresholds for Separate Directions

Boost vs drop paths need separate thresholds. Single threshold silently blocks smaller-delta direction.

Example: `credibility_min_auto_drop` vs `credibility_min_auto_boost`
See: `learned/threshold-and-setting-invariants.md`

## Compose Environment Forwarding

Every env var in `settings.py` MUST be in compose `environment:` block.
Missing vars silently default to `false`/`""` — features disabled, no error.
See: `learned/compose-environment-consistency.md`

## Per-Component Scheduling

Track timestamps per component (per adapter, per topic) not single global interval. Different cadences.

See: `learned/per-adapter-interval-scheduling.md`

## Startup Preflight Check

Required env vars (no default) MUST block startup if missing.
Extract `${VAR}` refs from compose, check before `make up`.
Pydantic defaults silently — don't rely on it.
See: `learned/compose-env-preflight-check.md`, `learned/startup-credential-validation.md`

## Dead Variable Cleanup

After migrating algorithms or removing features, delete old env vars from compose, `.env.example`, `settings.py`. Dead vars silently ignored by pydantic — tuning them does nothing but looks correct.
See: `learned/compose-dead-env-var-cleanup.md`

## Path Resolution Verification

`Path.parents[N]` fragile — count starts from file's directory (`parents[0]`), not file itself. Verify with print. Prefer marker-file search (`while not (p / 'pyproject.toml').exists()`) over hard-coded indices.
See: `learned/path-parents-index-off-by-one.md`

## No Inline Comments on .env Integer Fields

Pydantic reads `PORT=8000 # api` as `"8000 # api"` → crash.
Comments on separate lines above variable.
See: `learned/dotenv-inline-comment-int-fields.md`

## Fail-Open on Non-Critical Enrichment

Pipeline A→B→C→D where C adds optional enrichment. C fails → pipeline must NOT crash — A→B→D produces valid output.

Wrap non-critical enrichment in try/except with structured log + safe defaults:
```python
try:
    identifiers = await db.fetch_topic_identifiers(pool, topic_id)
except Exception:
    log.warning("enrichment_failed", step="identifiers", topic_id=topic_id)
    identifiers = []  # downstream uses `if identifiers:` guard
```

Apply when: step additive, output valid without it, downstream uses `if data:` guards.
Do NOT apply when: step produces data downstream REQUIRES (RAG chunks, content_hash).
See: `learned/fail-open-enrichment-steps.md`

## Invariant Tests

Test settings don't defeat themselves:
```python
assert settings.credibility_contradiction_drop >= settings.credibility_min_auto_drop
```