"""Unit tests for CORS header whitelist — HIGH-9.

allow_headers=["*"] must be replaced with specific allowed headers.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestCORSHeaderWhitelist:
    def test_cors_does_not_allow_wildcard_headers(self):
        """main.py must NOT use allow_headers=['*'] — whitelist specific headers."""
        import inspect
        from pathlib import Path

        # Read main.py source to check CORS config
        main_path = Path(
            inspect.getfile(__import__("anveshak.api.main", fromlist=["app"]))
        ).resolve()
        source = main_path.read_text()

        assert 'allow_headers=["*"]' not in source, (
            "CORS allow_headers must whitelist specific headers, not '*'"
        )
        assert "allow_headers=['*']" not in source, (
            "CORS allow_headers must whitelist specific headers, not '*'"
        )

    def test_cors_allows_authorization_header(self):
        """Authorization header must be in the CORS whitelist."""
        import inspect
        from pathlib import Path

        main_path = Path(
            inspect.getfile(__import__("anveshak.api.main", fromlist=["app"]))
        ).resolve()
        source = main_path.read_text()

        assert "Authorization" in source, "CORS allow_headers must include 'Authorization'"

    def test_cors_allows_content_type_header(self):
        """Content-Type header must be in the CORS whitelist."""
        import inspect
        from pathlib import Path

        main_path = Path(
            inspect.getfile(__import__("anveshak.api.main", fromlist=["app"]))
        ).resolve()
        source = main_path.read_text()

        assert "Content-Type" in source, "CORS allow_headers must include 'Content-Type'"
