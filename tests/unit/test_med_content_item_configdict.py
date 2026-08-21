"""Unit tests for ContentItem explicit ConfigDict — MED-19.

ContentItem must have explicit model_config = ConfigDict(strict=True)
per AGENTS.md rules, not just inherit it from AuditedModel.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestContentItemExplicitConfigDict:
    def test_content_item_has_explicit_model_config(self):
        """ContentItem must declare model_config explicitly, not just inherit."""
        import inspect

        from anveshak.models.content import ContentItem

        # Check the source code of the class itself (not parent)
        source = inspect.getsource(ContentItem)
        assert "model_config" in source, (
            "ContentItem must have explicit model_config = ConfigDict(strict=True)"
        )

    def test_content_item_is_strict(self):
        """ContentItem must be in strict mode."""
        from anveshak.models.content import ContentItem

        config = ContentItem.model_config
        assert config.get("strict") is True, "ContentItem.model_config must have strict=True"
