"""LLM provider abstraction with a hard cloud guard.

Architectural rule 10 forbids a cloud LLM call with real data. ADR 0002 makes
that structural rather than procedural: cloud access is off by default and a
production environment refuses it outright rather than warning.

Every caller goes through :func:`generate`. No service module names a provider
or a provider URL; both come from settings.
"""

from .provider import (
    CloudProviderRefusedError,
    LLMProviderSettings,
    describe_provider,
    generate,
    log_provider_startup,
    payload_hash,
    resolve_provider,
)

__all__ = [
    "CloudProviderRefusedError",
    "LLMProviderSettings",
    "describe_provider",
    "generate",
    "log_provider_startup",
    "payload_hash",
    "resolve_provider",
]
