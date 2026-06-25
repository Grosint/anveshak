---
paths:
  - "**/*.py"
---
# Python Coding Style

- PEP 8
- Type annotations all function signatures
- black formatting, ruff linting, isort imports
- Pydantic v2 strict: model_config = ConfigDict(strict=True) on ALL models
- Labels field MANDATORY, non-Optional on all Pydantic models
- Immutable dataclasses for DTOs where fit
- Module-level constants for SQL queries (testability — same as Drishti)
- No bare `except:` clauses

# Silent Failure Prevention

Every conditional feature (flag, env toggle, optional dep) MUST log at INFO when disabled/degraded. Silent defaults = #1 "works on my machine" bug source.

- Feature off → `log.info("feature.disabled", feature="X", reason="env var not set")`
- Optional model missing → `log.warning("model.not_loaded", model="X")`, never return 0.0 silently
- Env var missing from compose → feature silently defaults false, no trace
- Volume-mounted model dir empty → inference returns zero scores, no error

When in doubt: log it. Analyst debugging missing signal at 2am needs WHY feature is off, not just no output.