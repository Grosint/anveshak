"""Unit tests for the translation device setting — architectural rule 6.

Rule 6 forbids a hardcoded device string in service code. Every other model
loader in the analyst reads its device from settings (stance_device,
hostility_device), and the translation pipeline was the one that did not: it
passed device=-1 with a comment deferring the setting to "future". That made
the NLLB GPU upgrade in hardware.md impossible to reach by env var alone.

pytest.mark.unit — no DB, no network, no real ML models.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _reset_pipeline_cache() -> None:
    """The pipeline is a module-level singleton, so a test that builds one
    leaks into the next unless the cache is cleared first."""
    from anveshak.analyst import translation

    translation._pipeline = None


@pytest.fixture(autouse=True)
def _clean_pipeline():
    _reset_pipeline_cache()
    yield
    _reset_pipeline_cache()


class TestTranslationDeviceSetting:
    def test_setting_exists_and_defaults_to_cpu(self):
        from anveshak.analyst.settings import settings

        assert settings.translation_device == "cpu"

    def test_setting_reads_the_env_var(self, monkeypatch):
        from anveshak.analyst.settings import AnalystSettings

        monkeypatch.setenv("TRANSLATION_DEVICE", "cuda")
        assert AnalystSettings().translation_device == "cuda"


class TestPipelineHonoursTheSetting:
    """The device the pipeline is built with must come from the setting.

    Asserting on the keyword rather than on behaviour, because the alternative
    is loading a 2.4GB model, and a unit test never touches a real one.
    """

    def _build(self, device: str):
        from anveshak.analyst import translation

        fake_torch = MagicMock()
        fake_hf_pipeline = MagicMock(return_value=MagicMock())

        with patch.dict(
            sys.modules,
            {"torch": fake_torch, "transformers": MagicMock(pipeline=fake_hf_pipeline)},
        ):
            with patch.object(translation.settings, "translation_device", device):
                translation._get_pipeline()

        return fake_hf_pipeline

    def test_cpu_setting_reaches_the_pipeline(self):
        assert self._build("cpu").call_args.kwargs["device"] == "cpu"

    def test_cuda_setting_reaches_the_pipeline(self):
        assert self._build("cuda").call_args.kwargs["device"] == "cuda"

    def test_explicit_cuda_index_reaches_the_pipeline(self):
        """A multi-GPU host names the card, so 'cuda:1' must pass through
        unparsed rather than being collapsed to a boolean."""
        assert self._build("cuda:1").call_args.kwargs["device"] == "cuda:1"


class TestRuleSixHoldsInSource:
    """Grep-level guards. The keyword assertions above pass if someone
    reintroduces a literal alongside the setting, so pin the source too.

    Both modules, not just translation.py. download_models.py builds the same
    NLLB pipeline to pre-cache it, and a literal left there is the same rule 6
    violation: it is the module analyse-init runs, so a GPU deployment would
    pre-cache on CPU while the worker loads on GPU, with nothing raising.
    """

    @staticmethod
    def _source(module) -> str:
        from pathlib import Path

        return Path(module.__file__).read_text(encoding="utf-8")

    def test_translation_module_has_no_hardcoded_device_literal(self):
        import anveshak.analyst.translation as translation_module

        source = self._source(translation_module)
        assert "device=-1" not in source
        assert "device=settings.translation_device" in source

    def test_download_models_has_no_hardcoded_device_literal(self):
        import anveshak.analyst.download_models as download_models_module

        source = self._source(download_models_module)
        assert "device=-1" not in source

    def test_download_models_builds_nllb_on_the_configured_device(self):
        """It already reads stance_device and hostility_device. Translation
        was the one that did not, so the three must now agree."""
        import anveshak.analyst.download_models as download_models_module

        source = self._source(download_models_module)
        assert "device=settings.translation_device" in source
        assert "device=settings.stance_device" in source
        assert "device=settings.hostility_device" in source
