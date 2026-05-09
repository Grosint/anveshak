# Configuration Hygiene

Consolidated from 9 learned instincts.

## One Setting, One Purpose

Never use one setting for two unrelated purposes. If a value is checked in two
different contexts with different semantics, create two settings — even if the
values happen to be the same today.

Example: `credibility_deepfake_drop` (penalty per item) vs `credibility_min_auto_drop`
(noise filter threshold). See: `learned/threshold-and-setting-invariants.md`

## Separate Thresholds for Separate Directions

When a feature has both positive and negative paths (boost vs drop), use separate
thresholds. A single threshold silently blocks whichever direction has a smaller delta.

Example: `credibility_min_auto_drop` vs `credibility_min_auto_boost`
See: `learned/threshold-and-setting-invariants.md`

## Compose Environment Forwarding

Every env var in `settings.py` MUST be in compose `environment:` block.
Missing vars silently default to `false`/`""` — features disabled with no error.
See: `learned/compose-environment-consistency.md`

## Per-Component Scheduling

Track timestamps per component (per adapter, per topic) rather than using a single
global interval. Different components have different natural cadences.

See: `learned/per-adapter-interval-scheduling.md`

## Startup Preflight Check

Required env vars (those with no default) MUST block startup if missing.
Extract `${VAR}` references from compose, check presence before `make up`.
Don't rely on pydantic to catch missing vars — it defaults silently.
See: `learned/compose-env-preflight-check.md`, `learned/startup-credential-validation.md`

## Dead Variable Cleanup

After migrating algorithms or removing features, delete the old env vars
from compose, `.env.example`, and `settings.py`. Dead vars are silently
ignored by pydantic — tuning them has zero effect but looks correct.
See: `learned/compose-dead-env-var-cleanup.md`

## Path Resolution Verification

Hard-coded `Path.parents[N]` indices are fragile — count starts from the file's
directory (`parents[0]`), not the file itself. Always verify with a print before
using. Prefer marker-file search (`while not (p / 'pyproject.toml').exists()`)
over hard-coded indices.
See: `learned/path-parents-index-off-by-one.md`

## No Inline Comments on .env Integer Fields

Pydantic reads `PORT=8000 # api` as string `"8000 # api"` and crashes.
Put comments on separate lines above the variable.
See: `learned/dotenv-inline-comment-int-fields.md`

## Invariant Tests

Test that settings don't defeat themselves:
```python
assert settings.credibility_contradiction_drop >= settings.credibility_min_auto_drop
```
