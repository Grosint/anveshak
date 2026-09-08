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
import json
from typing import Any

import httpx
import structlog
from pydantic import SecretStr
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
    # SecretStr so the key does not appear in a repr of this object. A
    # structlog exception renderer, a pydantic ValidationError, or a later
    # log.error(settings=...) would otherwise print it verbatim.
    llm_cloud_api_key: SecretStr = SecretStr("")
    llm_cloud_base_url: str = ""
    llm_cloud_timeout_s: int = 120
    llm_cloud_max_tokens: int = 2048
    # Header the provider expects the key in, and any extra headers it
    # requires, as a JSON object. Both are configuration so that no provider
    # dialect is written into this module.
    llm_cloud_auth_header: str = "x-api-key"
    llm_cloud_extra_headers: str = ""

    # Environments where cloud inference is permitted at all. An allowlist,
    # never a denylist: "prod", "staging", "preprod" and "prod-dr" are all
    # environments a denylist of "production" would have let through.
    llm_cloud_allowed_environments: list[str] = ["development", "test", "local"]

    model_config = {"env_prefix": "", "case_sensitive": False, "extra": "ignore"}


def payload_hash(payload: str) -> str:
    """SHA-256 of an outbound payload.

    Logged with every cloud call so an auditor can prove what was sent without
    the audit log becoming a second copy of the data.
    """
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _refusal_reason(settings: LLMProviderSettings) -> str | None:
    """Return why cloud access is refused, or None when it is permitted.

    Only called once the flag is on. Deny by default at every step: an
    unrecognised environment, an incomplete configuration, or a non-HTTPS
    endpoint all refuse rather than proceed.
    """
    environment = settings.environment.strip().lower()
    allowed = {name.strip().lower() for name in settings.llm_cloud_allowed_environments}
    if environment not in allowed:
        return (
            f"LLM_CLOUD_ENABLED is true in environment {environment!r}, which is "
            f"not in LLM_CLOUD_ALLOWED_ENVIRONMENTS. Cloud inference is a "
            "development-only convenience; intel data never leaves the "
            "deployment boundary. See ADR 0002."
        )
    if not settings.llm_cloud_provider:
        return "LLM_CLOUD_ENABLED is true but LLM_CLOUD_PROVIDER is not set"
    if not settings.llm_cloud_model:
        return "LLM_CLOUD_ENABLED is true but LLM_CLOUD_MODEL is not set"
    if not settings.llm_cloud_api_key.get_secret_value():
        return "LLM_CLOUD_ENABLED is true but LLM_CLOUD_API_KEY is not set"
    if not settings.llm_cloud_base_url:
        return "LLM_CLOUD_ENABLED is true but LLM_CLOUD_BASE_URL is not set"
    if not settings.llm_cloud_base_url.lower().startswith("https://"):
        return (
            "LLM_CLOUD_BASE_URL must be https. The API key travels in a "
            "request header, and a plaintext endpoint puts it on the wire."
        )
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


async def _generate_cloud(
    prompt: str,
    settings: LLMProviderSettings,
    max_tokens: int | None = None,
) -> str:
    """POST to the configured cloud provider.

    The endpoint, the auth header name and any extra headers are all
    configuration, so no provider name, URL or dialect is written here.
    """
    digest = payload_hash(prompt)
    log.info(
        "llm.cloud_call",
        provider=settings.llm_cloud_provider,
        model=settings.llm_cloud_model,
        payload_sha256=digest,
        payload_chars=len(prompt),
    )

    # One auth header, named by configuration. Sending the key in two
    # headers doubles its exposure for no benefit.
    headers = {
        "content-type": "application/json",
        settings.llm_cloud_auth_header: settings.llm_cloud_api_key.get_secret_value(),
    }
    headers.update(_extra_headers(settings))

    body = {
        "model": settings.llm_cloud_model,
        "max_tokens": max_tokens or settings.llm_cloud_max_tokens,
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


def _extra_headers(settings: LLMProviderSettings) -> dict[str, str]:
    """Parse LLM_CLOUD_EXTRA_HEADERS, a JSON object, into request headers.

    A provider that needs an API version header states it here rather than
    having its dialect hardcoded in this module. A malformed value is logged
    and dropped rather than crashing the call, because the headers are
    additive and the auth header is set separately.
    """
    raw = settings.llm_cloud_extra_headers.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("llm.extra_headers_invalid", error=str(exc))
        return {}
    if not isinstance(parsed, dict):
        log.warning("llm.extra_headers_not_an_object")
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


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
    max_tokens: int | None = None,
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
        # The same job must not produce a 512-token answer locally and a
        # 2048-token answer in cloud, so the caller's budget carries across.
        budget = max_tokens
        if budget is None and local_options:
            raw_budget = local_options.get("num_predict")
            budget = int(raw_budget) if isinstance(raw_budget, int) else None
        return await _generate_cloud(prompt, effective, max_tokens=budget)

    return await _generate_local(
        prompt,
        model=local_model,
        host=local_host,
        timeout_s=local_timeout_s,
        options=local_options,
    )
