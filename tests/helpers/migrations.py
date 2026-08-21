"""Helpers for asserting on Alembic migration content.

Usage:
    from tests.helpers.migrations import migrations_sql

    assert "CREATE TABLE organizations" in migrations_sql()

Tests must assert on what the migration set *contains*, never on a
per-file path. Migrations 002-013 were squashed into
``001_initial_schema.py`` and the originals moved to
``services/api/migrations/archive/``; every test that hardcoded a
version filename broke on that squash. Concatenating the live versions
directory survives the next squash too.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[2] / "services" / "api" / "migrations" / "versions"
)


@lru_cache(maxsize=1)
def migrations_sql() -> str:
    """Source of every live migration, concatenated in version order.

    Excludes ``services/api/migrations/archive/``, which holds superseded
    pre-squash migrations that no longer run.
    """
    files = sorted(MIGRATIONS_DIR.glob("*.py"))
    if not files:
        raise AssertionError(f"no migration files found in {MIGRATIONS_DIR}")
    return "\n".join(p.read_text() for p in files)
