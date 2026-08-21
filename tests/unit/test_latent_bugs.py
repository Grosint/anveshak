"""Tests for latent bugs: orphan_enqueued_at + JSONB codec consistency.

Bug 1: orphan_enqueued_at column missing from schema → orphan sweep crashes
Bug 2: 7 of 8 service pools missing JSONB codec → data loss in 3 locations
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SERVICES_DIR = Path(__file__).resolve().parents[2] / "services"


# ===========================================================================
# Bug 1: orphan_enqueued_at must exist in migration
# ===========================================================================


class TestOrphanEnqueuedAtColumn:
    """Column orphan_enqueued_at must exist in the DB schema."""

    def test_orphan_enqueued_at_in_migration(self):
        """A migration must ADD orphan_enqueued_at to content_items."""
        migrations_dir = _SERVICES_DIR / "api" / "migrations" / "versions"
        found = False
        for f in sorted(migrations_dir.glob("*.py")):
            content = f.read_text(errors="ignore")
            if "orphan_enqueued_at" in content:
                found = True
                break
        assert found, (
            "No migration creates 'orphan_enqueued_at' column on content_items. "
            "Orphan sweep (scheduler.py:64) references it but column doesn't exist."
        )


# ===========================================================================
# Bug 2: JSONB codec — shared pool utility + safe parsing
# ===========================================================================


class TestSharedPoolUtility:
    """SDK must provide a shared create_db_pool with JSONB codec."""

    def test_sdk_create_db_pool_exists(self):
        """anveshak.db module must export create_db_pool function."""
        try:
            from anveshak.db import create_db_pool
        except ImportError:
            pytest.fail(
                "anveshak.db.create_db_pool not found — "
                "SDK must provide shared pool with JSONB codec"
            )
        import asyncio

        assert asyncio.iscoroutinefunction(create_db_pool), "create_db_pool must be async"


class TestAllServicePoolsUseCodec:
    """Every service pool creation must use the shared utility (or init callback)."""

    _POOL_FILES = [
        ("analyst worker", "analyst/anveshak/analyst/jobs.py"),
        ("analyst scheduler", "analyst/anveshak/analyst/scheduler.py"),
        ("scraper", "scraper/anveshak/scraper/jobs.py"),
        ("social worker", "social/anveshak/social/jobs.py"),
        ("social scheduler", "social/anveshak/social/main.py"),
        ("reporter", "reporter/anveshak/reporter/db/__init__.py"),
        ("vision", "vision/anveshak/vision/db/__init__.py"),
    ]

    @pytest.mark.parametrize("service,rel_path", _POOL_FILES)
    def test_service_pool_has_jsonb_codec(self, service, rel_path):
        """Service pool must use create_db_pool (with codec) or init=callback."""
        path = _SERVICES_DIR / rel_path
        if not path.exists():
            pytest.skip(f"{rel_path} not found")
        content = path.read_text()

        has_shared = "create_db_pool" in content
        has_init_callback = "init=" in content and "set_type_codec" in content
        has_codec_import = "from anveshak.db import" in content and "create_db_pool" in content

        assert has_shared or has_init_callback or has_codec_import, (
            f"{service} ({rel_path}) creates asyncpg pool without JSONB codec. "
            f"Use 'from anveshak.db import create_db_pool' or add init=_init_connection."
        )


class TestNoUnsafeJsonLoads:
    """No bare json.loads(row[...]) without isinstance(str) guard.

    After JSONB codec is enabled, JSONB columns arrive as dict.
    json.loads(dict) raises TypeError. Code that catches TypeError
    in except block silently loses data.
    """

    def test_no_bare_json_loads_on_db_row_fields(self):
        """json.loads() on DB row fields must have isinstance(str) guard.

        Only checks patterns that access asyncpg row results:
        - json.loads(row["field"])
        - json.loads(latest["field"])
        - json.loads(report["field"])
        - json.loads(snapshot) where snapshot = row.get(...)

        Ignores json.loads on LLM output, file reads, base64 — not JSONB.
        """
        # Pattern: json.loads(row["..."])  or  json.loads(varname)
        # where varname was assigned from row["..."] within 5 lines
        row_access = re.compile(
            r"""json\.loads\(\s*(?:row|latest|report|current|source|topic|r)\s*\["""
        )
        violations = []

        for py_file in _SERVICES_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            lines = py_file.read_text(errors="ignore").splitlines()

            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if not row_access.search(stripped):
                    continue

                # Check for isinstance(str) guard within 4 lines before
                window = "\n".join(lines[max(0, i - 4) : i + 1])
                has_guard = "isinstance(" in window and "str)" in window

                # Accept ternary: json.loads(x) if isinstance(x, str) else x
                if "if isinstance(" in stripped and "str)" in stripped:
                    continue

                if not has_guard:
                    rel = py_file.relative_to(_SERVICES_DIR)
                    violations.append(f"{rel}:{i + 1}: {stripped[:120]}")

        assert not violations, (
            "Found json.loads() on DB row fields without isinstance(str) guard "
            "(will lose data after JSONB codec enabled):\n" + "\n".join(violations)
        )
