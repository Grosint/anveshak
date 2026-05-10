"""RED phase — Phase 3 resilience tests.

Tests for:
  - OllamaCircuitBreaker: 3-state machine for reporter/Ollama calls
  - create_pool_with_retry: DB pool creation with exponential backoff
  - PDF detection in scraper: detect PDF URLs and extract text
  - Alertmanager compose config
  - Frontend export buttons

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ===================================================================
# 1. Ollama Circuit Breaker
# ===================================================================

class TestOllamaCircuitBreaker:
    """Reporter circuit breaker for Ollama LLM calls."""

    def test_class_exists(self):
        """OllamaCircuitBreaker must exist in reporter.circuit_breaker."""
        from services.reporter.anveshak.reporter.circuit_breaker import OllamaCircuitBreaker
        assert OllamaCircuitBreaker is not None

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self):
        """New circuit breaker starts in CLOSED state."""
        from services.reporter.anveshak.reporter.circuit_breaker import OllamaCircuitBreaker

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        cb = OllamaCircuitBreaker(redis, threshold=3, cooldown_s=120)

        state = await cb.get_state()
        assert state == "CLOSED"

    @pytest.mark.asyncio
    async def test_allows_call_when_closed(self):
        """Calls are allowed when circuit is CLOSED."""
        from services.reporter.anveshak.reporter.circuit_breaker import OllamaCircuitBreaker

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        cb = OllamaCircuitBreaker(redis, threshold=3, cooldown_s=120)

        assert await cb.allows_call() is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        """Circuit opens after N consecutive failures."""
        from services.reporter.anveshak.reporter.circuit_breaker import OllamaCircuitBreaker

        redis = AsyncMock()
        # Simulate: incr returns 3 (threshold reached)
        redis.incr = AsyncMock(return_value=3)
        redis.set = AsyncMock()

        cb = OllamaCircuitBreaker(redis, threshold=3, cooldown_s=120)
        await cb.record_failure()

        # Should have set opened_at key
        redis.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_blocks_call_when_open(self):
        """Calls are blocked when circuit is OPEN."""
        from services.reporter.anveshak.reporter.circuit_breaker import OllamaCircuitBreaker

        redis = AsyncMock()
        # 3 failures (>= threshold=3), opened recently
        redis.get = AsyncMock(side_effect=lambda k: "3" if "failures" in k else str(time.monotonic()))

        cb = OllamaCircuitBreaker(redis, threshold=3, cooldown_s=120)
        assert await cb.allows_call() is False

    @pytest.mark.asyncio
    async def test_half_open_after_cooldown(self):
        """Circuit transitions to HALF_OPEN after cooldown expires."""
        from services.reporter.anveshak.reporter.circuit_breaker import OllamaCircuitBreaker

        redis = AsyncMock()
        # 3 failures, opened long ago (cooldown expired)
        redis.get = AsyncMock(
            side_effect=lambda k: "3" if "failures" in k else str(time.monotonic() - 999)
        )

        cb = OllamaCircuitBreaker(redis, threshold=3, cooldown_s=120)
        state = await cb.get_state()
        assert state == "HALF_OPEN"

    @pytest.mark.asyncio
    async def test_success_resets_to_closed(self):
        """Recording success deletes failure counter and closes circuit."""
        from services.reporter.anveshak.reporter.circuit_breaker import OllamaCircuitBreaker

        redis = AsyncMock()
        redis.delete = AsyncMock()

        cb = OllamaCircuitBreaker(redis, threshold=3, cooldown_s=120)
        await cb.record_success()

        # Should delete both keys
        assert redis.delete.await_count == 2

    @pytest.mark.asyncio
    async def test_record_failure_uses_atomic_incr(self):
        """record_failure must use Redis INCR (atomic), not GET+SET."""
        from services.reporter.anveshak.reporter.circuit_breaker import OllamaCircuitBreaker

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=1)

        cb = OllamaCircuitBreaker(redis, threshold=3, cooldown_s=120)
        await cb.record_failure()

        redis.incr.assert_awaited_once()


# ===================================================================
# 2. DB Pool Retry
# ===================================================================

class TestCreatePoolWithRetry:
    """create_pool_with_retry must retry with exponential backoff."""

    def test_function_exists(self):
        """create_pool_with_retry must exist as importable function."""
        from services.api.anveshak.api.db.pool import create_pool_with_retry
        assert callable(create_pool_with_retry)

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        """If pool creation succeeds immediately, return the pool."""
        from services.api.anveshak.api.db.pool import create_pool_with_retry

        mock_pool = MagicMock()
        with patch("services.api.anveshak.api.db.pool.asyncpg") as mock_asyncpg:
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
            pool = await create_pool_with_retry(
                "postgresql://test:test@localhost/test",
                max_retries=3,
                backoff_base=0.01,
            )

        assert pool is mock_pool

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self):
        """If first attempt fails, retry until success."""
        from services.api.anveshak.api.db.pool import create_pool_with_retry

        mock_pool = MagicMock()
        with patch("services.api.anveshak.api.db.pool.asyncpg") as mock_asyncpg:
            mock_asyncpg.create_pool = AsyncMock(
                side_effect=[ConnectionError("refused"), mock_pool]
            )
            pool = await create_pool_with_retry(
                "postgresql://test:test@localhost/test",
                max_retries=3,
                backoff_base=0.01,
            )

        assert pool is mock_pool
        assert mock_asyncpg.create_pool.await_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """If all retries fail, raise the last exception."""
        from services.api.anveshak.api.db.pool import create_pool_with_retry

        with patch("services.api.anveshak.api.db.pool.asyncpg") as mock_asyncpg:
            mock_asyncpg.create_pool = AsyncMock(
                side_effect=ConnectionError("refused")
            )
            with pytest.raises(ConnectionError):
                await create_pool_with_retry(
                    "postgresql://test:test@localhost/test",
                    max_retries=2,
                    backoff_base=0.01,
                )

        assert mock_asyncpg.create_pool.await_count == 2


# ===================================================================
# 3. PDF Detection in Scraper
# ===================================================================

class TestScraperPDFDetection:
    """Scraper must detect PDF URLs and use fetch_pdf_text."""

    def test_is_pdf_url_function_exists(self):
        """is_pdf_url helper must exist in scraper fetch module."""
        from services.scraper.anveshak.scraper.fetch import is_pdf_url
        assert callable(is_pdf_url)

    def test_detects_pdf_extension(self):
        """URLs ending in .pdf should be detected."""
        from services.scraper.anveshak.scraper.fetch import is_pdf_url
        assert is_pdf_url("https://example.com/report.pdf") is True
        assert is_pdf_url("https://example.com/report.PDF") is True

    def test_rejects_non_pdf(self):
        """HTML URLs should not be detected as PDF."""
        from services.scraper.anveshak.scraper.fetch import is_pdf_url
        assert is_pdf_url("https://example.com/page.html") is False
        assert is_pdf_url("https://example.com/article") is False

    def test_detects_pdf_with_query_params(self):
        """PDF URLs with query params should still be detected."""
        from services.scraper.anveshak.scraper.fetch import is_pdf_url
        assert is_pdf_url("https://example.com/report.pdf?dl=1") is True


# ===================================================================
# 4. Reporter settings — circuit breaker config
# ===================================================================

class TestReporterCircuitBreakerSettings:
    """Reporter settings must include circuit breaker configuration."""

    def test_threshold_setting(self):
        """ollama_circuit_breaker_threshold must exist in settings."""
        from services.reporter.anveshak.reporter.settings import ReporterSettings
        s = ReporterSettings()
        assert hasattr(s, "ollama_circuit_breaker_threshold")
        assert isinstance(s.ollama_circuit_breaker_threshold, int)

    def test_cooldown_setting(self):
        """ollama_circuit_breaker_cooldown_s must exist in settings."""
        from services.reporter.anveshak.reporter.settings import ReporterSettings
        s = ReporterSettings()
        assert hasattr(s, "ollama_circuit_breaker_cooldown_s")
        assert isinstance(s.ollama_circuit_breaker_cooldown_s, int)


# ===================================================================
# 5. Alertmanager in compose
# ===================================================================

class TestAlertmanagerCompose:
    """Alertmanager must be in compose.yml for alert delivery."""

    def test_alertmanager_service_exists(self):
        """compose.yml must define an alertmanager service."""
        from pathlib import Path

        content = Path("infra/compose.yml").read_text()
        assert "alertmanager" in content.lower(), \
            "compose.yml must include an alertmanager service"

    def test_prometheus_alertmanager_config(self):
        """Prometheus config must reference alertmanager."""
        from pathlib import Path

        prom_cfg = Path("infra/configs/prometheus/prometheus.yml")
        if prom_cfg.exists():
            content = prom_cfg.read_text()
            assert "alertmanager" in content.lower(), \
                "prometheus.yml must reference alertmanager for alert routing"


# ===================================================================
# 6. Frontend export buttons
# ===================================================================

class TestFrontendExportButtons:
    """Frontend pages must have export button components."""

    def test_export_util_exists(self):
        """A shared export utility or hook must exist in frontend."""
        from pathlib import Path

        # Check for export-related files
        export_files = list(Path("frontend/src").rglob("*xport*"))
        assert len(export_files) > 0, \
            "Frontend must have export utility/hook (e.g., useExport.ts or ExportButton.tsx)"

    def test_content_feed_has_export(self):
        """ContentFeed page must reference export functionality."""
        from pathlib import Path

        # Find the content feed page
        candidates = list(Path("frontend/src").rglob("*ContentFeed*"))
        if not candidates:
            candidates = list(Path("frontend/src").rglob("*content*feed*"))
        assert len(candidates) > 0, "ContentFeed page must exist"

        content = candidates[0].read_text()
        assert "export" in content.lower(), \
            "ContentFeed must have export button/functionality"
