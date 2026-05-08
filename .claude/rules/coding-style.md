---
paths:
  - "**/*.py"
---
# Python Coding Style

- PEP 8 conventions
- Type annotations on all function signatures
- black for formatting, ruff for linting, isort for imports
- Pydantic v2 strict mode: model_config = ConfigDict(strict=True) on ALL models
- Labels field MANDATORY and non-Optional on all Pydantic models
- Immutable dataclasses for DTOs where appropriate
- Module-level constants for SQL queries (testability — same pattern as Drishti)
- No bare except: clauses

# Silent Failure Prevention

Every conditional feature (feature flag, env toggle, optional dependency) MUST log
at INFO level when disabled or operating in degraded mode. Silent defaults are the
#1 source of "works on my machine" bugs in this project.

- Feature toggled off → `log.info("feature.disabled", feature="X", reason="env var not set")`
- Optional model missing → `log.warning("model.not_loaded", model="X")`, never return 0.0 silently
- Env var missing from compose → feature silently defaults to false with no trace
- Volume-mounted model dir empty → inference returns zero scores with no error

When in doubt: log it. An analyst debugging a missing signal at 2am needs to see
WHY a feature is off, not just that it produced no output.
