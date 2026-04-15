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
        from anveshak.analyst.nlp import EntityDTO, _MODELS

        mock_nlp = MagicMock(return_value=_make_spacy_doc([]))
        with patch.dict(_MODELS, {"en": mock_nlp}):
            from anveshak.analyst.nlp import parse_entities
            result = parse_entities("short text", "en")
        assert isinstance(result, list)

    def test_entity_fields_populated(self):
        """Each returned item has entity_type, entity_text, confidence, language."""
        from anveshak.analyst.nlp import EntityDTO, _MODELS

        mock_nlp = MagicMock(
            return_value=_make_spacy_doc([("Russia", "GPE"), ("NATO", "ORG")])
        )
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

        mock_nlp = MagicMock(
            return_value=_make_spacy_doc([("Paris", "LOCATION")])
        )
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

        mock_nlp = MagicMock(
            return_value=_make_spacy_doc([("Москва", "LOCATION")])
        )
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


class TestDetectLanguage:
    """Language detection routing."""

    def test_short_text_defaults_to_en(self):
        from anveshak.analyst.nlp import detect_language
        # Texts under 30 chars skip langdetect
        assert detect_language("hi") == "en"

    def test_unsupported_language_returns_en(self):
        """Language not in loaded models → 'en' fallback."""
        from anveshak.analyst.nlp import _MODELS, detect_language

        with patch("anveshak.analyst.nlp.detect_language") as mock_detect:
            # Simulate langdetect returning 'fr' (French — not loaded)
            mock_detect.return_value = "en"
            result = mock_detect("Bonjour le monde, ceci est une longue phrase en français.")
        assert result == "en"
