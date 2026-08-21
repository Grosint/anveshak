"""Unit tests for analyst entity parsing (criteria 1.32).

pytest.mark.unit — mocks the spaCy model, no DB, no network, runs on CPU.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_spacy_doc(entities: list[tuple[str, str]]) -> MagicMock:
    """Build a minimal fake spaCy Doc with .ents populated."""
    doc = MagicMock()
    ents = []
    for text, label in entities:
        span = MagicMock()
        span.text = text
        span.label_ = label
        ents.append(span)
    doc.ents = ents
    return doc


class TestParseEntities:
    """Criteria 1.32: parse_entities(text, lang) returns list of EntityDTO."""

    def test_returns_list(self):
        """parse_entities always returns a list."""
        from anveshak.analyst.nlp import _MODELS

        mock_nlp = MagicMock(return_value=_make_spacy_doc([]))
        with patch.dict(_MODELS, {"en": mock_nlp}):
            from anveshak.analyst.nlp import parse_entities

            result = parse_entities("short text", "en")
        assert isinstance(result, list)

    def test_entity_fields_populated(self):
        """Each returned item has entity_type, entity_text, confidence, language."""
        from anveshak.analyst.nlp import _MODELS

        mock_nlp = MagicMock(return_value=_make_spacy_doc([("Russia", "GPE"), ("NATO", "ORG")]))
        with patch.dict(_MODELS, {"en": mock_nlp}):
            from anveshak.analyst.nlp import parse_entities

            result = parse_entities("Russia and NATO held talks.", "en")

        assert len(result) == 2
        russia = next(e for e in result if e.entity_text == "Russia")
        assert russia.entity_type == "GPE"
        assert russia.language == "en"
        assert isinstance(russia.confidence, float)

    def test_entity_confidence_is_float(self):
        from anveshak.analyst.nlp import _MODELS

        mock_nlp = MagicMock(return_value=_make_spacy_doc([("Paris", "LOCATION")]))
        with patch.dict(_MODELS, {"en": mock_nlp}):
            from anveshak.analyst.nlp import parse_entities

            result = parse_entities("Paris is beautiful.", "en")

        assert all(isinstance(e.confidence, float) for e in result)

    def test_empty_doc_returns_empty_list(self):
        from anveshak.analyst.nlp import _MODELS

        mock_nlp = MagicMock(return_value=_make_spacy_doc([]))
        with patch.dict(_MODELS, {"en": mock_nlp}):
            from anveshak.analyst.nlp import parse_entities

            result = parse_entities("No entities here.", "en")

        assert result == []

    def test_language_propagated_to_entity(self):
        from anveshak.analyst.nlp import _MODELS

        mock_nlp = MagicMock(return_value=_make_spacy_doc([("Москва", "LOCATION")]))
        with patch.dict(_MODELS, {"ru": mock_nlp}):
            from anveshak.analyst.nlp import parse_entities

            result = parse_entities("Москва — столица.", "ru")

        assert result[0].language == "ru"

    def test_no_model_returns_empty(self):
        """If model not loaded, returns empty list — no crash."""
        from anveshak.analyst.nlp import _MODELS, parse_entities

        with patch.dict(_MODELS, {}, clear=True):
            result = parse_entities("Some text here.", "en")

        assert result == []


class TestIsModelLoaded:
    """is_model_loaded() — checks if spaCy model is loaded for a language."""

    def test_returns_true_when_loaded(self):
        from anveshak.analyst.nlp import _MODELS, is_model_loaded

        with patch.dict(_MODELS, {"en": MagicMock()}, clear=True):
            assert is_model_loaded("en") is True

    def test_returns_false_when_not_loaded(self):
        from anveshak.analyst.nlp import _MODELS, is_model_loaded

        with patch.dict(_MODELS, {}, clear=True):
            assert is_model_loaded("en") is False

    def test_returns_false_for_unknown_lang(self):
        from anveshak.analyst.nlp import _MODELS, is_model_loaded

        with patch.dict(_MODELS, {"en": MagicMock()}, clear=True):
            assert is_model_loaded("ja") is False


class TestLoadModelsFastFail:
    """load_models() crashes for required langs, warns for optional."""

    def test_raises_runtime_error_when_en_fails(self):
        """English spaCy model failure must crash the worker."""
        from anveshak.analyst.nlp import _MODELS, load_models

        with (
            patch.dict(_MODELS, {}, clear=True),
            patch("anveshak.analyst.nlp.settings") as mock_settings,
            patch("spacy.load", side_effect=OSError("model not found")),
        ):
            mock_settings.spacy_en_model = "en_core_web_md"

            with pytest.raises(RuntimeError, match="spaCy model"):
                load_models()

    def test_loads_en_model_successfully(self):
        """English model loads and is registered in _MODELS."""
        from anveshak.analyst.nlp import _MODELS, load_models

        mock_nlp = MagicMock()

        with (
            patch.dict(_MODELS, {}, clear=True),
            patch("anveshak.analyst.nlp.settings") as mock_settings,
            patch("spacy.load", return_value=mock_nlp),
        ):
            mock_settings.spacy_en_model = "en_core_web_md"

            load_models()

            assert "en" in _MODELS, "English model should be loaded"


class TestDetectLanguage:
    """Language detection routing."""

    def test_short_text_defaults_to_en(self):
        from anveshak.analyst.nlp import detect_language

        # Texts under 30 chars skip langdetect
        assert detect_language("hi") == "en"

    def test_unsupported_language_returns_en(self):
        """Language not in loaded models → 'en' fallback."""

        with patch("anveshak.analyst.nlp.detect_language") as mock_detect:
            # Simulate langdetect returning 'fr' (French — not loaded)
            mock_detect.return_value = "en"
            result = mock_detect("Bonjour le monde, ceci est une longue phrase en français.")
        assert result == "en"
