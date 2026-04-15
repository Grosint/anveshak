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
