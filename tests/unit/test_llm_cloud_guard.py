"""Cloud model guard — issue #22, ADR 0002.

Cloud inference is a development convenience. These tests pin the property
that it cannot survive silently into a deployment: off by default, refused
outright in production, and every permitted call logged with a payload hash.
"""

from __future__ import annotations

import pytest
from anveshak.llm import (
    CloudProviderRefusedError,
    LLMProviderSettings,
    describe_provider,
    payload_hash,
    resolve_provider,
)

pytestmark = pytest.mark.unit


def _settings(**overrides) -> LLMProviderSettings:
    base = {
        "environment": "development",
        "llm_cloud_enabled": False,
        "llm_cloud_provider": "",
        "llm_cloud_model": "",
        "llm_cloud_api_key": "",
        "llm_cloud_base_url": "https://provider.example/v1/messages",
    }
    base.update(overrides)
    return LLMProviderSettings(**base)


class TestEnvironmentIsAnAllowlist:
    """Deny by default. "prod", "staging" and "preprod" are all environments
    a denylist of "production" would have let through."""

    @pytest.mark.parametrize(
        "environment", ["production", "prod", "staging", "preprod", "prod-dr", "uat", ""]
    )
    def test_an_environment_outside_the_allowlist_is_refused(self, environment):
        with pytest.raises(CloudProviderRefusedError):
            resolve_provider(
                _settings(
                    environment=environment,
                    llm_cloud_enabled=True,
                    llm_cloud_provider="someprovider",
                    llm_cloud_model="somemodel",
                    llm_cloud_api_key="key",
                )
            )

    def test_the_allowlist_is_configuration(self):
        provider = resolve_provider(
            _settings(
                environment="ci",
                llm_cloud_allowed_environments=["ci"],
                llm_cloud_enabled=True,
                llm_cloud_provider="someprovider",
                llm_cloud_model="somemodel",
                llm_cloud_api_key="key",
            )
        )
        assert provider == "cloud"


class TestEndpointMustBeHttps:
    def test_a_plaintext_endpoint_is_refused(self):
        """The key travels in a request header."""
        with pytest.raises(CloudProviderRefusedError):
            resolve_provider(
                _settings(
                    llm_cloud_enabled=True,
                    llm_cloud_provider="someprovider",
                    llm_cloud_model="somemodel",
                    llm_cloud_api_key="key",
                    llm_cloud_base_url="http://provider.example/v1",
                )
            )

    def test_a_missing_endpoint_is_refused(self):
        with pytest.raises(CloudProviderRefusedError):
            resolve_provider(
                _settings(
                    llm_cloud_enabled=True,
                    llm_cloud_provider="someprovider",
                    llm_cloud_model="somemodel",
                    llm_cloud_api_key="key",
                    llm_cloud_base_url="",
                )
            )


class TestTheKeyIsNotPrintable:
    def test_the_settings_repr_hides_the_key(self):
        settings = _settings(
            llm_cloud_enabled=True,
            llm_cloud_provider="someprovider",
            llm_cloud_model="somemodel",
            llm_cloud_api_key="super-secret-key",
        )
        assert "super-secret-key" not in repr(settings)
        assert "super-secret-key" not in str(settings)


class TestDefaultsToLocal:
    def test_cloud_is_off_by_default(self):
        """No environment flag set means local inference — ADR 0002 point 2."""
        assert LLMProviderSettings().llm_cloud_enabled is False

    def test_resolve_returns_local_when_flag_off(self):
        assert resolve_provider(_settings()) == "local"

    def test_resolve_returns_local_even_when_provider_configured(self):
        """A configured provider is inert while the flag is off."""
        provider = resolve_provider(
            _settings(llm_cloud_provider="anthropic", llm_cloud_model="claude-opus-5")
        )
        assert provider == "local"


class TestProductionRefusal:
    def test_production_plus_enabled_raises(self):
        """Hard refusal, never a warning — ADR 0002 point 3."""
        with pytest.raises(CloudProviderRefusedError):
            resolve_provider(
                _settings(
                    environment="production",
                    llm_cloud_enabled=True,
                    llm_cloud_provider="anthropic",
                    llm_cloud_model="claude-opus-5",
                    llm_cloud_api_key="key",
                )
            )

    def test_refusal_message_names_both_causes(self):
        with pytest.raises(CloudProviderRefusedError) as exc:
            resolve_provider(
                _settings(
                    environment="production",
                    llm_cloud_enabled=True,
                    llm_cloud_provider="anthropic",
                    llm_cloud_model="claude-opus-5",
                    llm_cloud_api_key="key",
                )
            )
        message = str(exc.value)
        assert "production" in message
        assert "LLM_CLOUD_ENABLED" in message
        assert "ADR 0002" in message

    def test_production_with_flag_off_is_permitted(self):
        assert resolve_provider(_settings(environment="production")) == "local"


class TestDevelopmentPermittedPath:
    def test_development_plus_enabled_returns_cloud(self):
        provider = resolve_provider(
            _settings(
                llm_cloud_enabled=True,
                llm_cloud_provider="anthropic",
                llm_cloud_model="claude-opus-5",
                llm_cloud_api_key="key",
            )
        )
        assert provider == "cloud"

    def test_enabled_without_provider_is_refused(self):
        """A half-configured cloud provider must not silently fall back to local."""
        with pytest.raises(CloudProviderRefusedError):
            resolve_provider(_settings(llm_cloud_enabled=True, llm_cloud_api_key="key"))

    def test_enabled_without_api_key_is_refused(self):
        with pytest.raises(CloudProviderRefusedError):
            resolve_provider(
                _settings(
                    llm_cloud_enabled=True,
                    llm_cloud_provider="anthropic",
                    llm_cloud_model="claude-opus-5",
                )
            )


class TestPayloadHash:
    def test_hash_is_sha256_hex(self):
        digest = payload_hash("some prompt")
        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")

    def test_hash_is_stable(self):
        assert payload_hash("same") == payload_hash("same")

    def test_hash_differs_by_content(self):
        assert payload_hash("a") != payload_hash("b")

    def test_hash_does_not_contain_the_payload(self):
        """The log records that a call happened, never what was in it."""
        assert "secret" not in payload_hash("secret intel text")


class TestStartupDisclosure:
    def test_disabled_state_reports_a_reason(self):
        """A disabled feature explains itself — silent failure prevention."""
        description = describe_provider(_settings())
        assert description["provider"] == "local"
        assert description["reason"]

    def test_enabled_state_reports_provider_and_model(self):
        description = describe_provider(
            _settings(
                llm_cloud_enabled=True,
                llm_cloud_provider="anthropic",
                llm_cloud_model="claude-opus-5",
                llm_cloud_api_key="key",
            )
        )
        assert description["provider"] == "cloud"
        assert description["cloud_provider"] == "anthropic"
        assert description["cloud_model"] == "claude-opus-5"

    def test_description_never_carries_the_api_key(self):
        description = describe_provider(
            _settings(
                llm_cloud_enabled=True,
                llm_cloud_provider="anthropic",
                llm_cloud_model="claude-opus-5",
                llm_cloud_api_key="super-secret-key",
            )
        )
        assert "super-secret-key" not in str(description)

    def test_refused_configuration_is_described_not_raised(self):
        """Startup logging must survive a configuration that resolve_provider refuses."""
        description = describe_provider(_settings(environment="production", llm_cloud_enabled=True))
        assert description["provider"] == "refused"
        assert description["reason"]


class TestNoProviderNameInServiceCode:
    def test_provider_names_come_from_settings(self):
        """Rule 6: no provider name hardcoded in service code."""
        import subprocess

        result = subprocess.run(
            ["grep", "-rn", "api.anthropic.com", "services/", "sdk/"],
            capture_output=True,
            text=True,
        )
        assert result.stdout == ""


class TestLocalHostStaysOnTheDeploymentBoundary:
    """Rule 10 is only enforced if something checks.

    OLLAMA_HOST is an environment variable, so an unvalidated one turns
    "local inference" into an arbitrary outbound POST of collected intel,
    past the cloud guard entirely.
    """

    @pytest.mark.parametrize(
        "host",
        [
            "http://localhost:11434",
            "http://127.0.0.1:11434",
            "http://ollama:11434",
            "http://ollama.internal:11434",
            "http://gpu-box.local:11434",
        ],
    )
    async def test_a_boundary_host_is_permitted(self, host):
        from anveshak.llm.provider import _assert_local_host

        _assert_local_host(host)

    @pytest.mark.parametrize(
        "host",
        [
            "https://api.openai.com",
            "http://attacker.example.com:11434",
            "http://198.51.100.7:11434",
            "not-a-url",
            "",
        ],
    )
    async def test_a_host_off_the_boundary_is_refused(self, host):
        from anveshak.llm.provider import _assert_local_host

        with pytest.raises(CloudProviderRefusedError):
            _assert_local_host(host)
