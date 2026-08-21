"""Unit tests for consistent DB pool sizes — LOW-20.

All services must use min_size=2 for connection pooling.
Reporter was the outlier at min_size=1.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

# All service files that create asyncpg pools
_POOL_FILES = [
    Path("services/scraper/anveshak/scraper/jobs.py"),
    Path("services/scraper/anveshak/scraper/main.py"),
    Path("services/analyst/anveshak/analyst/jobs.py"),
    Path("services/social/anveshak/social/jobs.py"),
    Path("services/vision/anveshak/vision/db/__init__.py"),
    Path("services/reporter/anveshak/reporter/db/__init__.py"),
]


class TestPoolSizeConsistency:
    @pytest.mark.parametrize("filepath", _POOL_FILES, ids=lambda p: p.parts[-1])
    def test_min_size_is_two(self, filepath):
        """Every create_pool call must use min_size=2."""
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")
        source = filepath.read_text()
        # Find all create_pool calls with min_size
        matches = re.findall(r"min_size\s*=\s*(\d+)", source)
        for val in matches:
            assert int(val) == 2, f"{filepath}: min_size={val}, expected 2"
