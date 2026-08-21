"""Unit tests for snowball discovery — outbound URL extraction with frequency."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _link_row(source_url, outbound_url):
    """Simulate an asyncpg row from SQL_OUTBOUND_LINKS_FREQ."""
    return {"outbound_url": outbound_url, "source_url": source_url}


def _freq_row(domain, citation_count):
    """Simulate an asyncpg row from the frequency query."""
    return {"domain": domain, "citation_count": citation_count}


# ---------------------------------------------------------------------------
# Snowball extraction logic
# ---------------------------------------------------------------------------


async def test_snowball_extracts_domains_from_urls():
    """extract_domains_with_frequency returns domain + count."""
    from anveshak.analyst.discovery import extract_domains_with_frequency

    link_rows = [
        _link_row("https://source1.com/article", "https://example.com/page1"),
        _link_row("https://source2.com/article", "https://example.com/page2"),
        _link_row("https://source1.com/article", "https://other.org/news"),
    ]
    result = extract_domains_with_frequency(link_rows)
    assert result["example.com"] == 2
    assert result["other.org"] == 1


async def test_snowball_excludes_existing_sources():
    """filter_existing_domains removes already-registered sources."""
    from anveshak.analyst.discovery import filter_existing_domains

    domain_counts = {
        "example.com": 5,
        "registered.org": 3,
        "newsite.net": 2,
    }
    existing = {"registered.org"}
    result = filter_existing_domains(domain_counts, existing)
    assert "registered.org" not in result
    assert result["example.com"] == 5
    assert result["newsite.net"] == 2


async def test_snowball_sorts_by_frequency():
    """sorted_suggestions returns list sorted by citation_count DESC."""
    from anveshak.analyst.discovery import sorted_suggestions

    domain_counts = {
        "low.com": 1,
        "high.com": 10,
        "medium.com": 5,
    }
    result = sorted_suggestions(domain_counts)
    assert result[0] == ("high.com", 10)
    assert result[1] == ("medium.com", 5)
    assert result[2] == ("low.com", 1)


async def test_snowball_handles_malformed_urls():
    """extract_domains_with_frequency skips malformed URLs gracefully."""
    from anveshak.analyst.discovery import extract_domains_with_frequency

    link_rows = [
        _link_row("https://source1.com/article", "not-a-url"),
        _link_row("https://source1.com/article", "https://valid.com/page"),
        _link_row("https://source1.com/article", ""),
    ]
    result = extract_domains_with_frequency(link_rows)
    assert "valid.com" in result
    assert "not-a-url" not in result


# ---------------------------------------------------------------------------
# Snowball job function
# ---------------------------------------------------------------------------


async def test_discover_snowball_sources_upserts(mock_conn):
    """discover_snowball_sources must upsert results into discovered_sources."""
    from anveshak.analyst.discovery import discover_snowball_sources

    # Mock: topic with active sources
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock outbound links
    mock_conn.fetch = AsyncMock(
        side_effect=[
            # First call: SQL_OUTBOUND_LINKS
            [
                _link_row("https://src.com/article", "https://newsite.com/page1"),
                _link_row("https://src.com/article2", "https://newsite.com/page2"),
            ],
            # Second call: SQL_EXISTING_SOURCE_URLS
            [{"url_or_handle": "https://registered.com"}],
        ]
    )
    mock_conn.execute = AsyncMock()

    count = await discover_snowball_sources(mock_pool, "topic-1")
    assert count >= 1
    # Verify upsert was called
    assert mock_conn.execute.call_count >= 1


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    return conn
