# Silent Failure Prevention

Consolidated from 7 learned instincts. Silent failures are the #1 source of production bugs.

## Return Values

- ML inference returning float scores: return `None` on error, never `0.0` or default values
  Force explicit null checks at call sites (`if score is not None`)
  See: `learned/deepfake-none-error-signal.md`

- Functions with mandatory output fields must set them in every return path, not just the happy path

## Environment & Configuration

- Every env var a service reads in `settings.py` must be in compose `environment:` block
  Missing vars silently default to `false`/`""` with no error
  See: `learned/compose-env-var-silent-disable.md`

- Never put inline comments on integer env vars in `.env` — pydantic crashes silently
  See: `learned/dotenv-inline-comment-int-fields.md`

- Core features must be in base `compose.yml`, never in overlay files
  See: `learned/compose-overlay-core-feature-trap.md`

## Quality Gates

- When you compute a quality signal, apply it at EVERY consumption point (SQL, API, reports)
  Use `WHERE quality IS NULL OR quality >= threshold` for backward compat
  Checklist: compute point → SQL filter → API filter → RAG context → report display
  See: `learned/quality-gate-all-consumers.md`

- Word-counting regex must cover all supported languages (Devanagari, Arabic, CJK)
  Missing ranges silently drop content with zero detected words
  See: `learned/quality-gate-unicode-ranges.md`

- Language detection must not gatekeep — return the real detected language even if
  no downstream model supports it. Filtering on model availability silently drops content.
  See: `learned/detect-language-must-not-gatekeep.md`

## ML Models

- Volume-mounted models start empty on first deploy — add health checks
  Empty volume = silent 0.0 scores with no error
  See: `learned/volume-mounted-models-silent-failure.md`

## Scripts (psql subprocess)

- Scripts that shell out to `psql -A -F "\t"` get empty string `''` for NULL columns,
  not Python `None`. Code like `float(row["col"]) if row.get("col") is not None` crashes
  with `ValueError: could not convert string to float: ''`
  Use truthiness check: `float(raw) if raw else default`
  Only affects subprocess-based scripts — asyncpg returns proper Python None
  See: `learned/psql-null-empty-string-pitfall.md`

## Git & Build

- Blanket `.gitignore` patterns (`models/`, `media/`) silently exclude Python packages
  with the same directory name — fresh clones break with `ImportError`, but developer
  machines work fine (files exist in working tree). Always use negation rules for
  Python packages: `!sdk/anveshak/models/`
  See: `rules/git-build.md`
