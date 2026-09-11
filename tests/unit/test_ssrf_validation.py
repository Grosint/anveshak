"""Unit tests for SSRF validation on media URL downloads.

Critical fix: _download_page_media extracts URLs from HTML and downloads
them without validating that they point to external hosts. Internal
network IPs (Docker 172.28.x.x, localhost, metadata endpoints) must be
blocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestValidateExternalUrl:
    """validate_external_url must block private/internal/dangerous URLs."""

    def test_blocks_localhost(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("http://localhost/secret") is False

    def test_blocks_127_0_0_1(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("http://127.0.0.1:8080/admin") is False

    def test_blocks_ipv6_loopback(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("http://[::1]/admin") is False

    def test_blocks_docker_internal_network(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("http://172.28.0.5:5432/") is False

    def test_blocks_10_x_private_range(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("http://10.0.0.1/internal") is False

    def test_blocks_192_168_private_range(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("http://192.168.1.1/router") is False

    def test_blocks_169_254_link_local(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("http://169.254.169.254/latest/meta-data/") is False

    def test_blocks_cloud_metadata_hostname(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("http://metadata.google.internal/computeMetadata/v1/") is False

    def test_blocks_ftp_scheme(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("ftp://files.example.com/data.csv") is False

    def test_blocks_file_scheme(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("file:///etc/passwd") is False

    def test_blocks_0_0_0_0(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("http://0.0.0.0:8000/") is False

    def test_allows_valid_external_http(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("https://cdn.example.com/image.jpg") is True

    def test_allows_valid_external_https(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("https://images.reuters.com/photo.png") is True

    def test_blocks_empty_url(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("") is False

    def test_blocks_no_scheme(self):
        from anveshak.net.url_safety import validate_external_url

        assert validate_external_url("//example.com/image.jpg") is False


class TestResolvedHostValidation:
    """A hostname that resolves into the deployment network is not external.

    validate_external_url can only judge literal addresses and a name blocklist.
    A feed-supplied link naming a compose service - ollama, redis, postgres -
    passes it and reaches an internal port. Resolution is what settles it.
    """

    async def test_compose_service_name_resolving_to_private_ip_is_refused(self):
        from anveshak.net import url_safety

        with patch.object(url_safety, "_resolve_host", new=AsyncMock(return_value=["172.28.0.4"])):
            assert await url_safety.validate_external_url_resolved("http://ollama:11434/") is False

    async def test_public_host_is_allowed(self):
        from anveshak.net import url_safety

        with patch.object(
            url_safety, "_resolve_host", new=AsyncMock(return_value=["93.184.216.34"])
        ):
            assert (
                await url_safety.validate_external_url_resolved("https://outlet.example.in/a")
                is True
            )

    async def test_any_private_answer_refuses_the_whole_name(self):
        """A name answering with both a public and a private address is refused."""
        from anveshak.net import url_safety

        with patch.object(
            url_safety,
            "_resolve_host",
            new=AsyncMock(return_value=["93.184.216.34", "127.0.0.1"]),
        ):
            assert (
                await url_safety.validate_external_url_resolved("https://rebind.example/a") is False
            )

    async def test_unresolvable_host_is_refused(self):
        """Deny by default: a name we cannot resolve is not a name we fetch."""
        from anveshak.net import url_safety

        with patch.object(url_safety, "_resolve_host", new=AsyncMock(return_value=[])):
            assert await url_safety.validate_external_url_resolved("https://nx.example/a") is False

    async def test_literal_checks_still_apply_before_resolution(self):
        from anveshak.net import url_safety

        resolver = AsyncMock(return_value=["93.184.216.34"])
        with patch.object(url_safety, "_resolve_host", new=resolver):
            assert await url_safety.validate_external_url_resolved("file:///etc/passwd") is False
            assert resolver.await_count == 0

    async def test_unspecified_literal_address_is_refused(self):
        """:: routes to the local host and is not enumerated by the written-form check."""
        from anveshak.net import url_safety

        assert await url_safety.validate_external_url_resolved("http://[::]:8000/") is False
