"""The committed OpenAPI schema matches the API service.

The frontend's API types are generated from
`frontend/src/api/generated/openapi.json`, so that file is the contract between
the Pydantic models and the TypeScript that reads them. A model change that is
not followed by `make gen-api-types` leaves the frontend compiling against the
old shape, and a renamed field then reads as `undefined` instead of failing the
build. This test is the half of the drift check that sees the Python side; the
frontend suite checks that `schema.ts` was generated from this file.
"""

from __future__ import annotations

import json

import pytest

from scripts.export_openapi import SCHEMA_PATH, current_schema, render

pytestmark = pytest.mark.contract


def test_committed_schema_matches_the_api() -> None:
    committed = SCHEMA_PATH.read_text(encoding="utf-8")

    assert committed == render(current_schema()), (
        f"{SCHEMA_PATH} is stale against the API service. "
        "Run `make gen-api-types` and commit the result."
    )


def test_tipline_ingest_declares_its_response_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    ok = schema["paths"]["/api/v1/tipline/ingest"]["post"]["responses"]["200"]
    ref = ok["content"]["application/json"]["schema"]["$ref"]

    assert ref == "#/components/schemas/TiplineIngestResponse"
    status = schema["components"]["schemas"]["TiplineIngestResponse"]["properties"]["status"]
    assert status["enum"] == ["queued", "duplicate"]
