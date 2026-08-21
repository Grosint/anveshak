# Host venv Rebuild, Python Pinning, and the Quality-Target Backlog

Written 2026-08-20, alongside the `chore/harness-agnostic-agents` branch.
Last updated 2026-08-21.

The original scope was the venv rebuild.
Verifying it uncovered that four Makefile quality targets had been silently dead, so this document now also tracks the backlog that exposed.

**Nothing here is committed yet.**
All of the work below is in the working tree on `chore/harness-agnostic-agents`.

## Status at a glance

Done:

- [x] Interpreter pinned to 3.12, in version control
- [x] `.venv` rebuilt on a uv-managed CPython, off Anaconda
- [x] `make venv-check` guard, wired into every test target, all five failure modes negative-tested
- [x] `make lint` clean, 1334 errors to 0
- [x] `make format` clean and stable, 470 files
- [x] `make security-scan` clean, 28 findings to 0
- [x] `pyright` installed and configured, so `make typecheck` runs at all
- [x] Unit and contract suites no longer segfault when run in one process
- [x] [1. Pyright backlog](#1-pyright-backlog-176-errors-to-0) - 176 errors to 0, `make typecheck` passes
- [x] [2. `make verify-labels`](#2-make-verify-labels-resolved-by-narrowing-rule-2) - rule 2 scope resolved, passes
- [x] [3. The 19 baseline test failures](#3-the-19-baseline-test-failures-all-fixed) - all fixed, 2387 pass
- [x] [4. Three tests that never assert](#4-three-tests-that-never-assert-assertions-restored) - assertions restored
- [x] `make test-frontend` - 378 tests across 36 files, all passing
- [x] `make test-contract` - target added, it was documented but did not exist
- [x] [5. Integration suite, host-side](#5-verification-integration-now-passes) - 6 failures to 0, 128 passing
- [x] [7. Runtime saturation](#7-runtime-saturation-the-analyst-worker-hang) - the analyst worker hang and the scraper OOM loop, both fixed

Not done, in suggested order:

- [ ] [5b. `make test-ci` and `make test-scrape`](#5-verification-integration-now-passes) - still unrun
- [ ] [6. Commit the branch](#6-commit-the-branch)

Two findings surfaced during this work that are NOT fixed and need their own change:

- **YouTube stable dedup is unwired.** `youtube_video_hash()` and `youtube_comment_hash()`
  exist in `services/social/anveshak/social/adapters/youtube_adapter.py` and have unit tests,
  but nothing in production calls either.
  The adapter set `_youtube_video_id` on the `RawItem` instead, an undeclared attribute nothing read,
  under a comment claiming it overrode `content_hash`.
  The dead assignments are gone; the feature is still missing.
  Effect: editing a video's captions changes its `raw_text`, so it re-ingests as a new content item.
  Fixing it needs a declared field on `RawItem` and a `content_hash()` that honours it, which changes
  the adapter SDK contract and what lands in the DB, so it was left out of a bug-fix pass.
- **`tests/migration/test_org_migration.py::test_default_org_shape` now skips on an unseeded DB.**
  The default org moved from migration 007's backfill to `scripts/seed_demo.sql`.
  The test was asserting a row the migration no longer promises.
  Decide whether the integration test DB should be seeded, and if so make the skip an assertion again.
- **29 orphaned ARQ jobs on the default `arq:queue`, dated 2026-07-10.**
  Every worker now declares an isolated `queue_name` (`arq:analyst`, `arq:vision`, `arq:social`, `arq:scraper`),
  and every `enqueue_job` call passes an explicit `_queue_name`, so nothing produces to or consumes from the default queue any more.
  The 29 jobs predate that isolation and will sit in Redis forever.
  They are idle and cost nothing, but they make `zcard arq:queue` misleading when diagnosing a backlog.
  Decide whether to purge them and whether a startup check should warn on a non-empty default queue.
- **Six integer env vars carry inline comments**, in `.env` and `.env.example`:
  `TRANSLATION_MAX_CHARS`, `EMBEDDING_DIMENSIONS`, `IDENTIFIER_CLUSTER_INTERVAL_S`.
  This is the pattern `.agents/skills/learned/references/dotenv-inline-comment-int-fields.md` warns about.
  It is not currently firing: Compose strips the trailing comment, and the container parses `TRANSLATION_MAX_CHARS` as `1500`, verified.
  It would still bite any tool that reads `.env` directly without comment stripping.

See [Outcome](#outcome) for what was done and why, including one deviation from Step 1.
See [Resolved work](#resolved-work) for how items 1 to 4 were closed, and
[Remaining work](#remaining-work) for what is left.

## Problem

The host `.venv` is stale and `make test-unit` cannot run.

```
$ make test-unit
error: Failed to spawn: `pytest`
  Caused by: No such file or directory (os error 2)
```

The repo moved from `/Users/navitas28/Work/anveshak` to `/Users/navitas28/Work/garud/anveshak`.
uv venvs are path-bound: the console scripts in `.venv/bin/` carry an absolute shebang to the interpreter.
92 of the 100 scripts in `.venv/bin/` still point at the old path, so every console-script entry point fails to spawn.

The failure is confined to console scripts.
`uv run python` resolves correctly, which is why `make setup` and `make syscheck` still work while `make test-unit` does not.
`uv sync` does not repair it, because uv considers the environment satisfied: all 264 packages are present, and it never rewrites shebangs.

Two contributing weaknesses make this worse than a one-off:

1. The venv's base interpreter is Anaconda (`home = /opt/anaconda3/bin`, `version_info = 3.12.7`), not a uv-managed CPython.
   That couples the workspace to whatever Anaconda happens to be on the machine.
2. There is no `.python-version`, so nothing pins the interpreter.
   Homebrew on this machine currently provides 3.14.6, and `requires-python = ">=3.12"` would happily accept it.

## Plan

### Step 1: Pin the interpreter first

Do this before deleting anything.
Without a pin, `uv sync` may select Homebrew 3.14, and the ML wheels (torch, spaCy, thinc, blis, scipy) are the most likely thing to have no 3.14 build.

```bash
uv python install 3.12
echo "3.12" > .python-version
```

Commit `.python-version`.
It belongs in version control so every machine and CI runner resolves the same interpreter.

### Step 2: Rebuild

```bash
rm -rf .venv
uv sync
```

The old venv is 2.0 GB.
The uv cache is warm at 410 MB, so most small wheels are local, but torch will likely re-download.
Budget 5 to 15 minutes.

### Step 3: Verify

```bash
uv run pytest --version          # must not say "Failed to spawn"
grep -rl "Work/anveshak" .venv/bin/ | wc -l   # must be 0
make test-unit
```

`make test-unit` should reach the test run.
Do not expect green: see the baseline below.

### Step 4: Guard against recurrence

Add a staleness check so the next path change surfaces as a clear message rather than "Failed to spawn".
Follow the existing `syscheck` and `agents-check` pattern in the Makefile.

The check: if `.venv/bin/python3`'s shebang or `.venv/pyvenv.cfg` does not resolve under the current repo root, print "venv was built for a different path, run: rm -rf .venv && uv sync" and exit non-zero.
Wire it as a prerequisite of the `test-*` targets, or call it from `syscheck`.

## Exit criteria

- `uv run pytest --version` succeeds
- `make test-unit` runs the suite and reports exactly the 18 known failures, no more
- The interpreter is pinned to 3.12 in version control (see [Outcome](#deviation-from-step-1-no-pythonversion), this landed as `requires-python`, not `.python-version`)
- A stale-venv guard exists and has been negative-tested by pointing it at a bad path

## Baseline: do not chase these during the rebuild

Captured 2026-08-20 by diffing a clean worktree at `8f8983f` against the working branch.
Both trees produce an identical set, so these predate all recent work and are not caused by the venv.

This section records the baseline as first observed.
All 19 failures have since been diagnosed - see [Resolved work item 3](#3-the-19-baseline-test-failures-all-fixed) for the causes and the fixes.
The segfault below did not reproduce after the rebuild.

18 unit failures:

- `tests/unit/test_org_multitenancy.py::TestMigration` (6 tests)
- `tests/unit/test_org_rls.py` (9 tests across `TestRLSEnabledOnTables`, `TestRLSMigrationExists`, `TestRLSPolicies`, `TestWorkerRole`)
- `tests/unit/test_phase3_resilience.py::TestFrontendExportButtons::test_content_feed_has_export`
- `tests/unit/test_provenance_api.py::TestGetClusterProvenance` (2 tests)

Plus one contract failure:

- `tests/contracts/test_service_contracts.py::TestEnqueueTargetsMatchWorkers::test_all_enqueue_calls_specify_queue`,
  reporting `analyst/anveshak/analyst/geocoding_backfill.py:148: enqueue_job('backfill_geocoding') missing _queue_name`

And one crash:

- Running `tests/unit/` and `tests/contracts/` in a single pytest process segfaults.
  Each directory passes when run alone.
  Reproduces on the base commit.
  Likely a native-extension conflict among the 183 loaded extension modules.
  Worth its own investigation; `make test-ci` runs both, so CI is affected.

Fixing any of these was correctly kept out of the venv rebuild.
They are now tracked as [Resolved work item 3](#3-the-19-baseline-test-failures-all-fixed).

## Outcome

All exit criteria met.
`make test-unit` now runs and reports exactly the documented baseline.

### Deviation from Step 1: no `.python-version`

The plan called for committing `.python-version` pinning 3.12.
That was tried and reverted, because `.python-version` is shared configuration between uv and pyenv, and this machine has pyenv installed.

pyenv resolves `.python-version` against its own installed versions and requires an exact version string.
Writing `3.12` made every pyenv shim fail inside the repo:

```
$ uv --version
pyenv: version `3.12' is not installed (set by .../anveshak/.python-version)
pyenv: uv: command not found
```

uv itself is a pyenv shim on this machine, installed as a pip package under pyenv 3.10.14, so the pin disabled the very tool it was meant to configure.
It also broke the bare `python3` calls in the Makefile health-count pipes, which are wrapped in `2>/dev/null || echo 0` and would have started silently reporting zero healthy containers.

The pin now lives in `requires-python` instead.
All seven workspace members moved from `">=3.12"` to `">=3.12,<3.13"`, which uv records in the lock as `requires-python = "==3.12.*"`.
This is equivalent determinism for uv and CI, collides with nothing, and is not machine-specific.

Side effect: the upper bound collapsed a dual resolution fork, so `uv.lock` dropped from 6389 to 4416 lines and `pydantic` consolidated from a 2.13.0/2.13.4 split to 2.13.4.
Docker is unaffected, since the images pin 3.12 through `FROM python:3.12-slim` and install with `UV_SYSTEM_PYTHON=1`.

Weakness 1 from the Problem section, the Anaconda base interpreter, is fixed regardless: the rebuilt venv reports
`home = /Users/navitas28/.local/share/uv/python/cpython-3.12-macos-aarch64-none/bin`.
The guard below asserts it stays 3.12, so drift fails loudly rather than silently.

### The guard

`make venv-check` in the Makefile, wired as a prerequisite of `test-unit`, `test-integration`, `test-e2e`, `test-full`, and `test-scrape`.
Silent on success, since it runs before every test target.

It checks five things, each negative-tested:

| Failure mode | Message |
| --- | --- |
| No `.venv` | `no .venv found, run: uv sync` |
| `.venv` present, dev deps missing | `.venv has no dev dependencies, run: uv sync` |
| Console script shebang outside `$(CURDIR)/.venv/` | `venv was built for a different path, run: rm -rf .venv && uv sync`, plus both paths |
| `pyvenv.cfg` base interpreter unreachable | `venv base interpreter is gone, run: rm -rf .venv && uv sync` |
| `pyvenv.cfg` version not 3.12 | `venv is Python X, this workspace requires 3.12, ...` |

The plan's phrasing, checking `.venv/bin/python3`'s shebang, does not work as written: `.venv/bin/python3` is a symlink to the base interpreter outside the repo and has no shebang.
The path check reads a console script's shebang instead, which is what actually broke.

### Baseline confirmed, with one correction

19 failures, matching the documented list exactly: the 18 unit failures plus the one contract failure.

The segfault did **not** reproduce.
`tests/unit/` and `tests/contracts/` ran together in a single pytest process and completed, 2361 passed.
The crash appears to have been an artifact of the stale Anaconda-based venv rather than a native-extension conflict.
`make test-ci` is therefore probably no longer affected, though that has not been re-run end to end.

### Adjacent fix: the quality targets were dead

Found while verifying, same "Failed to spawn" symptom class, so fixed here.

`UV := uv run`, but `lint`, `format`, `typecheck`, and `security-scan` all wrote `$(UV) run <tool>`, expanding to `uv run run ruff` and failing with `error: Failed to spawn: run`.
Five occurrences, all corrected to `$(UV) <tool>`.

That exposed a backlog accumulated while the targets were silently dead: 1334 ruff errors, 28 bandit findings, and no `pyright` in `dev-dependencies` at all.
`make lint`, `make format`, and `make security-scan` are now clean; `make typecheck` runs but still reports 174 errors.
Details below.

#### Lint: 1334 to 0

The bulk was mechanical: 434 import-sort and f-string fixes, 246 unused imports, then `ruff format` across 446 files, which alone took E501 from 516 to 164.
The codebase had never been formatted, because `make format` was broken by the same `uv run run` bug.

Three findings were real rather than cosmetic:

- `services/reporter/anveshak/reporter/main.py` annotated `_parse_labels(labels: Any)` without importing `Any`.
  Masked at runtime by `from __future__ import annotations`, but `typing.get_type_hints()` on that module would have raised.
- Six dead computations in service code, including `all_vectors` in `clustering.py`, which allocated `existing_centroid * existing_item_count` on every incremental cluster assignment and threw it away.
- `make lint` never looked at `sdk/anveshak/models/` or `sdk/anveshak/media/`.
  `.gitignore` blanket-excludes `models/` and `media/` for ML weights, and although the `!sdk/anveshak/models/` negations make git itself track those files, ruff's walker prunes the directory before it evaluates the negation.
  The SDK Pydantic models, where architectural rule 2 lives, were a lint blind spot.
  Fixed with `respect-gitignore = false`; that revealed 16 more errors, now fixed.

Two policy decisions are recorded in `pyproject.toml` next to the settings themselves:

- `E501` is disabled. Every one of the 164 survivors was inside a string literal - SQL DDL, the CSS in `reporter/pdf.py`, LLM prompt text, XML test fixtures.
  Rewrapping would have hurt readability or changed meaning, and in the fixture case would have changed `content_hash`.
  Ruff documents E501 as incompatible with its formatter.
- `E402` and `N806` have narrow per-file ignores where the pattern is deliberate: service entrypoints call `configure_logging()` before the remaining imports, and the demo generators use function-local UPPER_CASE constants.

Two source-scanning tests broke on the reformat and were rewritten to walk the AST instead of matching line text.
`test_service_contracts.py` claimed in its own docstring to handle multi-line calls but required `enqueue_job(` and the job name on one line; once the formatter split them it silently saw nothing, and reported `arq:social` as a queue nobody enqueues to.
The AST version also binds `_queue_name` to its own call rather than guessing from a nine-line window.

#### Security: 28 findings to 0

All ten medium-severity findings were false positives or documented deployment choices, each now carrying a justification comment and a bare `# nosec <ID>`:

- Three B608 in `api/db/identifiers.py` interpolate only `_ID_TYPES_SQL`, built from the hardcoded `IDENTIFIER_TYPES` tuple; every user value is a bind param.
- Two B104 bind `0.0.0.0`: one is a container metrics endpoint, the other is an SSRF blocklist entry that blocks the address rather than binding it.
- Two B108 set `HOME=/tmp` because crawl4ai and Playwright need a writable home.
- B310 uses a literal `https://github.com` prefix.
- Two B615 match the existing `clip_detector.py` precedent: models are pre-cached by an init container, with no runtime HuggingFace download in production.

Justifications were moved off the `# nosec` line and onto the line above.
Bandit parses everything after the test ID as further test IDs, which is where the `Test in comment: by is not a test name` warnings came from.

Note on placement: bandit associates `# nosec` with the line it reports, which for a multi-line SQL constant is the closing `"""`, not the assignment.
Putting the comment after the opening `f"""` puts it inside the SQL string, where `#` is not a PostgreSQL comment and the query would fail at runtime.

#### Typecheck: still failing, 174 errors

Actionable next steps are in [Resolved work item 1](#1-pyright-backlog-176-errors-to-0).

`pyright>=1.1` added to `dev-dependencies`, plus a `[tool.pyright]` block pinning `pythonVersion = "3.12"` so results are identical everywhere.
Two genuine bugs found and fixed:

- `analyst/nlp.py` annotated `_MODELS: dict[str, "spacy.Language"]` with a `# noqa: F821`, referring to a module never imported. Now a `TYPE_CHECKING` import of `spacy.language.Language`.
- `social/adapters/reddit.py` could reach `for post in posts` with `posts` bound to the *previous* feed's results, silently reprocessing the `new` feed as `hot`. Now initialised to `None` per feed with an explicit skip.

The remaining 174 are a real backlog, not configuration noise, and were deliberately not suppressed:

| Count | Cause |
| --- | --- |
| 45 | untyped third-party return values inferred as `Unknown` |
| 23 | asyncpg `PoolConnectionProxy` vs the `conn: asyncpg.Connection` annotation used in 171 places |
| 20 | attribute access on a value pyright cannot prove is non-`None` - the likeliest place for real bugs |
| 10 | optional dependencies genuinely absent from the host venv (aiokafka, optimum, yt_dlp, otlp exporter) |
| 76 | mixed |

Suggested order: the asyncpg group is one type alias and mechanical; the 20 Optional accesses deserve individual review; the `Unknown` group is mostly noise and should be judged last.


## Resolved work

Items 1 to 4 below were open as of 2026-08-20 and were closed on 2026-08-21.
Each entry records what the problem was and how it was resolved, so the reasoning survives.

Current state of the gates:

```bash
make venv-check     # passes
make lint           # passes
make typecheck      # passes, 0 errors
make security-scan  # passes
make verify-labels  # passes
make test-unit      # 2387 passed, 0 failed
make test-contract  # 37 passed
make test-frontend  # 378 passed across 36 files
```

### 1. Pyright backlog, 176 errors to 0

Every error was read individually rather than suppressed in bulk.
The breakdown by resolution:

**23 asyncpg errors, fixed by one type alias.**
`pool.acquire()` yields a `PoolConnectionProxy`, but 313 signatures annotated `conn: asyncpg.Connection`.
`DBConnection` now lives in `sdk/anveshak/db.py` as the union of the two, adopted across 48 files.
`services/AGENTS.md` was updated, since it documented the wrong annotation.

**31 Optional-access errors, each reviewed individually.**
These were the likeliest place for real bugs and several were:

- `services/vision/anveshak/vision/db/__init__.py` had no `get_or_create_stub_content_item`, but
  `jobs.py` imported one from `.db`. `POST /vision/youtube` without a `content_item_id` raised
  `ImportError` at runtime. The function now exists in the vision service's own db module.
- `insert_vision_result` annotated `deepfake_score: float` while its only caller documented
  "float or None on error". Now `Optional[float]`, matching rule 7.
- `require_client()` was added to the adapter base. Telegram, Reddit and YouTube reached collect paths
  assuming `authenticate()` had run; they now raise `AdapterAuthError` instead of
  `AttributeError: 'NoneType' object has no attribute 'iter_messages'`.
- The CLIP and YOLO detectors called `_load_model()` and then used the model without rechecking.
  An empty mounted model volume, the first-deploy state, produced an opaque `NoneType` error.
  Both now raise a message naming the model cache.
- `require_pool()` was added alongside `get_pool()` for routes that hand the pool straight to a
  repository function.

**12 org_id errors, a multi-tenancy correctness fix.**
Routes in assessments, provenance, signals, sources, topics and trackers passed
`get_user_org(user)`, typed `str | None`, into repository functions requiring `str`.
A token without an org silently returned an empty list, or attempted a NULL insert on a NOT NULL column.
All twelve now use `require_org_context(user)`, which raises 400.
Every one is on a non-super-admin path; the super-admin branches return earlier.

**2 Labels errors, one a live bug.**
`UpdateGeocodedLocationRequest.labels` was declared `Labels = {}`.
Pydantic does not validate defaults, so `.labels` was a plain `dict` whenever the caller omitted it.
Now `Field(default_factory=Labels)`.

**32 int-coercion errors in `api/db/system.py`**, all `int(await conn.fetchval(...))` over `COUNT(*)`.
Replaced with one `_count()` helper.

**The rest** were annotations that were simply wrong: `redis: object` in the analyst scheduler
(now `ArqRedis`), `broadcast: object` in signal delivery with a comment naming the real type
(now that type), `request: Request = None` on two topic routes where FastAPI always injects
(now a required param, which also removed two dead None guards), and `-> FileResponse` on a
route that returns a 202 `Response`.

**24 library-stub errors** remained after all of the above, and are genuinely not code defects.
They are suppressed per site with a `# pyright: ignore[rule]` and a reason on the line above,
matching the `# nosec` discipline used for bandit.
Two kinds: container-only dependencies correctly absent from the host venv
(aiokafka, optimum, yt_dlp, the OTLP exporter), and libraries whose stubs are wrong
(telethon, tweepy, atproto, PIL, cv2, transformers, onnxruntime).

Nothing is suppressed at the rule or file level, so a new error of any of these kinds still fails.

### 2. `make verify-labels`, resolved by narrowing rule 2

The verifier and `tests/unit/test_models_labels.py` disagreed: the test passed while the script failed
on `ExtractedEntity`.
The disagreement was resolved in favour of narrowing the rule, not adding the field.

`ExtractedEntity` is a nested value object.
It only ever exists as a list on `ContentItem.extracted_entities`, is never persisted or transmitted
alone, and has no constructor anywhere in the repo.
Duplicating `labels` onto it would let the two diverge: an entity marked OPEN inside a SECRET
`ContentItem`.

Rule 2 in `AGENTS.md` now states its scope, and `scripts/verify_labels.py` implements it through an
explicit `EXEMPT_MODELS` registry with a reason per entry.
The previous substring skip list (`"Create" in name`, and so on) was removed: it would have silently
exempted a model called `CreatorProfile`, which is exactly the gap rule 2 exists to close.
Only `Labels` itself and `ExtractedEntity` are exempt.

`TestLabelsVerifierAgreement` in `tests/unit/test_models_labels.py` now runs the real scanner, so the
two can no longer drift apart, and asserts every exemption carries a reason.

### 3. The 19 baseline test failures, all fixed

**1 real production bug.**
`services/analyst/anveshak/analyst/geocoding_backfill.py` enqueued its own continuation with no
`_queue_name`, so the job landed on ARQ's default `arq:queue`, which no worker listens on.
Geocoding backfill stopped silently after its first batch.
Now `_queue_name="arq:analyst"`, matching every sibling call.
A bare `except Exception: pass` in the same function now logs.

**15 migration-path failures.**
`test_org_multitenancy.py` and `test_org_rls.py` hardcoded `007_organizations.py` and
`008_rls_policies.py`, which were squashed into `001_initial_schema.py`.
Both now assert on migration *content* via `tests/helpers/migrations.py`, which concatenates the live
versions directory, so the next squash will not break them.

The RLS assertions were tightened while retargeting: against the concatenated migration set, the old
`assert "topics" in content` would have passed trivially.
They now assert `ALTER TABLE <t> ENABLE ROW LEVEL SECURITY` and a matching `CREATE POLICY` per table,
because enabling RLS without a policy denies every row.

The default-org assertion moved to the seed SQL, which is what creates it now that there is nothing to
backfill on a fresh schema.

**1 stale frontend test.**
`test_content_feed_has_export` globbed for `*ContentFeed*`, a component that no longer exists.
The feed now lives in the content view of `pages/TopicWorkspace.tsx`.
The test asserts on the export endpoint the button targets rather than on a filename.

**2 exhausted mocks.**
`get_cluster_provenance` gained a sixth concurrent query, `linked_tracker`, and the `side_effect` lists
supplied five. Both tests now supply the full sequence and assert on `linked_tracker`.

### 4. Three tests that never assert, assertions restored

- `test_trackers.py` now asserts the `DELETE` from `tracker_content_items` and the audit-log write,
  not just the exclusion insert, matching what its comment always claimed.
- `test_models_labels.py::test_generated_at_is_optional_initially` now checks the annotation really is
  `Optional[datetime]`. A bare `datetime` with `default=None` would have passed the old check while
  making the None sentinel unrepresentable under strict mode.
- `test_assessment_brief.py` now asserts on the `brief_md` that reaches the DB, not only on the
  in-memory brief the code mutated, so the hallucinated-ID stripping is verified where it matters.

None of the three surfaced a further failure.

## Remaining work

### 5. Verification not yet run

`make test-frontend` and `make test-contract` have since been run and pass.
Still unrun, both needing containers:

- `make test-integration` - needs `make up`
- `make test-ci` - runs unit, contract, integration, frontend, and the 80 percent coverage gate
- `make test-scrape` - needs internet

`make test-ci` is the one that matters, since the segfault that used to break it did not reproduce and
that should be confirmed end to end rather than inferred.

Note that `make test-contract` did not exist when this document was written, despite `AGENTS.md`
listing it in the development workflow. The target was added.

### 6. Commit the branch

Nothing is committed.
The working tree holds the venv work, the quality-target fixes, the 446-file reformat, the pyright
backlog, and the test fixes, on top of the pre-existing harness-agnostic-agents changes.

Consider splitting the commits, because a single commit mixing a repo-wide reformat with substantive
fixes is close to unreviewable:

1. Python pin, `venv-check` guard, the `uv run run` Makefile fix, and the new `test-contract` target
2. `ruff format` across `services/`, `sdk/`, `tests/`, `scripts/`, formatting only
3. Lint fixes with behaviour implications: the missing `Any` import, the dead computations, the AST
   rewrites of the two source-scanning tests
4. Bandit justifications and `respect-gitignore = false`
5. `pyright` dependency and config, plus the type bugs it caught
6. The baseline test fixes, including the `arq:analyst` queue fix
7. Rule 2 scope narrowing and the `verify_labels.py` exemption registry

Committing also clears the `git stash` symptom described at the end of this document.

## Risk register

| Risk | Mitigation |
| --- | --- |
| `uv sync` picks Homebrew 3.14 and ML wheels fail to build | Step 1 pins 3.12 before the venv is deleted |
| Deleting the 2.0 GB venv on a slow connection leaves no working env | uv cache is warm at 410 MB; run during a window where a 15 minute rebuild is acceptable |
| Anaconda reappears as the base interpreter | `uv python install 3.12` provisions a uv-managed CPython, and `.python-version` keeps selection deterministic |
| spaCy models missing after rebuild | None are installed in the host venv today, and only `spacy>=3.7` is declared in `services/analyst/pyproject.toml`. Models load inside containers, so the host venv does not need them. |

## Separate note: git stash is not broken

While the `chore/harness-agnostic-agents` branch is uncommitted, this fails:

```
$ git stash -u
fatal: Unable to process path .claude/skills/adapter-patterns/SKILL.md
Cannot save the current worktree state
```

This is not a defect and needs no fix.
HEAD holds `.claude/skills/adapter-patterns/SKILL.md` as a regular file, while the index and worktree hold `.claude/skills/adapter-patterns` as a symlink.
Stashing would have to restore the HEAD file by writing through that symlink, and git refuses to write through symlinks as a matter of policy.

Committing the type change resolves it.
Verified with a minimal reproduction: stash fails while the file-to-symlink change is uncommitted, and succeeds immediately after committing, with `stash pop` restoring content correctly.

So: commit the branch, and the symptom is gone.
Nothing to carry into the rebuild work.
