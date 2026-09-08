"""Settings for the concern taxonomy — issue #36.

A separate settings class rather than a field on a service settings object,
because the taxonomy is shared by the analyst and the API and neither owns
it.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class ConcernSettings(BaseSettings):
    """Path to the versioned taxonomy file the customer owns."""

    concern_taxonomy_path: str = "/workspace/infra/configs/taxonomies/concern.yaml"

    model_config = {"env_prefix": "", "case_sensitive": False, "extra": "ignore"}
