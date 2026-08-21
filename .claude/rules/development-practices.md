# Development Practices

8 instincts. TDD wiring, testing patterns, seeds, migrations, session workflow.

## Agent Wiring Check After GREEN

- After tests pass, verify every new symbol has a caller. Agents create new files but miss modifying existing ones.
  Checklist: new function -> grep callers, new async loop -> grep lifespan registration, new router -> verify main.py, new component -> verify route render.
  See: `.claude/skills/learned/agent-wiring-check-after-green.md`

## Characterization Testing (Existing Code)

- Existing working code: read first, then pin current behavior (including bugs).
  Mark bugs explicitly: `test('BUG R2: defaults to HIGH for unknown types')`.
  Hollow test detection: `expect(document.body).toBeTruthy()` always passes — replace w/ specific assertions.
  TDD = new features only. Characterization = safety net before refactoring.
  See: `.claude/skills/learned/characterization-testing-existing-code.md`

## Demo Seed Script

- Multi-stage: DB seed (idempotent) -> ARQ enqueue+poll -> clustering -> pre-seed signals -> auth -> report gen -> PDF.
  Run ONE seed at a time on CPU — concurrent report gens timeout. Pre-seed signals for demo reliability.
  `ON CONFLICT DO NOTHING` allows reruns. Explicit step counters `[3/8]` show which step hangs.
  `--replay` vs `--live` flags w/ `ANVESHAK_ALLOW_LIVE=1` env guard.
  See: `.claude/skills/learned/demo-seed-script-pattern.md`

## Makefile Infrastructure-First

- Phased startup: infra (postgres/redis/ollama) -> health-poll loop -> migrate -> app services.
  Never `sleep N` for health — always poll. Migrations BEFORE app services or crash-loop on empty schema.
  `--format json` for machine-parseable health status. `$(call warn,...)` breaks inside shell blocks — use plain printf.
  See: `.claude/skills/learned/makefile-infrastructure-first-setup.md`

## Migration Files in Containers

- Host migration files NOT visible in running containers (COPY, not volume mount).
  `alembic upgrade head` runs zero migrations, no error. Fix: `docker cp` or rebuild image.
  Don't forget test database migration too.
  See: `.claude/skills/learned/migration-not-visible-in-container.md`

## Phase-Check Pitfalls

- WebSocket: `accept()` before `verify_token()` = auth aspirational, not enforced.
  Settings: new setting in settings.py w/ zero grep matches in service code = not wired.
  Status strings: use exact spec values (`"queued"` not `"pending"`). Test exact string, not just truthy.
  SQL JOINs: frontend shows field from related table = verify SQL has JOIN, not just TypeScript type.
  Self-defeating defaults: boost=2.0 < min_threshold=10.0 = feature never fires. Write invariant tests.
  See: `.claude/skills/learned/phase-check-pitfalls.md`

## Session Boundary Plan-Driven Dev

- Multi-session projects: write plan to `docs/` file ONCE. Each session: 3 lines (read plan, state step, /tdd).
  Plan = architecture, numbered steps, phased exit criteria, test matrix, risk register.
  Memory tracks decisions/preferences. Plans track implementation sequences.
  See: `.claude/skills/learned/session-boundary-plan-driven-dev.md`

## pytest.exit() Safety Guard

- Session-scoped autouse fixture: hard-block if targeting production DB. `pytest.exit()` kills entire session w/ returncode=1.
  `pytest.skip()` = silently green. `pytest.fail()` = only fails guard test, others still run.
  Deny-by-default: check for production identifier and refuse, not test identifier and allow.
  See: `.claude/skills/learned/pytest-exit-safety-guard.md`
