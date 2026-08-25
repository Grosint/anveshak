# Host venv Rebuild, Python Pinning, and the Quality-Target Backlog

Written 2026-08-20, alongside the `chore/harness-agnostic-agents` branch.
Last updated 2026-08-21, after a fourth session that added items 10 and 11: it closed the three
findings item 9 left open, and ran the two gates that had never been run, `make test-integration`
in full and `make test-scrape`.

The original scope was the venv rebuild.
Verifying it uncovered that four Makefile quality targets had been silently dead, so this document
now also tracks the backlog that exposed.

Items 1 to 8 are committed on `chore/harness-agnostic-agents` as the single commit `694de76`.
The ten-way split suggested under item 6 was not used, so that one commit mixes a 446-file reformat
with substantive fixes; worth knowing before bisecting anything in this range.
Items 9, 10 and 11 are in the working tree on top of it, uncommitted.

## Status at a glance

Done:

- [x] Interpreter pinned to 3.12, in version control
- [x] `.venv` rebuilt on a uv-managed CPython, off Anaconda
- [x] `make venv-check` guard, wired into every test target, all five failure modes negative-tested
- [x] `make lint` clean, 1334 errors to 0
- [x] `make format` clean and stable, 473 files
- [x] `make security-scan` clean, 28 findings to 0
- [x] `pyright` installed and configured, so `make typecheck` runs at all
- [x] Unit and contract suites no longer segfault when run in one process
- [x] [1. Pyright backlog](#1-pyright-backlog-176-errors-to-0) - 176 errors to 0, `make typecheck` passes
- [x] [2. `make verify-labels`](#2-make-verify-labels-resolved-by-narrowing-rule-2) - rule 2 scope resolved, passes
- [x] [3. The 19 baseline test failures](#3-the-19-baseline-test-failures-all-fixed) - all fixed
- [x] [4. Three tests that never assert](#4-three-tests-that-never-assert-assertions-restored) - assertions restored
- [x] `make test-frontend` - 378 tests across 36 files, all passing
- [x] `make test-contract` - target added, it was documented but did not exist
- [x] [5. Integration suite, host-side](#5-verification-integration-now-passes) - 6 failures to 0, 128 passing
- [x] [7. Runtime saturation](#7-runtime-saturation-the-analyst-worker-hang) - the analyst worker hang and the scraper OOM loop
- [x] [8. `scam_templates` never seeded](#8-built-in-scam-templates-were-never-seeded-on-a-fresh-database) - production bug, Engine C matched nothing on a fresh database
- [x] [9. Env forwarding, healthchecks, and worker logging](#9-env-forwarding-healthchecks-and-worker-logging) - 20 unforwarded or dead env vars, 6 healthchecks that proved nothing, 4 workers logging without a service field
- [x] All four findings recorded on 2026-08-20 are closed; see [Closed findings](#closed-findings)
- [x] [10. The three findings item 9 left open](#10-the-three-findings-item-9-left-open) - NULL
      centroids repaired, both schedulers given a real heartbeat, the analyst backlog measured
- [x] [11. `make test-scrape`](#11-make-test-scrape-item-d) - run with internet, item D; 20 of 22
      pass with 1 skip, and three reporting defects in the harness are fixed

Open, in suggested order:

- [ ] [A. Commit items 9, 10 and 11](#6-commit-the-branch) - suggested 6-way split at item 6
- [ ] [B. `make test-integration` end to end](#5-verification-integration-now-passes) - run in full; steps 1 to 3 pass, steps 4 and 5 need a stack that is not competing for memory and CPU
- [ ] [C. `make test-ci`](#5-verification-integration-now-passes) - the gate that matters, never run end to end

Gate status as of the end of the 2026-08-21 sessions:

```bash
make venv-check     # passes
make lint           # passes
make typecheck      # passes, 0 errors
make security-scan  # passes
make verify-labels  # passes
make verify-env     # passes, 84 of 84 forwarded   <- new in item 9
make test-unit      # 2425 passed, 0 failed   <- +21 in item 10
make test-contract  # 46 passed               <- +5 in item 10
make test-frontend  # 378 passed across 36 files -- carried from the item 5 session,
                    # not re-run for items 9 or 10, neither of which touched frontend code
make test-integration  # run in full, item B. Steps 1-3 green: 128 passed, 4/4, 5/5.
                       # Step 4 2/4 and step 5 unfinished, both starved of memory
                       # and CPU by the running stack, not by a code defect.
make test-ci        # NEVER RUN, item C. Contains test-integration, so it inherits
                    # the constraint above.
make test-scrape    # run, item D. 20/22 passed, 2 failed, 1 skipped. The two failures
                    # are one unreachable onion and an X keyword search that returns
                    # nothing on this API tier. Duration swings from 5 to 23 minutes.
```

Everything above except `test-frontend` was re-run at the end of the item 10 session.

## Open findings

The three recorded while doing item 9 are closed; see
[item 10](#10-the-three-findings-item-9-left-open) for how.
Running item B in full raised two more, both about this host rather than the code.

- **Ollama cannot load its model while the full stack runs.** The Docker VM has 11.9 GB, the stack
  holds about 10.2 GB of it, and `qwen2:7b` at 8192 context with `OLLAMA_NUM_PARALLEL=2` is
  OOM-killed: `OOMKilled: true`, and the API returns
  `HTTP 500: llama-server process has terminated: signal: killed`.
  With three workers stopped the same test passes 4/4. This gates integration step 4 and therefore
  `make test-ci`. See [item 5](#5-verification-integration-now-passes) for the three options.
- **LLM jobs starve the analyst worker's job slots.** After a restart with the queue at 555, all
  four `max_jobs` slots were held by `generate_cluster_label`, each waiting on Ollama and failing
  at its 300s timeout, while the worker sat at 0.88 percent CPU and completed 4 jobs in ten
  minutes. `analyse_content` cannot progress behind them.
  This is the fuller answer to the item 9 backlog finding: depth is a symptom, and the cause is
  that CPU-bound ML jobs and LLM-bound label jobs share one queue and one slot budget.
  Fixing it is a design decision, either a separate queue and worker for LLM jobs or a circuit
  breaker on label generation, so it is recorded rather than patched.

## Closed findings

The four recorded on 2026-08-20 and the three recorded on 2026-08-21, all now closed.

- ~~**40 of 275 active narrative clusters have a NULL `embedding_centroid`.**~~ Fixed by item 10.
  `run_clustering` now repairs what it can before loading centroids: 7 of the 40 hold member
  embeddings and get an `l2_normalize(AVG(embedding))` centroid, the same value the write path
  computes. The other 33 are seed clusters with no member embeddings, which nothing can rebuild
  from; they are now reported once per cycle as `clustering.centroid_missing` with a count, rather
  than 33 `clustering.bad_centroid` lines that read like corruption.
- ~~**The analyst queue is deeply backed up.**~~ Measured. Depth alone is not the defect:
  `arq:analyst` drained from 944 to 328 in about eight minutes with jobs taking 0.4s to 0.9s, and
  refills as fast as the scrapers feed it. The real constraint turned up later in the same session
  and is recorded above under [Open findings](#open-findings): `generate_cluster_label` holds all
  four job slots waiting on Ollama. This entry is closed only in the sense that it is no longer the
  right question to ask.
- ~~**The two schedulers still use `kill -0 1`.**~~ Fixed by item 10. Both now write
  `anveshak:scheduler:<name>:health-check` from `sdk/anveshak/heartbeat.py`, refreshed every 30s
  while they sleep between 900s cycles, and both compose healthchecks read it through the existing
  `sdk/arq_health.sh`. A contract test fails if `kill -0 1` reappears on any service.

- ~~**29 orphaned ARQ jobs on the default `arq:queue`.**~~ Purged 2026-08-21.
  All 29 dated 2026-07-10, and by the time they were deleted every matching `arq:job:<id>` payload
  had already expired: the sorted set held 29 dangling ids pointing at nothing, so even a worker
  consuming the default queue would have found no definition to run. `zcard arq:queue` went 29 to 0
  and the five isolated queues were untouched. The member list was dumped to
  `/tmp/anveshak-arq-purge/` first, which is throwaway insurance rather than a real backup.
  No startup check was added, because nothing can repopulate the queue: two contract tests already
  cover both routes onto it. `test_all_enqueue_calls_specify_queue` catches an *omitted*
  `_queue_name`, which is how these 29 arrived and how the item 3 geocoding-backfill bug arrived,
  and `test_no_default_queue_usage` catches an explicit `arq:queue`.
- ~~**YouTube stable dedup is unwired.**~~ `RawItem.stable_id` is a declared field,
  `RawItem.content_hash()` keys on `{platform}:{stable_id}` when it is set, and the adapter sets
  `video:{video_id}` and `comment:{comment_id}`. This is the narrow rule 3 exception, and
  `tests/unit/test_social_conformance.py::TestStableId` pins it.
  Closed before the 2026-08-21 session that went looking for it; the entry above was simply stale.
- ~~**`test_default_org_shape` skips on an unseeded DB.**~~ Closed by moving the assertion rather
  than seeding the DB. `tests/migration/test_org_migration.py` is now schema-only and says so in
  its docstring; the default org is asserted against the seed SQL itself in
  `tests/unit/test_org_multitenancy.py::TestSeedDefaultOrg`, over both seed files.
- ~~**Six integer env vars carry inline comments.**~~ Closed, and it was 12 rather than 6.
  The original count missed float fields, which pydantic coerces the same way and which fail the
  same way. Chasing it is what turned up the 20 unforwarded variables in item 9.

See [Outcome](#outcome) for what was done and why, including one deviation from Step 1.
See [Resolved work](#resolved-work) for how items 1 to 4 and 7 to 9 were closed, and
[Remaining work](#remaining-work) for what is left.

## Next session: start here

Items 9, 10 and 11 are uncommitted on `chore/harness-agnostic-agents`; items 1 to 8 are in `694de76`.

Do this first:

1. Commit items 9, 10 and 11, using the 6-way split under [item 6](#6-commit-the-branch).
   Doing this before the long test runs means a failure has something to bisect against.
2. `make test-integration` and read all five steps. Only step 1 has been confirmed green.
3. `make test-ci`, the gate that actually matters and has never been run end to end.

Environment state left behind by the 2026-08-21 sessions, so nothing here is a surprise:

- **The local stack is already rebuilt and running items 9 and 10.** All six service images were
  rebuilt during item 9 and the stack recreated; `anveshak-scraper`, `anveshak-social` and
  `anveshak-analyst` were rebuilt again for item 10, and the three affected containers recreated.
  A *fresh clone* still needs `make build`, because compose calls
  `bash /workspace/sdk/arq_health.sh`, which an older image does not contain, and an unrebuilt
  worker or scheduler will report unhealthy immediately.
- `anveshak_test` was dropped and recreated from zero to pick up the restored `scam_templates` seed.
  This is the correct way to verify a migration seed and is safe to repeat.
- The analyst queue is being fed as fast as it drains, so its depth oscillates; the worker's own
  counters in `arq:analyst:health-check` are the signal, not `zcard arq:analyst`. Long test steps
  that run inside `analyse-worker` compete with that backlog for CPU.
- Triage command for a worker that looks busy but is wedged:

  ```bash
  docker exec anveshak-redis-1 redis-cli get arq:analyst:health-check
  ```

  If the timestamp in that value is not advancing while the container burns CPU, the worker is
  wedged, not working. Compare against `arq:vision:health-check` and `arq:reporter:health-check`.
  As of item 9 the container healthcheck reads exactly this key, so `docker ps` reflects it without
  the manual check.
- The same check for the two schedulers, which are not ARQ workers and write their own key:

  ```bash
  docker exec anveshak-redis-1 redis-cli get anveshak:scheduler:scrape-web:health-check
  docker exec anveshak-redis-1 redis-cli get anveshak:scheduler:scrape-social:health-check
  ```

  These carry a TTL of 120s and are refreshed every 30s, so a value older than about two minutes,
  or an absent key, means the loop has stopped. See item 10.

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
- The interpreter is pinned to 3.12 in version control (see [Outcome](#deviation-from-step-1-no-python-version), this landed as `requires-python`, not `.python-version`)
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
Items 7 and 8 were found and closed later on 2026-08-21, in the session that first ran the
integration suite against a live stack.
Item 9 came out of a third session on 2026-08-21, which set out to close the last of the
2026-08-20 findings and found a larger version of the same problem behind it.
Each entry records what the problem was and how it was resolved, so the reasoning survives.

Numbering is stable and used as a cross-reference, so these are not in chronological order.
Item 5 is partly done and item 6 is done without its split; both live under
[Remaining work](#remaining-work).

Gate status is recorded once, under [Status at a glance](#status-at-a-glance), rather than
repeated here where it would drift.

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

### 7. Runtime saturation: the analyst worker hang

Symptom that started this: `make test-integration` was unusable because the machine was pinned,
with Docker reporting roughly 1500 percent CPU across a 12-core VM before pytest was even started.

The analyst worker was not busy, it was **hung**.
It sat at 617 to 910 percent CPU with no log output for 40 minutes, while its ARQ health key
(`arq:analyst:health-check`) stopped advancing and `arq:vision` and `arq:reporter` kept heartbeating normally.

Four bugs stacked to produce it:

1. **Blocking torch inference on the async event loop.**
   `translate_to_english` in `services/analyst/anveshak/analyst/translation.py` is a plain `def`
   wrapping a synchronous NLLB `pipeline()` call, and `analyse_content` awaited nothing around it.
   That froze the entire worker event loop, not just the one job.
   Fixed with `await asyncio.to_thread(...)` at `services/analyst/anveshak/analyst/jobs.py:207`.
   Note that spaCy NER and the embedding encoder in the same job are still called synchronously.
   They currently run in about 3 seconds so they have not caused a visible stall, but they sit on the same event loop
   and are the next candidates if this recurs.
2. **`job_timeout` could not fire.**
   `WorkerSettings.job_timeout = 300` is enforced with `asyncio.wait_for`, which needs the loop to tick.
   Bug 1 froze the loop, so the timer never ran and a job with a 300 second limit ran for 29 minutes.
   Resolved by bug 1, and confirmed working independently: `generate_cluster_label` in the same log
   was correctly killed at `300.01s`.
3. **A character budget guarding a token limit.**
   `translation_max_chars = 1500` truncates characters, but NLLB's constraint is 512 positions.
   Devanagari tokenises at roughly 3 characters per token, so 1500 Hindi characters produced 514 tokens
   and the log showed `Your input_length: 514 is bigger than 0.9 * max_length: 512`.
   Overrunning the position limit does not raise, generation simply never terminates.
   `truncation=True` was also never passed, so the tokenizer did not clamp either.
   Fixed by clamping on tokens through the pipeline tokenizer before inference, and passing
   `truncation=True` plus an explicit `max_length`.
   New setting `translation_max_input_tokens`, default 480, deliberately below the model limit.
4. **Thread oversubscription.**
   Inside the container `torch.get_num_threads()` was 12 on a 12-core host, with `OMP_NUM_THREADS` unset,
   and `WorkerSettings.max_jobs = 4`, so up to 48 threads contended for 12 cores.
   Fixed with `torch.set_num_threads(settings.torch_num_threads)` at pipeline construction,
   new setting `torch_num_threads`, default 2, per rule 6 read from env rather than hardcoded.

**No CPU limit existed anywhere.** `grep "cpus:" infra/compose.yml` returned nothing before this change.
Only `mem_limit` was set, so a runaway service could take the whole host.
Added `cpus:` to the two heavy consumers, via `ANALYST_WORKER_CPUS` and `SCRAPER_WORKER_CPUS`.

Note that `docker update --cpus` on a running container did not take effect on Docker Desktop:
`NanoCpus` was set on the container but observed CPU stayed at 647 percent.
The limit only applied after the container was recreated.

#### The scraper OOM restart loop

Separate cause, same symptom.
`scrape-web-worker` had `mem_limit: 1g` while `SCRAPER_CONCURRENCY` defaulted to 4,
and each concurrency slot is a Playwright Chromium at roughly 350 to 450 MB.
`docker inspect` showed `RestartCount=8, OOMKilled=true`.
Every restart re-crawled the same queue, so it burned 418 percent CPU indefinitely while making no progress.

Raised to `mem_limit: ${SCRAPER_MEM_LIMIT:-3g}` with `cpus: ${SCRAPER_WORKER_CPUS:-3}`.
Note `.env` pins `SCRAPER_CONCURRENCY=4`, which overrides the Compose default of 2.
At 3g that is fine, roughly 1.8 GB of browsers against a 3 GB limit, but the two numbers are coupled
and `.env.example` now says so.

#### The healthcheck that hid it

`analyse-worker` used `test: ["CMD-SHELL", "kill -0 1 || exit 1"]`.
That only proves PID 1 exists, which says nothing about whether the event loop is alive,
so a fully wedged worker reported `healthy` for 40 minutes.
ARQ already writes a liveness key to Redis, but `health_check_interval` defaults to 3600 seconds,
so even a key-based check would have taken an hour to notice.
Set `health_check_interval = 30` in the analyst `WorkerSettings`.

The container healthcheck itself is still `kill -0 1` and should be switched to read
`arq:analyst:health-check` before this is considered closed.

#### Result

The stack idles at about 15 percent total CPU, down from roughly 1500 percent.
Under load the web scraper sits at its 300 percent cap with 2.3 GB of its 3 GB limit and no OOM kills,
and the analyst worker runs near 100 percent against a 400 percent cap.

### 8. Built-in scam templates were never seeded on a fresh database

This is a production bug that an integration test happened to expose, not a test bug.

`tests/integration/test_engine_c_pipeline.py::TestTemplateSignalsToDB::test_template_match_signal_fired`
failed with `assert 0 >= 1`, because `scam_templates` was empty in the test database while the dev database had 11 rows.

The 11 built-in templates were seeded by migration `009_engine_c.py` and amended by `013_phone_intl.py`,
which adds `PHONE_INTL` to four of them.
Both migrations have since been archived into `services/api/migrations/archive/`.
The squashed baseline `001_initial_schema.py` creates the `scam_templates` table but never seeded it.

The dev database only has the rows because it was migrated before the squash.
Any fresh deployment gets an empty table.
`SQL_BREACHING_TEMPLATE_MATCHES` in `services/analyst/anveshak/analyst/template_signals.py`
inner-joins `scam_templates`, so an empty table silently yields zero signals with no error:
Engine C template matching would appear to work and detect nothing.

Fixed by moving the seed into `001_initial_schema.py`, kept verbatim from 009 plus the 013 `UPDATE`
rather than hand-merged, so the final state provably matches an already-migrated database.
The seed ends in `ON CONFLICT (id) DO NOTHING` and is therefore idempotent.

Verified by dropping `anveshak_test` entirely and re-running `make migrate-test` from zero:
11 templates, 4 carrying `PHONE_INTL`, matching the dev database exactly.

Worth checking whether any other data seeded by an archived migration was lost in the same squash.
This one was found by accident.

Remember that migration files are COPYed into images rather than volume-mounted, so a host edit is
invisible to a running container and `alembic upgrade head` will silently do nothing.
The `anveshak-api` image was rebuilt; a `docker cp` was used first to verify.
See `.agents/skills/learned/references/migration-not-visible-in-container.md`.

### 9. Env forwarding, healthchecks, and worker logging

Started as the last of the four 2026-08-20 findings, the inline comments on integer env vars.
Checking it turned up three larger problems behind it, all of the same shape: something is
declared, looks configured, and does nothing.

#### The inline comments, 12 sites not 6

The original count only looked at integer fields.
Floats coerce through the same pydantic path and fail the same way, so
`CREDIBILITY_DEEPFAKE_DROP`, `CREDIBILITY_MIN_AUTO_DROP` and `OTEL_TRACES_SAMPLER_ARG` were
affected too, in both `.env` and `.env.example`.
Every comment moved to the line above its variable.
`tests/unit/test_env_forwarding.py::TestNoInlineCommentsOnNumericEnvVars` now fails on a new one,
matching numbers with an optional decimal part rather than integers only.

#### 20 of 87 `.env.example` variables never reached a container

This is the real finding.
`grep` for each `.env.example` variable in `infra/compose.yml` returned nothing for 20 of them.

Seventeen were live settings, read by a service that never received them, so each one ran on its
code default while `.env` looked authoritative:

- All eight `CREDIBILITY_*` knobs. Nothing in compose mentioned credibility at all.
- `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS`, the documented `hardware.md` upgrade path.
  `analyse-init` pre-caches the embedding model and `analyse-worker` loads it, so setting
  `EMBEDDING_MODEL` for a GPU upgrade would have silently kept `all-MiniLM-L6-v2` in both.
- `JWT_EXPIRE_MINUTES`, `SIGNAL_WEBHOOK_ENABLED`, `ANVESHAK_DRISHTI_BRIDGE`,
  `INSTAGRAM_HOURLY_CALL_CAP`, and the three `OTEL_*` variables.

`SIGNAL_WEBHOOK_URL` and `DRISHTI_REDPANDA_BOOTSTRAP` were commented out in `.env.example` and
also absent from compose, so enabling either feature would have failed at the second step.
Both are now forwarded with empty defaults.

Three were genuinely dead and were deleted from `.env` and `.env.example`:
`HDBSCAN_MIN_CLUSTER_SIZE` and `HDBSCAN_MIN_SAMPLES`, left over from before Leiden replaced
HDBSCAN, and `ARQ_KEEP_RESULT_S`, which four `WorkerSettings` classes hardcode as
`keep_result = 3600`. The env value happened to match the constant, which is why nobody noticed.

`credibility_update_interval_s` was removed from `services/analyst/anveshak/analyst/settings.py`
for the same reason: the credibility job is an `arq.cron(..., hour={3})`, so the interval setting
had no reader in either direction.

**One latent bug, nearly activated by the fix.** `.env` carried
`CREDIBILITY_MIN_AUTO_DROP=10.0` while `.env.example` and the code default both say `1.0`.
With `CREDIBILITY_DEEPFAKE_DROP=1.0` and `CREDIBILITY_CONTRADICTION_DROP=5.0`, a noise floor of
10.0 discards every credibility drop the system can produce, and rule 8 then writes no audit row
at all. It had been harmless only because compose never forwarded it.
Forwarding it as written would have shipped the bug.
Corrected to `1.0` in `.env`, with the invariant stated in a comment beside it.

`tests/unit/test_credibility_settings.py` did not catch this, and still cannot: it instantiates
`AnalystSettings()`, which reads code defaults, and no settings class in this repo sets
`env_file`. It tests the defaults, not the deployment.

**The guard.** `scripts/verify_env_forwarding.py`, wired as `make verify-env` and as
`tests/unit/test_env_forwarding.py` so the gate and the test share one scanner.
It walks `.env.example`, `infra/compose.yml`, and every `BaseSettings` subclass plus every
`os.getenv` call under `services/` and `sdk/`, then splits the failures by required fix:

| Class | Meaning | Fix |
| --- | --- | --- |
| UNFORWARDED | a service reads it, compose never passes it | add to that service's `environment:` block |
| DEAD | nothing under `services/` or `sdk/` reads it | delete from `.env` and `.env.example` |

`EXEMPT_VARS` denies by default and each entry carries a reason, matching the registry style
`scripts/verify_labels.py` uses for rule 2. Two entries today, both host-only.

#### The healthchecks proved nothing, and one was self-defeating

`scrape-web-worker` was sitting at `unhealthy` with a failing streak of 9.
Its healthcheck was `python -c 'import arq; import anveshak.scraper.jobs'`, which imports the
whole job graph and with it crawl4ai and Playwright. Timed inside the running container:

```
$ time docker exec anveshak-scrape-web-worker-1 python -c 'import arq; import anveshak.scraper.jobs'
17.935 total
```

against a 10s timeout. The container was marked unhealthy purely by the cost of its own
healthcheck. `docker exec` is scheduled inside the container's own CPU quota, so a worker at its
`cpus:` cap starves its own probe; even `python -c 'import redis'` measured 6.5s under load.

The other four ARQ workers used `kill -0 1`, which only proves PID 1 exists.
That is the check that reported `healthy` for 40 minutes during the item 7 hang.

This also means `scrape-web-worker` had been sitting at `unhealthy` for some time with nothing
actually wrong with the worker, which is the worse failure: a health signal nobody can trust gets
ignored, including on the day it is right.

All five now use `bash /workspace/sdk/arq_health.sh arq:<queue>`.
ARQ writes its health key with `psetex(key, (health_check_interval + 1) * 1000)`, so the key
exists only if the worker's event loop ticked within the interval.
Presence of the key is the liveness signal, and a frozen event loop cannot fake it.
No timestamp parsing needed.

The probe is shell rather than Python on purpose, and the first attempt got this wrong.
A Python module reading the same key was written first and measured **15.9s** inside the running
scraper at its CPU cap, against the 20s timeout it had been given: better than 17.9s, but only
just, and on an already-pathological container. `docker exec` is scheduled inside the container's
own CPU quota, so the probe competes with the work it is measuring, and no interpreter-based
check is safe there. The same check in bash, over `/dev/tcp` and Redis's inline command protocol,
measured **1.2s**, most of which is `docker exec` overhead rather than the probe. The Python
version was deleted; one implementation, and it is the cheap one.
The timeout went back to 10s, which is now ample.

`sdk/arq_health.sh` sits next to the package rather than inside it, so the existing
`COPY sdk/ /workspace/sdk/` in every service Dockerfile ships it with no Dockerfile change.
All four exit paths were negative-tested inside a live container: healthy, absent key,
unreachable Redis, and a usage error.

One bug worth recording, because it was silent. The first version wrote
`exec 3<>/dev/tcp/host/port 2>/dev/null` to suppress bash's resolver noise. `exec` with no command
redirects the *current shell*, so that permanently pointed the script's stderr at `/dev/null` and
every later error message vanished while the exit codes stayed correct: a healthcheck that fails
without saying why. It is now `{ exec 3<>...; } 2>/dev/null`, and the reason is in a comment above
the line.

`health_check_interval = 30` was set on the four `WorkerSettings` that lacked it; only the analyst
had it. ARQ's default is 3600, so the key would have survived an hour past death and the check
would have been decorative.

The two schedulers keep `kill -0 1`; they are not ARQ workers and have no health key. Both expose
a Prometheus port that would make a better check, and that is left open.

**A third broken healthcheck, same family.** `whatsapp-bridge` had been `unhealthy` on a
`wget -q --spider http://localhost:3002/health` probe. The `node:*-slim` base ships neither wget
nor curl, so the probe exited 127 on every run and the container was permanently unhealthy while
`/health` was in fact returning 200. It now uses `node -e` with the built-in `http` module, which
is the one HTTP client the image is guaranteed to have.

**Verified against a live stack, not just reasoned about.** After rebuilding all six images and
recreating the stack, all 21 containers that declare a healthcheck report healthy, including
`scrape-web-worker`, which had been unhealthy with a failing streak of 9.

The detection path was then tested directly. `docker exec ... kill -STOP 1` does nothing, because
the kernel drops default-action signals sent to a PID namespace's own PID 1, so the frozen-worker
case was reproduced instead by holding `arq:analyst:health-check` deleted while the worker kept
running. That is precisely the state a blocked event loop produces: process alive, key not
refreshed. `docker inspect` walked the streak up and flipped the container at the third
consecutive failure:

```
t+15s: healthy   streak=0
t+30s: healthy   streak=1
t+60s: healthy   streak=2
t+90s: unhealthy streak=3
```

It returned to healthy on its own once the key was left alone. Under `kill -0 1` this same
condition reported healthy indefinitely.

`tests/contracts/test_service_contracts.py::TestWorkerHealthchecks` pins all of it: every
`WorkerSettings.queue_name` has a matching healthcheck, every worker sets a short
`health_check_interval`, and no healthcheck goes back to an import probe. That last test scans
only healthcheck `test:` lines, having first been written loosely enough to match the explanatory
comment beside them.

#### Four ARQ workers never configured logging

`configure_logging()` was called by the six FastAPI and scheduler entrypoints and by
`reporter/worker.py`, but not by `analyst`, `scraper`, `social` or `vision` `jobs.py`.
`arq anveshak.analyst.jobs.WorkerSettings` starts its own process and imports only that module,
so those four ran with unconfigured structlog. Side by side in the same stack:

```
report-worker    ... [info] cron:check_scheduled_reports  service=reporter environment=development
analyse-worker   03:07:36: 1505.99s → ...:analyse_content('f08db666-...') delayed=1505.99s
```

No `service` field, so Loki could not attribute the busiest workers in the system.
All four now call `configure_logging()` and `configure_tracing()` at module level, matching the
`reporter/worker.py` precedent, with the matching `E402` per-file ignores added to `pyproject.toml`
next to the existing entrypoint ignores.

#### `configure_tracing()` had no callers at all

`sdk/anveshak/tracing.py` is a complete OpenTelemetry setup, `infra/compose.yml` runs a `jaeger`
service, and `.env.example` documents three `OTEL_*` variables. Nothing called
`configure_tracing()` anywhere in the tree, so none of it had ever run.

It is now called by all ten entrypoints. The function is a no-op unless `OTEL_ENABLED=true`,
and it previously returned silently in that case; it now logs `tracing.disabled` with the reason,
per the silent-failure rule. The three `OTEL_*` variables are forwarded through `x-common-env`.

#### Typecheck was not at zero

`make typecheck` reported 6 errors in `services/analyst/anveshak/analyst/translation.py`, all in
the token-clamping block added by item 7. Item 7 landed after typecheck was declared clean and
the gate was never re-run.

One was worth fixing rather than suppressing: `pipe.tokenizer` is `Optional`, and the clamp is the
only thing standing between a dense-script input and the non-terminating generation that caused
the item 7 hang. It now fails closed, logging `translation.no_tokenizer` and returning `None`,
because translating without the clamp is worse than not translating.
The rest are wrong transformers stubs (`Encoding` declares neither `__len__` nor `__getitem__`
while the runtime object is a dict) and carry a per-site `# pyright: ignore` with the reason above
it, matching the discipline used for bandit.

#### Gates after this item

All green; the numbers live under [Status at a glance](#status-at-a-glance).
`make test-integration` and `make test-ci` were **not** run in this session, so items B, C and D
are unchanged.

Also cleaned up while here: five unit test modules declared
`pytestmark = [pytest.mark.unit, pytest.mark.asyncio]`, which applies the asyncio marker to their
sync tests too and emits a `PytestWarning` per test. `asyncio_mode = "auto"` already marks the
async ones. This is the same fix item 5 applied to `test_db_isolation.py`; the suite now runs with
zero such warnings.

### 10. The three findings item 9 left open

Two were defects and are fixed.
The third was measured and closed as throughput rather than a defect.

#### 40 active clusters could never be matched incrementally

`SQL_CLUSTER_CENTROIDS` selects `embedding_centroid::text`, which is `None` for a cluster whose
centroid was never computed.
`_parse_pgvector(None)` then raised inside the per-row `try` in `load_cluster_centroids`, the row
was dropped, and the cycle logged `clustering.bad_centroid`.
The effect was that `assign_to_nearest_cluster` never saw those clusters, so new content could
only reach them through a full re-cluster, and the log line described data corruption when the
real state was an absent value.

Two changes, both in `services/analyst/anveshak/analyst/clustering.py`:

- `backfill_missing_centroids()` recomputes the centroid from the cluster's own members,
  `l2_normalize(AVG(embedding))`, which is what `compute_centroid()` produces on the write path.
  It runs from `run_clustering` immediately before the centroids are loaded, so a repaired cluster
  is usable in the same cycle.
  It touches only rows where `embedding_centroid IS NULL`, and deliberately does not bump
  `updated_at`, since that drives archival by staleness and a repair is not activity.
- `load_cluster_centroids()` handles NULL as its own case, ahead of the parse.
  It emits one `clustering.centroid_missing` per cycle carrying a count and a sample of ids,
  rather than one line per cluster, and keeps `clustering.bad_centroid` for a value that is present
  but unparseable. The two states now read differently because they mean different things.

Measured against the live database: of the 40, 7 hold member embeddings and are repairable, and
the aggregate is unit-length in all 7 cases, matching the write path.
The other 33 are seed clusters whose members carry no embeddings at all.
Nothing can compute a centroid for those, which is why the remaining case is reported rather than
silently skipped.

Confirmed on the running stack after rebuilding `anveshak-analyst` and recreating
`analyse-scheduler`: the first `cluster_loop` pass logged
`clustering.centroid_backfilled count=5` for `nag-topic-01` and the active NULL count went 40 to
35, with the last 2 repairable clusters waiting on their own topic's turn, since
`get_prioritized_topics` does not process every topic every cycle.
The 33 unrepairable ones now surface as a handful of `clustering.centroid_missing` lines carrying
a count and a topic_id, one per topic per cycle.

`tests/unit/test_clustering_orchestrator.py::TestMissingCentroids` pins all of it: NULL skipped
without a corruption log, one aggregated line per cycle, the parse-failure path still reachable,
the backfill SQL's three invariants, and backfill running before the load.

#### The two schedulers had no heartbeat to read

`scrape-web-scheduler` and `scrape-social-scheduler` are plain `while True` loops, not ARQ
workers, so nothing wrote an ARQ health key for them and item 9 left them on `kill -0 1`.

They now record liveness themselves, through `sdk/anveshak/heartbeat.py`:

- `beat()` writes `anveshak:scheduler:<name>:health-check` with a TTL, so presence of the key is
  the signal and a stopped loop cannot fake it. The `arq:` namespace is avoided because writing
  into it would collide with a queue of the same name.
- `sleep_with_heartbeat()` replaces the bare `asyncio.sleep(poll_interval_s)` between cycles.
  The cycle interval is 900s by default, which cannot be the detection window, so the key is
  refreshed every 30s while the loop sleeps.
- `HEARTBEAT_TTL_S` is 120s rather than 31s. A cycle body that runs long, one enqueue per active
  topic against a slow database, must not be reported dead on its own cost; that is the mistake
  that made a worker flap in item 9. A stopped loop is still visible in under two minutes.

`sdk/arq_health.sh` needed no logic change, only wider wording: it already appends
`:health-check` to whatever prefix compose passes it, so the same probe covers both kinds of
process.

Verified on the running stack: both containers were rebuilt and recreated, both keys appear,
both in-container probes exit 0, a probe against an unwritten key exits 1 with the reason on
stderr, and `docker ps` reports both healthy.

`tests/contracts/test_service_contracts.py::TestSchedulerHeartbeats` asserts that no compose
healthcheck uses `kill -0 1` anywhere, that each scheduler's `HEARTBEAT_NAME` is the key its
compose probe reads, and that neither scheduler sleeps without refreshing.
The first of those is what stops the weak probe coming back on the next service added.

#### The integration scripts hid their own failures

Found while running item B. `scripts/test_ollama_models.py` reported
`"detail": "response_length=0"` for a call that had in fact returned HTTP 500 with
`llama-server process has terminated: signal: killed`: it read `resp.json().get("response", "")`
without checking the status, so a server error became an empty string.
On the retry it reported `"detail": ""` instead, because the generic handler used
`str(exc)[:200]` and `httpx.ReadTimeout` stringifies to nothing.

Two fixes, both in the same spirit as the rest of this document:

- `_generation_or_error()` in `scripts/test_ollama_models.py` returns the status code and body for
  any non-2xx reply, so the reason is in the report rather than in the reader's head.
- `_exc_detail()` prefixes the exception type, and falls back to the type alone when the message is
  empty. Added to all four in-container scripts, `test_ollama_models.py`,
  `test_multilingual_pipeline.py`, `test_vision_models.py` and `test_analyst_models.py`, which all
  used the same `str(exc)[:200]` idiom at 19 sites between them.

A test that fails is useful; a test that fails with an empty `detail` field costs a repro run to
learn anything.

#### The analyst backlog was throughput, not a wedge

Item 9 recorded `analyse_content` starting with `delayed=1505.99s` and 342 jobs on `arq:scraper`.
Re-measured this session with the item 9 healthchecks in place: `arq:analyst` went from 944 to 328
in about eight minutes, roughly 68 jobs a minute, with individual jobs completing in 0.4s to 0.9s.

Depth is not monotonic, and reading it as a drain curve is a mistake: the scrapers keep feeding the
queue, so it went back up to 660 later in the same session while the worker reported
`j_complete=1052 j_failed=0 j_ongoing=4`. The signal to read is the worker's own counters in
`arq:analyst:health-check`, not `zcard`. Both were healthy throughout.

So the delay is not a second wedge of the item 7 kind. No code change here.
It is also not the whole story: later in the same session, with the queue at 555, all four job
slots were held by `generate_cluster_label` waiting on Ollama and timing out at 300s while the
worker used 0.88 percent CPU. That is recorded under [Open findings](#open-findings), because
separating LLM jobs from ML jobs is a design change rather than a fix to this item.
One practical consequence for item C: `analyse-worker` was at 291 percent CPU servicing that
backlog while integration step 5 ran inside the same container, which is why that step took far
longer than its usual time. Let the queue quieten before treating a `test-ci` duration as normal.

### 11. `make test-scrape`, item D

Run on 2026-08-21 with internet available. It had never been run.
Three of the seven rows failed, and only one of those three was a real source problem.

#### The scraper block was killed by its own budget

`scripts/test_scrape.py` gave the in-container source tests 600s, and the duration of those tests
swings by an order of magnitude with load and network conditions. Two runs an hour apart:
1330s the first time, of which the ten RSS feeds were 1128s with BBC World alone at 466s, and 322s
the second time with BBC World at 34s. The feeds are fetched through the production path at its
per-domain rate limit while the rest of the stack competes for the same host, so the slow run is
as real as the fast one and 600s sits right in the middle of the spread.

So the run was killed mid-RSS every time, and `subprocess.run` discarded every partial result with
it. What the operator saw was a single row:

```
error   anveshak-scrape-web-scheduler-1   ✗ FAIL   0   600.0s   Timeout (600s)
```

A working scraper, reported as one opaque failure.
The timeout is now 1800s, with the measurement recorded next to it.

#### A timeout that could not be diagnosed

`test_scrape_sources.py` redirects stderr to `/dev/null` so library log noise cannot corrupt the
JSON on stdout. That is correct, and it also meant a killed run left nothing at all to look at.

`_progress()` now writes to the original fd 2, one line per phase and per source, and the
orchestrator's `TimeoutExpired` handler reports the last `[progress]` line it received. A run that
is killed now says which source it was on, rather than only that it ran out of time.

#### A disabled adapter is not a failure

`REDDIT_ADAPTER_ENABLED=false` was reported as `✗ FAIL`. Every adapter ships disabled by
architectural rule 1, so a stock configuration was guaranteed to show failures, which is exactly
the condition under which people stop reading a test's output.

`_skipped()` in `scripts/test_scrape_social.py` reports `SKIP` for all three adapters that can be
switched off, the table renders it dimmed, the summary counts skips separately, and the exit code
now keys on `status == "FAIL"` rather than `!= "PASS"`.

#### What the sources themselves said

Final run: **20 of 22 passed, 2 failed, 1 skipped**. All ten RSS feeds, all five Crawl4AI web
fetches, the BBC Tor mirror at 56108 chars through the Tor circuit, Telegram auth and both
channels, and X auth.

Two genuine results are worth keeping:

- **Tor Project onion, FAIL.** `scraper.darkweb_fetch_failed` with
  `Proxy Server could not connect: General SOCKS server failure`, while the BBC mirror through the
  same circuit succeeded seconds later. That is one unreachable hidden service, not a broken Tor
  path.
- **X keyword search returned no tweets.** The bearer token is accepted and the spend guard is
  intact, so this is the API tier rather than the adapter.

## Remaining work

### 5. Verification: integration now passes

`make test-frontend` and `make test-contract` have since been run and pass.

Step 1 of `make test-integration`, the host-side DB suite, has now been run against a live stack.
It started at 6 failures and now passes 128 tests with 0 failures.
The failures were all pre-existing and had three distinct causes, none related to the venv rebuild:

1. **Pagination signature drift.**
   `list_signals` (`services/api/anveshak/api/db/signals.py:404`) and
   `list_sources_by_org` (`services/api/anveshak/api/db/sources.py:212`) both return `tuple[list[dict], int]`
   so callers can page, but three tests still unpacked the result as a bare list.
   Symptom was `TypeError: list indices must be integers or slices, not str` and `assert ([], 0) == []`.
   Fixed in `tests/integration/test_db_signals.py` and `tests/integration/test_org_isolation.py`,
   which now assert on the total as well as the page.
2. **A mock patching a symbol that no longer exists.**
   `tests/integration/test_reporter_e2e.py` patched `anveshak.reporter.worker.call_ollama_with_retry`.
   The reporter now builds report bodies from SQL and the only LLM call left in `generate_report` is
   `call_ollama_for_bluf` (`services/reporter/anveshak/reporter/worker.py:186`), which the test already patched separately.
   The stale patch and the `ReportContent` mock it fed were dead weight; both removed.
3. **A real production bug, described under item 8 below.**

Also removed a `PytestWarning` in `tests/integration/test_db_isolation.py`:
module-level `pytestmark` applied `pytest.mark.asyncio` to sync tests.
`asyncio_mode = "auto"` in `pyproject.toml` already marks the async tests, so the explicit marker was redundant.

All five steps were run end to end on 2026-08-21, in the item 10 session. Result:

| Step | Result |
| --- | --- |
| 1/5 host-side DB tests | 128 passed |
| 2/5 analyst models, in `analyse-worker` | 4/4 passed |
| 3/5 vision models, in `analyse-vision-worker` | 5/5 passed |
| 4/5 Ollama LLM tests, in `report-worker` | 2/4, both generation tests failed |
| 5/5 multilingual pipeline, in `analyse-worker` | killed at the 50 minute mark, 2 of its cases had passed |

Steps 4 and 5 are the same problem wearing two hats, and neither is a code defect.

**Step 4.** Ollama was OOM-killed: `docker inspect` reports `OOMKilled: true` and the API returned
`HTTP 500: llama-server process has terminated: signal: killed`.
The Docker VM has 11.9 GB and the running stack was holding about 10.2 GB of it, leaving roughly
4.2 GB available against a 7B model with an 8192 context and `OLLAMA_NUM_PARALLEL=2`.
The container's own `mem_limit: 8g` is not the binding constraint and is misleading here, since the
VM cannot honour it while everything else runs.
Proved by elimination: with `analyse-worker`, `analyse-vision-worker` and `scrape-web-worker`
stopped, available memory went to 9.3 GB and the same script reported **4/4 passed**.

**Step 5.** `translation_zh` passed but took 1775s and `translation_ru` took 346s, against an
`analyse-worker` sitting at 291 percent CPU servicing its own backlog in the same container.
The step is not stuck, it is starved.

So the honest status of item B is: steps 1 to 3 pass unconditionally, and steps 4 and 5 pass only
when the host is not simultaneously running the full stack. On this hardware the two are mutually
exclusive. Options, in order of preference:

1. Give the Docker VM more memory, if the host has it. This is the only fix that makes
   `make test-ci` meaningful as a single command.
2. Run steps 4 and 5 against a quiesced stack, stopping `analyse-worker`,
   `analyse-vision-worker` and `scrape-web-worker` first. This is what was done to prove the
   diagnosis and it is repeatable, but it means `make test-integration` cannot be trusted as one
   run on this host.
3. Drop `OLLAMA_NUM_PARALLEL` to 1 for CPU deployments. It halves the KV cache, and two parallel
   slots on a CPU-bound 7B model do not buy throughput anyway. Left as a decision rather than
   applied, because the same default is read by the GPU deployment.

Still unrun:

- `make test-ci` - runs unit, contract, integration, frontend, and the 80 percent coverage gate.
  It contains `test-integration`, so it inherits the constraint above.
- `make test-scrape` - now run, see [item 11](#11-make-test-scrape-item-d)

`make test-ci` is the one that matters, since the segfault that used to break it did not reproduce and
that should be confirmed end to end rather than inferred.

Note that `make test-contract` did not exist when this document was written, despite `AGENTS.md`
listing it in the development workflow. The target was added.

### 6. Commit the branch

Done, as `694de76`, but **not** using the split below.
Everything through item 8 went in as one commit mixing the 446-file reformat with the substantive
fixes, which is worth knowing before bisecting anything in this range: a `git bisect` landing on
`694de76` cannot tell a formatting change from a behaviour change.

The split that was suggested at the time, kept for the record:

1. Python pin, `venv-check` guard, the `uv run run` Makefile fix, and the new `test-contract` target
2. `ruff format` across `services/`, `sdk/`, `tests/`, `scripts/`, formatting only
3. Lint fixes with behaviour implications: the missing `Any` import, the dead computations, the AST
   rewrites of the two source-scanning tests
4. Bandit justifications and `respect-gitignore = false`
5. `pyright` dependency and config, plus the type bugs it caught
6. The baseline test fixes, including the `arq:analyst` queue fix
7. Rule 2 scope narrowing and the `verify_labels.py` exemption registry
8. The analyst worker hang and the resource limits, item 7
9. The `scam_templates` seed restored to the baseline migration, item 8
10. The integration test fixes, item 5

Items 9, 10 and 11 are still uncommitted, and are small enough to split properly.
Suggested, in this order:

1. **Env forwarding.** `infra/compose.yml` (the `environment:` blocks and the `x-common-env`
   OTEL entries), `.env.example`, `.env`, the removed `credibility_update_interval_s` in
   `services/analyst/anveshak/analyst/settings.py`, plus the guard:
   `scripts/verify_env_forwarding.py`, `tests/unit/test_env_forwarding.py`, and the `verify-env`
   target and `.PHONY` entry in the `Makefile`.
   Behaviour change: seventeen settings start responding to `.env` for the first time.
   `CREDIBILITY_MIN_AUTO_DROP` must be corrected to `1.0` in the same commit, or the noise floor
   swallows every credibility drop the moment it starts being read.
2. **Healthchecks.** `sdk/arq_health.sh`, the six healthcheck blocks in `infra/compose.yml`
   (five ARQ workers plus `whatsapp-bridge`) and the new `x-worker-healthcheck-defaults` anchor,
   `health_check_interval = 30` in `services/{scraper,social,vision}/.../jobs.py` and
   `services/reporter/anveshak/reporter/worker.py`, and
   `tests/contracts/test_service_contracts.py::TestWorkerHealthchecks`.
   Behaviour change: five workers start being judged on their ARQ heartbeat rather than on PID 1,
   and `whatsapp-bridge` stops being permanently unhealthy.
3. **Worker observability.** `configure_logging` and `configure_tracing` in the four `jobs.py`
   modules, `configure_tracing` in the six existing entrypoints (`api/main.py`,
   `scraper/main.py`, `social/main.py`, `vision/main.py`, `analyst/scheduler.py`,
   `reporter/worker.py`), the `tracing.disabled` log line in `sdk/anveshak/tracing.py`, and the
   four new `E402` per-file ignores in `pyproject.toml`.
4. **Translation tokenizer guard.** `services/analyst/anveshak/analyst/translation.py` only:
   the fail-closed `tokenizer is None` branch and the two pyright suppressions.
5. **Test hygiene.** The five `tests/unit/` modules that dropped
   `pytestmark = [pytest.mark.unit, pytest.mark.asyncio]` down to `pytest.mark.unit`.
   Pure warning cleanup, no behaviour change, safe to squash into any of the above if preferred.
6. **Item 10.** Two independent fixes, so two commits if you prefer:
   the centroid repair is `services/analyst/anveshak/analyst/clustering.py` plus
   `tests/unit/test_clustering_orchestrator.py`; the scheduler heartbeat is
   `sdk/anveshak/heartbeat.py`, `sdk/arq_health.sh`, the two scheduler healthchecks in
   `infra/compose.yml`, `services/{scraper/anveshak/scraper,social/anveshak/social}/main.py`,
   `tests/unit/test_scheduler_heartbeat.py` and
   `tests/contracts/test_service_contracts.py::TestSchedulerHeartbeats`.
   Behaviour change: clusters that were skipped every cycle start being matched, and the two
   schedulers start being judged on their loop rather than on PID 1.
   The four `scripts/test_*.py` diagnostics changed too, `_exc_detail()` in all four and
   `_generation_or_error()` in the Ollama one. They are test tooling with no runtime effect, so
   they can ride along or go in their own commit.
7. **Item 11.** `scripts/test_scrape.py`, `scripts/test_scrape_sources.py` and
   `scripts/test_scrape_social.py`: the 1800s timeout with its measurement, `_progress()` and the
   `TimeoutExpired` reporting, and `SKIP` for a disabled adapter. Harness only, no service code.

Commits 1 and 2 both change how running services behave, the first in what they read from the
environment and the second in when they are declared unhealthy. Both need to be revertable on
their own, so neither should be folded into the others. The same applies to commit 6.
Note that commits 2 and 3 both touch the four `jobs.py` files, for different reasons.

`docs/venv_rebuild_plan.md` goes with whichever commit lands last.

The `git stash` symptom described at the end of this document is gone, as predicted.

## Risk register

| Risk | Mitigation |
| --- | --- |
| `uv sync` picks Homebrew 3.14 and ML wheels fail to build | Step 1 pins 3.12 before the venv is deleted |
| Deleting the 2.0 GB venv on a slow connection leaves no working env | uv cache is warm at 410 MB; run during a window where a 15 minute rebuild is acceptable |
| Anaconda reappears as the base interpreter | `uv python install 3.12` provisions a uv-managed CPython, and `.python-version` keeps selection deterministic |
| spaCy models missing after rebuild | None are installed in the host venv today, and only `spacy>=3.7` is declared in `services/analyst/pyproject.toml`. Models load inside containers, so the host venv does not need them. |
| Integration tests are unrunnable because the host is pinned | Root cause was the analyst worker hang, item 7, now fixed. `cpus:` limits on the two heavy workers bound the blast radius if it recurs. |
| Another archived migration seeded data the squashed `001` dropped | Closed. `services/api/migrations/archive/` holds exactly three `INSERT` statements: `scam_templates` (restored into `001`, item 8), `organizations` (now owned by `scripts/seed_demo.sql`), and an `org_sources` backfill that selects from existing rows and so has nothing to do on a fresh schema. Nothing else was lost. |
| A wedged worker reports healthy | Closed by item 9. All five ARQ workers set `health_check_interval = 30` and their container healthcheck reads the ARQ health key, which a frozen event loop cannot refresh. |
| A healthcheck marks a busy worker unhealthy by its own cost | `docker exec` runs inside the container's CPU quota. Worker probes use `x-worker-healthcheck-defaults` with `timeout: 20s`, against a measured worst case of 6.5s for a starved `import redis`. If a worker flaps again, time the probe with `docker exec` before assuming the worker is at fault. See item 9. |
| An env var is added to `.env.example` but never forwarded, and silently does nothing | `make verify-env` fails on it, and `tests/unit/test_env_forwarding.py` fails in CI. Both share one scanner, so they cannot drift. See item 9. |
| A setting is tuned in `.env` in a way that defeats another setting | Not covered. `tests/unit/test_credibility_settings.py` asserts the invariants against `AnalystSettings()`, which reads code defaults; no settings class sets `env_file`, so no test sees the deployed values. This is how `CREDIBILITY_MIN_AUTO_DROP=10.0` sat in `.env` unnoticed. A startup-time invariant check on the live settings object would close it. |

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
