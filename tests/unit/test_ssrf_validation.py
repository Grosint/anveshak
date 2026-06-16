"""Unit tests for SSRF validation on media URL downloads.

Critical fix: _download_page_media extracts URLs from HTML and downloads
them without validating that they point to external hosts. Internal
network IPs (Docker 172.28.x.x, localhost, metadata endpoints) must be
blocked.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestValidateExternalUrl:
    """validate_external_url must block private/internal/dangerous URLs."""

    def test_blocks_localhost(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("http://localhost/secret") is False

    def test_blocks_127_0_0_1(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("http://127.0.0.1:8080/admin") is False

    def test_blocks_ipv6_loopback(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("http://[::1]/admin") is False

    def test_blocks_docker_internal_network(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("http://172.28.0.5:5432/") is False

    def test_blocks_10_x_private_range(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("http://10.0.0.1/internal") is False

    def test_blocks_192_168_private_range(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("http://192.168.1.1/router") is False

    def test_blocks_169_254_link_local(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("http://169.254.169.254/latest/meta-data/") is False

    def test_blocks_cloud_metadata_hostname(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("http://metadata.google.internal/computeMetadata/v1/") is False

    def test_blocks_ftp_scheme(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("ftp://files.example.com/data.csv") is False

    def test_blocks_file_scheme(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("file:///etc/passwd") is False

    def test_blocks_0_0_0_0(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("http://0.0.0.0:8000/") is False

    def test_allows_valid_external_http(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("https://cdn.example.com/image.jpg") is True

    def test_allows_valid_external_https(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("https://images.reuters.com/photo.png") is True

    def test_blocks_empty_url(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("") is False

    def test_blocks_no_scheme(self):
        from anveshak.scraper.url_safety import validate_external_url

        assert validate_external_url("//example.com/image.jpg") is False
