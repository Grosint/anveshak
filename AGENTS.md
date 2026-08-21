# Anveshak

Sovereign OSINT platform.
Scrapes open sources, clusters content into narratives, fires signals when a story crosses an independent-source threshold, and generates immutable intelligence reports.

Python services under `services/`, shared SDK under `sdk/anveshak/`, React analyst workbench under `frontend/`, Docker and k3s under `infra/`.
Domain vocabulary is defined in [CONTEXT.md](CONTEXT.md); read it before naming anything.

## Where instructions live

This file holds repo-wide rules.
Directory-specific rules live in nested `AGENTS.md` files and take precedence within their subtree:

- [`infra/AGENTS.md`](infra/AGENTS.md) for Docker, Compose, and the Makefile
- [`services/AGENTS.md`](services/AGENTS.md) for database access and SQL
- [`frontend/AGENTS.md`](frontend/AGENTS.md) for API and UI data contracts

Deeper procedural knowledge is packaged as Agent Skills in `.agents/skills/`.
Each skill declares in its `description` when it applies, so load one when the task matches rather than reading them all.
The `learned` skill indexes 181 notes on specific failure modes; other skills and these rules cite it by path.

## Architectural rules, always enforce

These are numbered and stable.
Code comments and tests cite them by number, so never renumber them; append instead.

1. **Standalone-first.** Every service starts with `ANVESHAK_DRISHTI_BRIDGE=false`. Anveshak NEVER requires Drishti.
2. **Labels mandatory.** Every Pydantic model that is persisted or crosses a service boundary on its own MUST have `labels: Labels`, NEVER Optional. Never create a model without it. A nested value object that only ever exists inside an already-labelled parent inherits that parent's classification and is exempt, but the exemption is not automatic: it must be declared with a reason in `EXEMPT_MODELS` in `scripts/verify_labels.py`, which denies by default. `make verify-labels` enforces this.
3. **Content dedup mandatory.** Every ContentItem MUST have `content_hash`, a SHA-256 of normalised clean_text. All inserts use `ON CONFLICT(content_hash) DO NOTHING`. Narrow exception: where the platform guarantees an ID that outlives edits to the text, the hash may key on `{platform}:{stable_id}` instead. This is opt-in per item via `RawItem.stable_id`, never a default, and only for sources the platform itself re-writes: a YouTube ASR re-run rewrites the transcript of an unchanged video, and text hashing re-ingests it every poll. A user editing their own post is NOT this case, and must still produce a new hash.
4. **Reports immutable.** Once `generated_at` is set it is NEVER updated. A report is a point-in-time snapshot, and content changes produce a new report. `source_snapshot` captures credibility at generation time.
5. **All LLM calls async.** FastAPI routes NEVER call Ollama directly. All LLM inference is dispatched as an ARQ job and polled by the client.
6. **Hardware independence mandatory.** No model name, device string (`cpu` or `cuda`), batch size, or ML param is hardcoded in service code. All of it comes from `settings.py` via env vars. See `hardware.md`.
7. **Deepfake scores are probabilities, never booleans.** Return a float 0.0 to 1.0, never `is_deepfake: bool`. The analyst decides the threshold.
8. **Credibility changes audit-logged.** Every `credibility_score` change MUST insert a row into `credibility_audit_log`. No silent updates.
9. **LLM output validated before use.** All LLM responses are parsed through a Pydantic model before storage or display. Never trust a raw LLM string.
10. **No cloud LLM with real data.** Ollama is localhost or the internal Docker network only. This is a sovereignty requirement: intel data never leaves the deployment boundary.
11. **X/Twitter spend guard.** XAdapter checks the monthly read count against `X_MONTHLY_READ_CAP` before every API call. Never exceed the budget silently.
12. **Drishti bridge one-directional.** Anveshak emits entities TO Drishti via `source.envelopes.v1` and NEVER reads from Drishti. No circular dependency.

## Python coding style

- PEP 8
- Type annotations on all function signatures
- black formatting, ruff linting, isort imports
- Pydantic v2 strict: `model_config = ConfigDict(strict=True)` on ALL models
- `labels` field MANDATORY and non-Optional on all Pydantic models
- Immutable dataclasses for DTOs where they fit
- Module-level constants for SQL queries, for testability
- No bare `except:` clauses

## Python patterns

### ARQ job pattern (mandatory for all LLM calls)

```python
async def enqueue_report_job(topic_id: str, redis: Redis) -> str:
    job = await arq.create_pool(redis_settings).enqueue_job(
        "generate_report", topic_id
    )
    return job.job_id
```

### Content deduplication pattern (mandatory)

```python
# Always use ON CONFLICT(content_hash) DO NOTHING
await conn.execute(
    "INSERT INTO content_items (...) VALUES (...) ON CONFLICT(content_hash) DO NOTHING"
)
```

### Hardware config pattern (mandatory for all ML)

```python
# In settings.py — never in service code
class VisionSettings(BaseSettings):
    yolo_model_size: str = "nano"  # nano → xlarge on GPU upgrade
    vision_device: str = "cpu"     # cpu → cuda on GPU upgrade
```

### Threshold invariant testing pattern (mandatory for config)

```python
# Test that thresholds don't defeat each other
def test_threshold_invariants():
    assert settings.credibility_contradiction_drop >= settings.credibility_min_auto_drop
    assert settings.clustering_similarity_threshold <= settings.cluster_assign_threshold
    # Quality gate applied at ALL consumption points
    for sql in [SQL_TOPIC_CONTENT, SQL_RAG_CHUNKS, SQL_CLUSTER_INPUT]:
        assert "content_quality" in sql.lower() or "quality" in sql.lower()
```

### Report immutability pattern (mandatory)

```python
# generated_at is set ONCE. Never in an UPDATE.
# Always check before generating:
existing = await conn.fetchrow(
    "SELECT id FROM reports WHERE topic_id=$1 AND report_type=$2 "
    "AND generated_at > NOW() - INTERVAL '24 hours'",
    topic_id, report_type
)
if existing:
    return existing["id"]  # return cached, never regenerate within 24h
```

## Security

### Secrets

- NEVER hardcode secrets, API keys, tokens, passwords
- ALL credentials from env vars
- python-dotenv for local dev, real env vars in prod

### LLM security

- NEVER send user-controlled text to an LLM without sanitisation
- NEVER use LLM output in SQL or shell without Pydantic validation first
- NEVER call a cloud LLM with real intel data (sovereign requirement)
- Ollama must be localhost or internal Docker network only

### Content security

- Scraped content is untrusted input, sanitise before storage
- Scraper images are potentially adversarial, run them in the isolated vision service
- `content_hash` (SHA-256) on every ContentItem, for dedup and integrity

### Scanning

- `bandit -r src/` before any commit
- No secrets in Docker Compose environment blocks, use `${VAR}` references

## Testing

- pytest framework
- Tests MUST pass on CPU with default medium/nano/cpu config
- Never assume GPU in tests
- 80%+ coverage on new service code
- `pytest.mark.unit` for no external deps
- `pytest.mark.integration` requires running Docker Compose
- `pytest.mark.e2e` for the full demo arc, requires seeded data

### Hardware in tests

- Mock Ollama responses in unit tests, never call real Ollama
- Mock vision model inference in unit tests
- `httpx.MockTransport` for external API calls
- Integration tests use real PostgreSQL and Redis via Docker Compose

### ML test data and embedding realism

- Test embeddings must be L2-normalized, since sentence-transformers outputs unit vectors
- Seeded RNG, perturb base vectors with controlled noise.
  Calibration: 0.02 (tight clusters), 0.03 (realistic), 0.05 (broad topics)
- Golden test data: content in supported languages with pre-decided expected outputs.
  Fuzzy keyword matching (3/5, not 5/5), NLLB translation is non-deterministic.
  See: `.agents/skills/learned/references/test-embedding-realism.md`, `.agents/skills/learned/references/golden-test-data-ml-pipeline.md`

### DB module mocking

- New async DB function means grep all tests mocking that module and add
  `AsyncMock()`; `await` on a plain MagicMock raises TypeError
- `side_effect=[row1, row2]` (not `return_value`) for functions making multiple
  sequential DB fetches with different column schemas
- SQL JOINs change means expanding fake_row dicts with the new columns.
  See: `.agents/skills/learned/references/new-db-func-mock-all-callers.md`, `.agents/skills/learned/references/mock-sequential-db-calls.md`

### Mock shape must match reality

- Mock return value must match the shape the code actually unpacks, not a wrapper.
  Function returns `dict` means the mock returns `dict`, not `[dict]`.
- Common mismatch: API returns `r.data` (unwrapped) but the mock returns `[{...}]` (wrapped)
- JOIN adds columns means expanding fake_row dicts
- Function signature changes (new param) means grepping all test mocks and adding it; stale mocks cause `TypeError`.
  See: `.agents/skills/learned/references/mock-shape-unwrap-mismatch.md`

### Test-reality seams (A to cache to B boundaries)

- Unit tests pass but integration breaks at service boundaries. Test the seams:
  scraper to DB to analyst, analyst to DB to reporter, API to WebSocket to frontend
- Frontend seams: React Query `queryKey` prefix matching, optimistic mutation rollback,
  WebSocket invalidation. See: `.agents/skills/learned/references/frontend-seam-testing.md`
- ML pipeline seams: test with real models inside containers via `docker exec`.
  Host orchestrator plus container-side script. See: `.agents/skills/learned/references/docker-exec-integration-test.md`
- Characterization tests pin existing behavior before refactoring, which prevents regressions
  on code you don't fully understand. See: `.agents/skills/learned/references/characterization-testing-existing-code.md`

### Test database safety

- Hard-block tests from the production DB: `if "test" not in POSTGRES_URL: pytest.exit()`.
  See: `.agents/skills/learned/references/pytest-exit-safety-guard.md`
- Separate `anveshak_test` DB in the same postgres container; pool-based tests
  can't use transaction rollback. See: `.agents/skills/learned/references/test-db-same-container-isolation.md`
- FK teardown order matters, delete in reverse dependency order across 13 tables.
  See: `.agents/skills/learned/references/fk-cascade-teardown-order.md`

## Silent failure prevention

Silent failures are the top source of production bugs here.
Every conditional feature (flag, env toggle, optional dependency) MUST log at INFO when disabled or degraded.
An analyst debugging a missing signal at 2am needs to know WHY a feature is off, not just see no output.

- Feature off: `log.info("feature.disabled", feature="X", reason="env var not set")`
- Optional model missing: `log.warning("model.not_loaded", model="X")`, never return 0.0 silently

### Return values

- ML float scores return `None` on error, never `0.0` or a default.
  This forces null checks at call sites (`if score is not None`).
  See: `.agents/skills/learned/references/deepfake-none-error-signal.md`
- Mandatory output fields are set in every return path, not just the happy path

### Environment and configuration

- Every env var in `settings.py` MUST appear in the compose `environment:` block.
  Missing vars silently default to `false` or `""` with no error.
  See: `.agents/skills/learned/references/compose-environment-consistency.md`
- No inline comments on integer env vars in `.env`; pydantic crashes on them.
  See: `.agents/skills/learned/references/dotenv-inline-comment-int-fields.md`
- Core features belong in base `compose.yml`, never in overlay files.
  See: `.agents/skills/learned/references/compose-overlay-core-feature-trap.md`

### Quality gates

- A computed quality signal must be applied at EVERY consumption point: SQL, API, reports.
  Use `WHERE quality IS NULL OR quality >= threshold` for backward compat.
  Checklist: compute, SQL filter, API filter, RAG context, report display.
  See: `.agents/skills/learned/references/quality-gate-all-consumers.md`
- Word-counting regex must cover all scripts (Devanagari, Arabic, CJK).
  Missing ranges silently drop content as zero words.
  See: `.agents/skills/learned/references/quality-gate-unicode-ranges.md`
- `detect_language()` must return the real detected language even if no downstream model supports it.
  Filtering on model availability silently drops content.
  See: `.agents/skills/learned/references/detect-language-must-not-gatekeep.md`

### ML models

- Volume-mounted models start empty on first deploy, so add health checks.
  An empty volume yields silent 0.0 scores with no error.
  See: `.agents/skills/learned/references/volume-mounted-models-silent-failure.md`

### Scripts using psql subprocess

- `psql -A -F "\t"` returns `''` for NULL, not Python `None`.
  `float(row["col"]) if row.get("col") is not None` crashes with `ValueError: could not convert string to float: ''`.
  Use truthiness instead: `float(raw) if raw else default`.
  This affects subprocess scripts only; asyncpg returns proper None.
  See: `.agents/skills/learned/references/psql-null-empty-string-pitfall.md`

### Array matching

- PostgreSQL `&&` returns false silently when granularity differs, such as multi-word keywords against single-word tags.
  Normalize before matching.
  See: `.agents/skills/learned/references/keyword-tag-granularity-mismatch.md`

### Git and build

- Blanket `.gitignore` patterns (`models/`, `media/`) silently exclude Python packages with the same name.
  Fresh clones then break with `ImportError` while dev machines stay fine.
  Use negation: `!sdk/anveshak/models/`.
  See the `git-build` skill.

## Configuration hygiene

### One setting, one purpose

Never reuse one setting for two unrelated purposes.
Two contexts with different semantics need two settings, even if the values match today.

Example: `credibility_deepfake_drop` (penalty per item) against `credibility_min_auto_drop` (noise filter threshold).
See: `.agents/skills/learned/references/threshold-and-setting-invariants.md`

### Separate thresholds for separate directions

Boost and drop paths need separate thresholds.
A single threshold silently blocks the smaller-delta direction.

Example: `credibility_min_auto_drop` against `credibility_min_auto_boost`.
See: `.agents/skills/learned/references/threshold-and-setting-invariants.md`

### Compose environment forwarding

Every env var in `settings.py` MUST be in the compose `environment:` block.
Missing vars silently default to `false` or `""`, so features are disabled with no error.
See: `.agents/skills/learned/references/compose-environment-consistency.md`

### Per-component scheduling

Track timestamps per component (per adapter, per topic), not as a single global interval, because cadences differ.
See: `.agents/skills/learned/references/per-adapter-interval-scheduling.md`

### Startup preflight check

Required env vars with no default MUST block startup if missing.
Extract `${VAR}` refs from compose and check before `make up`.
Pydantic defaults silently, so don't rely on it.
See: `.agents/skills/learned/references/compose-env-preflight-check.md`, `.agents/skills/learned/references/startup-credential-validation.md`

### Dead variable cleanup

After migrating algorithms or removing features, delete the old env vars from compose, `.env.example`, and `settings.py`.
Dead vars are silently ignored by pydantic, so tuning them does nothing but looks correct.
See: `.agents/skills/learned/references/compose-dead-env-var-cleanup.md`

### Path resolution verification

`Path.parents[N]` is fragile because the count starts from the file's directory (`parents[0]`), not the file itself.
Verify with print.
Prefer a marker-file search (`while not (p / 'pyproject.toml').exists()`) over hard-coded indices.
See: `.agents/skills/learned/references/path-parents-index-off-by-one.md`

### No inline comments on .env integer fields

Pydantic reads `PORT=8000 # api` as `"8000 # api"` and crashes.
Put comments on separate lines above the variable.
See: `.agents/skills/learned/references/dotenv-inline-comment-int-fields.md`

### Fail-open on non-critical enrichment

In a pipeline A to B to C to D where C adds optional enrichment, a failure in C must NOT crash the pipeline.
A to B to D still produces valid output.

Wrap non-critical enrichment in try/except with a structured log and safe defaults:

```python
try:
    identifiers = await db.fetch_topic_identifiers(pool, topic_id)
except Exception:
    log.warning("enrichment_failed", step="identifiers", topic_id=topic_id)
    identifiers = []  # downstream uses `if identifiers:` guard
```

Apply when the step is additive, the output is valid without it, and downstream uses `if data:` guards.
Do NOT apply when the step produces data downstream REQUIRES, such as RAG chunks or content_hash.
See: `.agents/skills/learned/references/fail-open-enrichment-steps.md`

### Invariant tests

Test that settings don't defeat themselves:

```python
assert settings.credibility_contradiction_drop >= settings.credibility_min_auto_drop
```

## Multi-tenancy

All org isolation and access control.

### org_id placement, root tables only

`org_id` goes on root entities only: users, topics, sources, content_items, credibility_audit_log.
Children (signals, clusters, reports, entities, media_assets, vision_results) inherit through the `topic_id` FK and need no org_id.

Exception: tables with no topic_id path, such as credibility_audit_log, need a direct org_id.
Exception: tables accessible by direct UUID, such as content_items, need org_id for defense in depth.
See: `.agents/skills/learned/references/org-id-root-tables-only.md`

### Dual-layer isolation

Primary layer is `verify_topic_access()` or `verify_source_access()` on every route.
Secondary layer is PostgreSQL Row-Level Security as a safety net.

RLS pattern: `USING (current_setting('app.current_org', true) = '' OR org_id = current_setting(...))`.
The API sets `SET LOCAL app.current_org` per request, which is transaction-scoped and safe with pooling.
Background services use the `anveshak_worker` role with `BYPASSRLS`.
See: `.agents/skills/learned/references/dual-layer-rls-safety-net.md`

### Source visibility, global sources with org-scoped access

Sources are global entities, since an RSS feed is the same feed for everyone.
Don't duplicate them per org.
Use the `org_sources` join table for visibility, and have `SQL_LIST_SOURCES` JOIN through it.
When an org creates a source, auto-link it in `org_sources`.
See: `.agents/skills/learned/references/global-sources-org-visibility.md`

### Role constraints and migrations

Adding a new role such as `super-admin` means updating the CHECK constraint in the SAME migration, BEFORE any INSERT that uses the new role.
Use `DROP CONSTRAINT IF EXISTS` plus `ADD CONSTRAINT` for idempotency.
See: `.agents/skills/learned/references/role-constraint-migration-order.md`

### Seed scripts must match schema

When a migration adds a NOT NULL `org_id`, update ALL seed SQL INSERTs with the column and add rows to join tables such as `org_sources`.
Seeds run on fresh DBs, so there is nothing to backfill.
See: `.agents/skills/learned/references/seed-sql-must-match-migration.md`

### Cross-org leak prevention

Every cross-topic query (convergence, similarity) MUST filter `AND t1.org_id = t2.org_id`.
WebSocket signal broadcast filters by session org_id.
Export endpoints verify topic ownership before executing.
SQL param count must match all callers after adding org_id columns.
See: `.agents/skills/learned/references/sql-param-count-caller-mismatch.md`

### Cross-topic aggregate endpoints

Aggregate endpoints such as the analytics dashboard and global stats have no single resource to verify.
org_id must be baked into EVERY SQL sub-query, since missing one leaks cross-org data.
Tables without org_id, such as signals and reports, JOIN through `topics.org_id`.
Make org_id a keyword-only param on the repository function so it can't be forgotten.
Test by asserting "org_id" appears in every SQL constant and in every DB call's args.
See: `.agents/skills/learned/references/cross-topic-aggregate-org-scoping.md`

## Development practices

### Wiring check after GREEN

After tests pass, verify every new symbol has a caller.
Agents create new files but miss modifying existing ones.
Checklist: new function means grep for callers, new async loop means grep for lifespan registration, new router means verify main.py, new component means verify the route renders it.
See: `.agents/skills/learned/references/agent-wiring-check-after-green.md`

### Characterization testing for existing code

For existing working code, read first, then pin current behavior including bugs.
Mark bugs explicitly: `test('BUG R2: defaults to HIGH for unknown types')`.
Watch for hollow tests: `expect(document.body).toBeTruthy()` always passes, replace it with specific assertions.
TDD is for new features only; characterization is the safety net before refactoring.
See: `.agents/skills/learned/references/characterization-testing-existing-code.md`

### Demo seed script

Multi-stage: DB seed (idempotent), then ARQ enqueue and poll, then clustering, then pre-seeded signals, then auth, then report generation, then PDF.
Run ONE seed at a time on CPU, since concurrent report generations time out.
Pre-seed signals for demo reliability.
`ON CONFLICT DO NOTHING` allows reruns.
Explicit step counters like `[3/8]` show which step hangs.
Use `--replay` and `--live` flags with an `ANVESHAK_ALLOW_LIVE=1` env guard.
See: `.agents/skills/learned/references/demo-seed-script-pattern.md`

### Makefile infrastructure-first

Phased startup: infra (postgres, redis, ollama), then a health-poll loop, then migrate, then app services.
Never `sleep N` for health, always poll.
Migrations run BEFORE app services or they crash-loop on an empty schema.
Use `--format json` for machine-parseable health status.
`$(call warn,...)` breaks inside shell blocks, use plain printf.
See: `.agents/skills/learned/references/makefile-infrastructure-first-setup.md`

### Migration files in containers

Host migration files are NOT visible in running containers, since they are COPYed rather than volume-mounted.
`alembic upgrade head` then runs zero migrations with no error.
Fix with `docker cp` or rebuild the image.
Don't forget the test database migration too.
See: `.agents/skills/learned/references/migration-not-visible-in-container.md`

### Phase-check pitfalls

WebSocket: calling `accept()` before `verify_token()` makes auth aspirational rather than enforced.
Settings: a new setting in settings.py with zero grep matches in service code is not wired.
Status strings: use exact spec values (`"queued"`, not `"pending"`), and test the exact string rather than just truthiness.
SQL JOINs: if the frontend shows a field from a related table, verify the SQL has the JOIN, not just that the TypeScript type has it.
Self-defeating defaults: `boost=2.0` under `min_threshold=10.0` means the feature never fires; write invariant tests.
See: `.agents/skills/learned/references/phase-check-pitfalls.md`

### Session boundary plan-driven development

For multi-session projects, write the plan to a `docs/` file ONCE.
Each session then needs three lines: read the plan, state the step, run TDD.
The plan holds architecture, numbered steps, phased exit criteria, a test matrix, and a risk register.
Memory tracks decisions and preferences; plans track implementation sequences.
See: `.agents/skills/learned/references/session-boundary-plan-driven-dev.md`

### pytest.exit() safety guard

Use a session-scoped autouse fixture that hard-blocks if it is targeting a production DB.
`pytest.exit()` kills the entire session with returncode=1.
`pytest.skip()` is silently green and `pytest.fail()` only fails the guard test while others still run.
Deny by default: check for a production identifier and refuse, rather than checking for a test identifier and allowing.
See: `.agents/skills/learned/references/pytest-exit-safety-guard.md`

## Development workflow

### 0. Research and reuse (mandatory before new implementation)

Search existing patterns in the codebase first.
Check `hardware.md` before adding an ML component.
Check `.agents/skills/` for a relevant skill.

### 1. Plan first

Write a plan before any non-trivial change.
Document hardware-sensitive decisions in `hardware.md`.
Break work into phases.

### 2. TDD

Use the `tdd` skill.
Tests must pass on CPU with default config; never assume GPU.
RED, then GREEN, then IMPROVE.
80%+ coverage on new code.

### 3. Test

Run the layer appropriate to what changed, or use the `test` skill to auto-detect:

- Pure logic: `make test-unit` (under 30s)
- SQL, DB, wiring: `make test-integration` (under 5min)
- Service contracts: `make test-contract` (under 60s)
- Before push: `make test-ci` (under 6min)
- Before demo: `make test-scrape` (under 10min)

Every run reports pass/fail with file:line, and coverage per module.

### 4. Code review

Use the `code-review` skill after writing code.
Address all FAIL issues before committing.

### 5. Commit

Unit tests must pass before commit (`make test-unit`).
Use conventional commit format; see the `git-workflow` skill.
