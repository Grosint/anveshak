"""Unit tests for Redis port exposure documentation — LOW-22.

Dev compose exposes Redis on 6379. Must have a comment documenting
this is dev-only and prod uses k3s NetworkPolicy for isolation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

COMPOSE_PATH = Path("infra/compose.yml")


class TestRedisPortDocumentation:

    def test_redis_port_has_security_comment(self):
        """Redis port exposure must have a comment about dev-only usage."""
        content = COMPOSE_PATH.read_text()
        # Find the redis section and check for security/dev comment near ports
        lines = content.split("\n")
        in_redis = False
        found_port = False
        found_comment = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("redis:"):
                in_redis = True
            elif in_redis and stripped and not stripped.startswith("#") and not stripped.startswith("-") and ":" in stripped and not stripped.startswith("\""):
                # New service section
                if not stripped.startswith("-") and not stripped.startswith("test") and not stripped.startswith("command"):
                    pass  # still in redis subsection
            if in_redis and "6379" in line:
                found_port = True
                # Check surrounding lines for comment
                for j in range(max(0, i - 3), min(len(lines), i + 3)):
                    if "#" in lines[j] and ("dev" in lines[j].lower() or "prod" in lines[j].lower() or "security" in lines[j].lower() or "network" in lines[j].lower()):
                        found_comment = True
                break

        assert found_port, "Redis port 6379 not found in compose.yml"
        assert found_comment, (
            "Redis port 6379 exposed without security comment — "
            "add comment noting dev-only, prod uses k3s NetworkPolicy"
        )
