Working directory restricted. Let me output the fixed file directly:

# Silent Failure Prevention

7 instincts. Silent failures = #1 production bug source.

## Return Values

- ML float scores: return `None` on error, never `0.0` or defaults
  Force null checks at call sites (`if score is not None`)
  See: `learned/deepfake-none-error-signal.md`

- Mandatory output fields set in every return path, not just happy path

## Environment & Configuration

- Every env var in `settings.py` MUST be in compose `environment:` block
  Missing vars silently default to `false`/`""`, no error
  See: `learned/compose-env-var-silent-disable.md`

- No inline comments on integer env vars in `.env` — pydantic crashes silently
  See: `learned/dotenv-inline-comment-int-fields.md`

- Core features in base `compose.yml`, never overlay files
  See: `learned/compose-overlay-core-feature-trap.md`

## Quality Gates

- Quality signal computed → apply at EVERY consumption point (SQL, API, reports)
  `WHERE quality IS NULL OR quality >= threshold` for backward compat
  Checklist: compute → SQL filter → API filter → RAG context → report display
  See: `learned/quality-gate-all-consumers.md`

- Word-counting regex must cover all scripts (Devanagari, Arabic, CJK)
  Missing ranges silently drop content (zero words)
  See: `learned/quality-gate-unicode-ranges.md`

- `detect_language()` must return real detected language even if no downstream model supports it
  Filtering on model availability silently drops content
  See: `learned/detect-language-must-not-gatekeep.md`

## ML Models

- Volume-mounted models start empty on first deploy — add health checks
  Empty volume = silent 0.0 scores, no error
  See: `learned/volume-mounted-models-silent-failure.md`

## Scripts (psql subprocess)

- `psql -A -F "\t"` returns `''` for NULL, not Python `None`
  `float(row["col"]) if row.get("col") is not None` crashes w/ `ValueError: could not convert string to float: ''` — empty string not None
  Use truthiness: `float(raw) if raw else default`
  Only subprocess scripts — asyncpg returns proper None
  See: `learned/psql-null-empty-string-pitfall.md`

## Array Matching

- PostgreSQL `&&` returns false silently when granularity differs (multi-word keywords vs single-word tags). Normalize before matching.
  See: `learned/keyword-tag-granularity-mismatch.md`

## Git & Build

- Blanket `.gitignore` patterns (`models/`, `media/`) silently exclude Python packages w/ same name — fresh clones break `ImportError`, dev machines fine. Use negation: `!sdk/anveshak/models/`
  See: `rules/git-build.md`

---

Fix: restored missing inline code `` `ValueError: could not convert string to float: ''` `` in Scripts section. Can't write file due to directory restrictions — need write access to `/Users/navitas28/Work/anveshak/.claude/rules/silent-failures.md`.