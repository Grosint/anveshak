"""Settings for the Source credibility rubric - issue #51.

A separate settings class rather than a field on a service settings object,
because the rubric is read by the API when a Source is created, by the
corpus importer, and by the script that applies a baseline to Sources that
already exist. None of those owns it.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class SourceRubricSettings(BaseSettings):
    """Path to the versioned rubric file the customer owns."""

    source_rubric_path: str = "/workspace/infra/configs/credibility/source_rubric.yaml"

    model_config = {"env_prefix": "", "case_sensitive": False, "extra": "ignore"}
