"""Provider selection and the cloud guard. See ADR 0002.

The guard has one job: a development convenience must not survive silently
into a deployment. It does that with three properties.

1. ``LLM_CLOUD_ENABLED`` defaults to false, so nothing reaches a cloud
   provider unless someone set it deliberately.
2. ``ENVIRONMENT=production`` together with the flag on raises rather than
   warns, so a misconfiguration stops a deployment instead of degrading into
   a data leak.
3. A half-configured cloud provider is refused too. Falling back to local on
   a missing key would be exactly the silent degradation the rest of this
   codebase spends its effort preventing.
"""

from __future__ import annotations

import hashlib
from typing import Any

import httpx
import structlog
from pydantic_settings import BaseSettings

log = structlog.get_logger(__name__)

PROVIDER_LOCAL = "local"
PROVIDER_CLOUD = "cloud"
PROVIDER_REFUSED = "refused"


class CloudProviderRefusedError(RuntimeError):
    """Cloud inference was requested where it is not permitted."""


class LLMProviderSettings(BaseSettings):
    """Provider configuration. Every value is an environment variable.

    No provider name, model name, or endpoint appears in service code, which
    is architectural rule 6 applied to inference as well as to hardware.
    """

    # Matches the ENVIRONMENT variable the logging setup already reads.
    environment: str = "production"

    llm_cloud_enabled: bool = False
    llm_cloud_provider: str = ""
    llm_cloud_model: str = ""
    llm_cloud_api_key: str = ""
    llm_cloud_base_url: str = ""
    llm_cloud_timeout_s: int = 120

    model_config = {"env_prefix": "", "case_sensitive": False, "extra": "ignore"}


def payload_hash(payload: str) -> str:
    """SHA-256 of an outbound payload.

    Logged with every cloud call so an auditor can prove what was sent without
    the audit log becoming a second copy of the data.
    """
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _refusal_reason(settings: LLMProviderSettings) -> str | None:
    """Return why cloud access is refused, or None when it is permitted.

    Only called once the flag is on.
    """
    if settings.environment.strip().lower() == "production":
        return (
            "LLM_CLOUD_ENABLED is true in a production environment. "
            "Cloud inference is a development-only convenience; intel data "
            "never leaves the deployment boundary. See ADR 0002."
        )
    if not settings.llm_cloud_provider:
        return "LLM_CLOUD_ENABLED is true but LLM_CLOUD_PROVIDER is not set"
    if not settings.llm_cloud_model:
        return "LLM_CLOUD_ENABLED is true but LLM_CLOUD_MODEL is not set"
    if not settings.llm_cloud_api_key:
        return "LLM_CLOUD_ENABLED is true but LLM_CLOUD_API_KEY is not set"
    return None


def resolve_provider(settings: LLMProviderSettings) -> str:
    """Return ``"local"`` or ``"cloud"``, or raise.

    Raises:
        CloudProviderRefusedError: cloud was requested in production, or
            requested with an incomplete configuration.
    """
    if not settings.llm_cloud_enabled:
        return PROVIDER_LOCAL

    reason = _refusal_reason(settings)
    if reason is not None:
        raise CloudProviderRefusedError(reason)

    return PROVIDER_CLOUD


def describe_provider(settings: LLMProviderSettings) -> dict[str, Any]:
    """Describe the resolved provider for a startup log line.

    Never raises, because startup disclosure must survive a configuration that
    :func:`resolve_provider` refuses. A refused configuration is reported as
    ``provider="refused"`` with its reason.
    """
    if not settings.llm_cloud_enabled:
        return {
            "provider": PROVIDER_LOCAL,
            "reason": "LLM_CLOUD_ENABLED is not set, using local inference",
        }

    reason = _refusal_reason(settings)
    if reason is not None:
        return {"provider": PROVIDER_REFUSED, "reason": reason}

    return {
        "provider": PROVIDER_CLOUD,
        "reason": "LLM_CLOUD_ENABLED is set in a non-production environment",
        "cloud_provider": settings.llm_cloud_provider,
        "cloud_model": settings.llm_cloud_model,
    }


def log_provider_startup(settings: LLMProviderSettings, service: str) -> None:
    """Log which provider is in use and why, at INFO, at startup.

    An analyst debugging a missing output at 2am needs to know why a feature
    is off, not just see no output.
    """
    description = describe_provider(settings)
    log.info("llm.provider_selected", service=service, **description)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def _generate_local(
    prompt: str,
    *,
    model: str,
    host: str,
    timeout_s: int,
    options: dict[str, Any] | None = None,
) -> str:
    """POST to Ollama /api/generate. Rule 10: host is localhost or internal."""
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
    if options:
        payload["options"] = options
    async with httpx.AsyncClient(timeout=float(timeout_s)) as client:
        response = await client.post(f"{host}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
    return data.get("response", "")


async def _generate_cloud(prompt: str, settings: LLMProviderSettings) -> str:
    """POST to the configured cloud provider.

    The endpoint is ``LLM_CLOUD_BASE_URL``. It is not derived from the provider
    name, so no provider URL is hardcoded here.
    """
    if not settings.llm_cloud_base_url:
        raise CloudProviderRefusedError(
            "LLM_CLOUD_ENABLED is true but LLM_CLOUD_BASE_URL is not set"
        )

    digest = payload_hash(prompt)
    log.info(
        "llm.cloud_call",
        provider=settings.llm_cloud_provider,
        model=settings.llm_cloud_model,
        payload_sha256=digest,
        payload_chars=len(prompt),
    )

    headers = {
        "x-api-key": settings.llm_cloud_api_key,
        "authorization": f"Bearer {settings.llm_cloud_api_key}",
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": settings.llm_cloud_model,
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=float(settings.llm_cloud_timeout_s)) as client:
        response = await client.post(settings.llm_cloud_base_url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()

    log.info(
        "llm.cloud_call_complete",
        provider=settings.llm_cloud_provider,
        model=settings.llm_cloud_model,
        payload_sha256=digest,
    )
    return _extract_completion(data)


def _extract_completion(data: dict[str, Any]) -> str:
    """Pull the completion text out of a provider response.

    Handles the two response shapes in common use without naming a provider:
    a ``content`` block list, and an OpenAI-style ``choices`` list.
    """
    content = data.get("content")
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content if isinstance(block, dict))

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") or {}
        return message.get("content", "")

    return data.get("response", "")


async def generate(
    prompt: str,
    *,
    local_model: str,
    local_host: str,
    local_timeout_s: int,
    local_options: dict[str, Any] | None = None,
    settings: LLMProviderSettings | None = None,
) -> str:
    """Generate a completion from the resolved provider.

    Raises:
        CloudProviderRefusedError: the configuration requests cloud inference
            where it is not permitted. Never falls back to local, because a
            silent fallback hides the misconfiguration this guard exists to
            surface.
    """
    effective = settings if settings is not None else LLMProviderSettings()
    provider = resolve_provider(effective)

    if provider == PROVIDER_CLOUD:
        return await _generate_cloud(prompt, effective)

    return await _generate_local(
        prompt,
        model=local_model,
        host=local_host,
        timeout_s=local_timeout_s,
        options=local_options,
    )
