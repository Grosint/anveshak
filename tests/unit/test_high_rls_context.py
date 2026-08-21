"""Unit tests for RLS context — HIGH-7.

set_org_context() exists but is dead code. Decision: remove it.
The codebase uses application-level verify_topic_access() consistently.
Dead security code gives false confidence. Test that it's gone.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestSetOrgContextRemoved:
    """set_org_context must be removed — dead code that misleads."""

    def test_set_org_context_not_exported(self):
        """pool.py must NOT export set_org_context — it was dead code."""
        import anveshak.api.db.pool as pool_mod

        assert not hasattr(pool_mod, "set_org_context"), (
            "set_org_context is dead code — remove it from pool.py"
        )
