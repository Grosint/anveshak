"""Unit tests for multilingual NLP pipeline — translation, language detection, NER.

Tests cover:
  - Chinese language detection via langdetect
  - NLLB translation module (mocked — no real model loaded in unit tests)
  - needs_translation() routing logic
  - NER on translated English text
  - Embedding on translated English text
  - analyse_content job with translation wired in (fully mocked)
  - ContentItem model has translated_text / translation_model fields

pytest.mark.unit — no DB, no network, no real ML models.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CHINESE_TEXT = (
    "中国人民解放军在南海举行大规模军事演习，"
    "习近平主席视察了参演部队并发表重要讲话。"
    "此次演习被外界认为是针对台湾局势的重要信号。"
    "多国对此表示关注，美国国防部发言人在记者会上对演习规模表示关切，"
    "日本防卫省也发布了紧急声明。分析人士认为这将加剧地区紧张局势。"
)

EXPECTED_TRANSLATION = (
    "The Chinese People's Liberation Army held large-scale military exercises in the "
    "South China Sea. President Xi Jinping inspected the participating troops and "
    "delivered an important speech. The exercise is seen as an important signal "
    "regarding the Taiwan situation."
)


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

class TestDetectLanguageChinese:
    """langdetect correctly identifies Chinese text as 'zh' or 'zh-cn'."""

    def test_chinese_text_detected(self):
        """Long Chinese text must detect as a zh variant."""
        from langdetect import detect
        result = detect(CHINESE_TEXT)
        assert result.startswith("zh"), f"Expected zh*, got {result!r}"

    def test_short_text_defaults_to_en(self):
        """Texts shorter than _MIN_LANGDETECT_LEN fall back to 'en'."""
        from anveshak.analyst.nlp import _MODELS, detect_language
        # Inject a fake zh model so it's in _MODELS — avoids unsupported lang fallback
        _MODELS["zh"] = MagicMock()
        result = detect_language("短文")   # 2 chars — below minimum
        assert result == "en"
        del _MODELS["zh"]


# ---------------------------------------------------------------------------
# needs_translation() routing
# ---------------------------------------------------------------------------

class TestNeedsTranslation:

    def test_zh_needs_translation(self):
        from anveshak.analyst.translation import needs_translation
        assert needs_translation("zh") is True

    def test_zh_cn_needs_translation(self):
        from anveshak.analyst.translation import needs_translation
        assert needs_translation("zh-cn") is True

    def test_hi_needs_translation(self):
        from anveshak.analyst.translation import needs_translation
        assert needs_translation("hi") is True

    def test_ar_needs_translation(self):
        from anveshak.analyst.translation import needs_translation
        assert needs_translation("ar") is True

    def test_ur_needs_translation(self):
        from anveshak.analyst.translation import needs_translation
        assert needs_translation("ur") is True

    def test_ru_needs_translation(self):
        from anveshak.analyst.translation import needs_translation
        assert needs_translation("ru") is True

    def test_en_does_not_need_translation(self):
        from anveshak.analyst.translation import needs_translation
        assert needs_translation("en") is False

    def test_unknown_lang_does_not_need_translation(self):
        from anveshak.analyst.translation import needs_translation
        assert needs_translation("xx") is False


# ---------------------------------------------------------------------------
# translate_to_english() — mocked NLLB pipeline
# ---------------------------------------------------------------------------

class TestTranslateToEnglish:

    def test_successful_translation(self):
        """translate_to_english returns string when pipeline succeeds."""
        mock_output = [{"translation_text": EXPECTED_TRANSLATION}]
        with patch("anveshak.analyst.translation._get_pipeline") as mock_get:
            mock_pipe = MagicMock(return_value=mock_output)
            mock_get.return_value = mock_pipe

            from anveshak.analyst.translation import translate_to_english
            result = translate_to_english(CHINESE_TEXT, "zh")

        assert result == EXPECTED_TRANSLATION
        mock_pipe.assert_called_once()
        # Verify correct NLLB language codes passed
        call_kwargs = mock_pipe.call_args
        assert call_kwargs.kwargs.get("src_lang") == "zho_Hans"
        assert call_kwargs.kwargs.get("tgt_lang") == "eng_Latn"

    def test_translation_failure_returns_none(self):
        """translate_to_english returns None when pipeline raises."""
        with patch("anveshak.analyst.translation._get_pipeline") as mock_get:
            mock_pipe = MagicMock(side_effect=RuntimeError("model error"))
            mock_get.return_value = mock_pipe

            from anveshak.analyst.translation import translate_to_english
            result = translate_to_english(CHINESE_TEXT, "zh")

        assert result is None

    def test_unsupported_language_returns_none(self):
        """Unsupported language codes return None without calling pipeline."""
        with patch("anveshak.analyst.translation._get_pipeline") as mock_get:
            from anveshak.analyst.translation import translate_to_english
            result = translate_to_english("some text", "xx")

        assert result is None
        mock_get.assert_not_called()

    def test_text_truncation(self):
        """Very long text is truncated before translation."""
        long_text = "中" * 10000   # 10K chars, exceeds default max_chars=5000
        mock_output = [{"translation_text": "China " * 100}]
        with patch("anveshak.analyst.translation._get_pipeline") as mock_get:
            mock_pipe = MagicMock(return_value=mock_output)
            mock_get.return_value = mock_pipe

            from anveshak.analyst.translation import translate_to_english
            from anveshak.analyst.settings import settings
            result = translate_to_english(long_text, "zh")

        assert result is not None
        # Verify the text passed to pipeline was truncated
        passed_text = mock_pipe.call_args.args[0]
        assert len(passed_text) <= settings.translation_max_chars


# ---------------------------------------------------------------------------
# NER on translated English text
# ---------------------------------------------------------------------------

class TestNEROnTranslatedText:

    def test_english_ner_on_translated_chinese(self):
        """English NER extracts entities from the translated English text."""
        from anveshak.analyst.nlp import EntityDTO, _MODELS

        mock_doc = MagicMock()
        entities = [
            ("Xi Jinping", "PERSON"),
            ("South China Sea", "LOC"),
            ("People's Liberation Army", "ORG"),
        ]
        mock_spans = []
        for text, label in entities:
            span = MagicMock()
            span.text = text
            span.label_ = label
            mock_spans.append(span)
        mock_doc.ents = mock_spans

        mock_nlp = MagicMock(return_value=mock_doc)
        _MODELS["en"] = mock_nlp

        from anveshak.analyst.nlp import parse_entities
        result = parse_entities(EXPECTED_TRANSLATION, "en")

        assert len(result) == 3
        texts = {e.entity_text for e in result}
        assert "Xi Jinping" in texts
        assert "South China Sea" in texts
        assert "People's Liberation Army" in texts
        # All entities tagged with English language code
        assert all(e.language == "en" for e in result)

        del _MODELS["en"]


# ---------------------------------------------------------------------------
# Embedding on translated text
# ---------------------------------------------------------------------------

class TestEmbeddingOnTranslatedText:

    def test_encode_text_returns_vector(self):
        """encode_text produces a list of floats for English translated text."""
        import numpy as np
        expected_dim = 384
        fake_vector = np.array([0.1] * expected_dim, dtype=np.float32)
        with patch("anveshak.analyst.embeddings._encoder") as mock_enc:
            mock_enc.encode.return_value = fake_vector

            from anveshak.analyst.embeddings import encode_text
            result = encode_text(EXPECTED_TRANSLATION)

        assert isinstance(result, list)
        assert len(result) == expected_dim
        assert all(isinstance(x, float) for x in result)


# ---------------------------------------------------------------------------
# analyse_content job — translation path (fully mocked)
# ---------------------------------------------------------------------------

class TestAnalyseContentWithTranslation:
    """Verify the full analyse_content ARQ job wires translation correctly."""

    @pytest.mark.asyncio
    async def test_chinese_content_translated_before_ner(self):
        """analyse_content translates Chinese text; entities extracted in English."""
        from unittest.mock import AsyncMock, MagicMock, patch, call

        content_id = "test-zh-001"
        fake_row = {
            "id": content_id,
            "clean_text": CHINESE_TEXT,
            "topic_id": "topic-zh-test",
            "topic_name": "South China Sea",
            "topic_keywords": ["PLA", "military", "exercises"],
            "topic_relevance_threshold": None,
        }

        # Mock DB pool
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=fake_row)
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)

        ctx = {"db_pool": mock_pool}

        fake_entity = MagicMock()
        fake_entity.entity_type = "PERSON"
        fake_entity.entity_text = "Xi Jinping"
        fake_entity.confidence = 1.0
        fake_entity.language = "en"

        with (
            patch("anveshak.analyst.jobs.detect_language", return_value="zh"),
            patch("anveshak.analyst.jobs.needs_translation", return_value=True),
            patch("anveshak.analyst.jobs.translate_to_english", return_value=EXPECTED_TRANSLATION),
            patch("anveshak.analyst.jobs.parse_entities", return_value=[fake_entity]) as mock_ner,
            patch("anveshak.analyst.jobs.encode_text", return_value=[0.1] * 384),
            patch("anveshak.analyst.jobs.build_topic_query_embedding", return_value=[0.1] * 384),
            patch("anveshak.analyst.jobs.settings") as mock_settings,
        ):
            mock_settings.translation_enabled = True
            mock_settings.translation_model = "facebook/nllb-200-distilled-600M"

            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, content_id)

        # NER must have received the TRANSLATED English text, not the Chinese original
        mock_ner.assert_called_once_with(EXPECTED_TRANSLATION, "en")

    @pytest.mark.asyncio
    async def test_english_content_skips_translation(self):
        """analyse_content does NOT call translate_to_english for English content."""
        english_text = "The PLA conducted military drills near Taiwan today."
        fake_row = {"id": "test-en-001", "clean_text": english_text}

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=fake_row)
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)

        ctx = {"db_pool": mock_pool}

        with (
            patch("anveshak.analyst.jobs.detect_language", return_value="en"),
            patch("anveshak.analyst.jobs.needs_translation", return_value=False),
            patch("anveshak.analyst.jobs.translate_to_english") as mock_translate,
            patch("anveshak.analyst.jobs.parse_entities", return_value=[]),
            patch("anveshak.analyst.jobs.encode_text", return_value=[0.1] * 384),
            patch("anveshak.analyst.jobs.settings") as mock_settings,
        ):
            mock_settings.translation_enabled = True
            mock_settings.translation_model = "facebook/nllb-200-distilled-600M"

            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "test-en-001")

        mock_translate.assert_not_called()


# ---------------------------------------------------------------------------
# ContentItem model — translated_text fields (labels mandatory)
# ---------------------------------------------------------------------------

class TestContentItemTranslationFields:

    def test_translated_text_optional(self):
        """ContentItem accepts translated_text=None (English articles)."""
        from anveshak.models.content import ContentItem
        from anveshak.models.base import Labels
        import hashlib

        item = ContentItem(
            source_id="src-001",
            raw_text="raw",
            clean_text="clean text for testing",
            content_hash=hashlib.sha256(b"clean text for testing").hexdigest(),
            labels=Labels(),
        )
        assert item.translated_text is None
        assert item.translation_model is None

    def test_translated_text_populated(self):
        """ContentItem stores translated_text and translation_model when set."""
        from anveshak.models.content import ContentItem
        from anveshak.models.base import Labels
        import hashlib

        item = ContentItem(
            source_id="src-002",
            raw_text="中文原文",
            clean_text="中文原文清洗后",
            language="zh",
            content_hash=hashlib.sha256("中文原文清洗后".encode()).hexdigest(),
            translated_text=EXPECTED_TRANSLATION,
            translation_model="facebook/nllb-200-distilled-600M",
            labels=Labels(),
        )
        assert item.translated_text == EXPECTED_TRANSLATION
        assert item.translation_model == "facebook/nllb-200-distilled-600M"
        assert item.language == "zh"

    def test_labels_mandatory(self):
        """ContentItem.labels is non-Optional — omitting it raises ValidationError."""
        from pydantic import ValidationError
        from anveshak.models.content import ContentItem
        import hashlib

        with pytest.raises(ValidationError):
            ContentItem(
                source_id="src-003",
                raw_text="raw",
                clean_text="clean",
                content_hash=hashlib.sha256(b"clean").hexdigest(),
                # labels intentionally omitted
            )
