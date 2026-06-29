# Dependency Patterns

7 instincts. Library pitfalls, SDK boundaries, workspace structure.

## asyncpg JSONB Codec

- asyncpg returns JSONB as `str` by default. ONE shared pool factory (`sdk/anveshak/db.py:create_db_pool()`) w/ codec registration.
  Before enabling globally, grep for bare `json.loads(row[` without `isinstance(str)` guard — breaks after codec (TypeError caught = silent data loss).
  Safe: `json.loads(val) if isinstance(val, str) else val`.
  See: `learned/asyncpg-jsonb-codec-shared-pool.md`

## Jinja2 None vs Missing

- `.get(key, default)` returns `None` when key exists w/ None value — NOT the default.
  Crashes arithmetic: `None * 100 = TypeError`. Use `(match.get('confidence') or 0)` for numeric formatting.
  `or 0` converts 0 to 0 (falsy) — OK for percentage display.
  See: `learned/jinja2-none-vs-missing-default.md`

## Optional Dep Lazy Import

- Heavy/optional deps (WeasyPrint, PyMuPDF, facetorch): module-level try/except, `None` sentinel.
  Two-level logging: INFO at startup ("feature disabled"), WARNING at runtime ("feature invoked but unavailable").
  `if fitz is None: return None` — trivial feature checks.
  See: `learned/optional-dep-lazy-import-two-level-log.md`

## passlib + bcrypt>=4.0

- passlib 1.7.x broken w/ bcrypt>=4.0 (removed `__about__`, changed API). All login endpoints HTTP 500.
  Replace entirely w/ thin direct-bcrypt wrapper: `_BcryptContext` w/ `verify()` and `hash()`.
  Drop passlib import + CryptContext. Direct bcrypt simpler, future-proof.
  See: `learned/passlib-bcrypt-incompatibility.md`

## SDK: No DB/ARQ Dependencies

- Shared utilities in SDK = dependency-free. No asyncpg, no arq, no service-specific imports.
  Caller handles DB persistence and ARQ enqueueing. Content hash = SHA-256 of raw bytes (not text).
  Storage path: `media/{topic_id}/{YYYY}/{MM}/{DD}/{content_hash}{ext}`.
  See: `learned/sdk-shared-utility-no-db.md`

## uv Workspace Restructure

- Safe sequence: move files -> delete old -> update pyproject.toml `packages` -> update Dockerfiles -> `uv sync` -> run tests.
  `packages` value = directory path relative to pyproject.toml, not Python import name.
  Cannot remove `anveshak/<service>/` — namespace collisions across test installs.
  Always import from installed package name, never filesystem path.
  See: `learned/uv-workspace-restructure.md`

## Vitest + Vite Setup

- Config in `vite.config.ts` `test:` block, NOT separate vitest config. Setup file: `src/test/setup.ts` w/ jest-dom.
  CRITICAL: exclude `src/test` from `tsconfig.json` — vitest is devDep, `tsc --noEmit` fails without exclude.
  `postcss.config.js` must use `module.exports` not `export default` (CJS resolution).
  See: `learned/vitest-vite-setup.md`
