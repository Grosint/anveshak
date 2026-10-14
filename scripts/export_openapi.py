#!/usr/bin/env python3
"""Export the API service's OpenAPI schema for frontend type generation.

The frontend's API types are generated from this schema rather than written by
hand, so a field renamed on a Pydantic `response_model` breaks the frontend
build instead of silently emptying a panel. The schema is read from the FastAPI
app object directly: nothing needs to be running, and no database, Redis or
Ollama is touched, because the lifespan hook is never entered.

The output is rendered with sorted keys so that an unchanged API always
produces a byte-identical file, which is what lets
`tests/contracts/test_openapi_schema_committed.py` treat any difference as drift.

Usage:
    python scripts/export_openapi.py
    make gen-api-types     (export, then regenerate frontend/src/api/generated/schema.ts)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "frontend" / "src" / "api" / "generated" / "openapi.json"


def current_schema() -> dict[str, Any]:
    """Return the OpenAPI schema the API service serves at /openapi.json."""
    from anveshak.api.main import app

    return app.openapi()


def render(schema: dict[str, Any]) -> str:
    """Render a schema deterministically, so equal schemas give equal bytes."""
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(render(current_schema()), encoding="utf-8")
    print(f"wrote {SCHEMA_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
