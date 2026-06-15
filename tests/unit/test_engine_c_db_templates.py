"""Unit tests for DB template loading in analyse_content.

Verifies:
  1. SQL_GET_TEMPLATES_FOR_TOPIC exists and queries scam_templates + topic_templates
  2. analyse_content queries templates from DB, not just BUILTIN_TEMPLATES
  3. When topic has linked templates, only those are used
  4. When topic has no linked templates, all builtin templates are used (fallback)

pytest.mark.unit -- no external dependencies.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


_JOBS = "anveshak.analyst.jobs"


@pytest.mark.unit
class TestTemplateSQLExists:
    """jobs.py must have SQL to load templates for a topic."""

    def test_sql_get_templates_for_topic(self):
        from anveshak.analyst.jobs import SQL_GET_TEMPLATES_FOR_TOPIC
        sql = SQL_GET_TEMPLATES_FOR_TOPIC.lower()
        assert "scam_templates" in sql, "Must query scam_templates table"
        assert "topic_templates" in sql, "Must consider topic_templates linkage"


@pytest.mark.unit
class TestLoadTemplatesFromDB:
    """load_templates_for_topic function must exist and return ScamTemplate list."""

    def test_function_exists(self):
        from anveshak.analyst.jobs import load_templates_for_topic
        assert callable(load_templates_for_topic)

    @pytest.mark.asyncio
    async def test_returns_builtin_when_no_linked(self):
        """When topic has no linked templates, return all builtins from DB."""
        from anveshak.analyst.jobs import load_templates_for_topic

        # Mock DB returning builtin templates
        fake_rows = [
            {
                "name": "investment_fraud",
                "display": "Investment Fraud",
                "category": "fraud",
                "keywords": ["invest", "guaranteed", "returns"],
                "min_keyword_hits": 3,
                "expected_identifiers": ["PHONE_IN", "UPI"],
                "severity": "CRITICAL",
                "reference_embedding": None,
                "legal_sections": ["IPC 420"],
                "is_linked": False,
            },
        ]

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=fake_rows)

        templates = await load_templates_for_topic(conn, "topic-1")
        assert len(templates) >= 1
        assert templates[0].name == "investment_fraud"

    @pytest.mark.asyncio
    async def test_returns_only_linked_when_linked(self):
        """When topic has linked templates, return only linked ones."""
        from anveshak.analyst.jobs import load_templates_for_topic

        fake_rows = [
            {
                "name": "investment_fraud",
                "display": "Investment Fraud",
                "category": "fraud",
                "keywords": ["invest", "guaranteed"],
                "min_keyword_hits": 2,
                "expected_identifiers": ["PHONE_IN"],
                "severity": "CRITICAL",
                "reference_embedding": None,
                "legal_sections": ["IPC 420"],
                "is_linked": True,
            },
            {
                "name": "drug_sale",
                "display": "Drug Sale",
                "category": "narco",
                "keywords": ["maal", "stuff"],
                "min_keyword_hits": 2,
                "expected_identifiers": ["PHONE_IN"],
                "severity": "HIGH",
                "reference_embedding": None,
                "legal_sections": ["NDPS 20"],
                "is_linked": False,
            },
        ]

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=fake_rows)

        templates = await load_templates_for_topic(conn, "topic-1")
        # Only linked template should be returned
        names = [t.name for t in templates]
        assert "investment_fraud" in names
        assert "drug_sale" not in names


@pytest.mark.unit
class TestAnalyseContentUsesDBTemplates:
    """analyse_content must call load_templates_for_topic instead of using BUILTIN_TEMPLATES."""

    @pytest.mark.asyncio
    async def test_calls_load_templates(self):
        row = {
            "id": "ci-1",
            "clean_text": "Invest now for guaranteed returns. Pay to fraud@ybl",
            "topic_id": "topic-1",
            "topic_name": "Cyber Fraud",
            "topic_keywords": ["fraud", "scam"],
            "topic_relevance_threshold": None,
            "platform": "telegram",
        }

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=row)
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)
        acq = AsyncMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)
        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=acq)

        with (
            patch(f"{_JOBS}.is_quality_content", return_value=(True, "passed")),
            patch(f"{_JOBS}.detect_language", return_value="en"),
            patch(f"{_JOBS}.needs_translation", return_value=False),
            patch(f"{_JOBS}.is_model_loaded", return_value=True),
            patch(f"{_JOBS}.parse_entities", return_value=[]),
            patch(f"{_JOBS}.encode_text", return_value=[0.1] * 384),
            patch(f"{_JOBS}.build_topic_query_embedding", return_value=[0.2] * 384),
            patch(f"{_JOBS}.compute_topic_relevance", return_value=0.5),
            patch(f"{_JOBS}.analyse_sentiment", return_value=type("S", (), {"compound": 0.0, "positive": 0.0, "negative": 0.0, "neutral": 1.0})()),
            patch(f"{_JOBS}.extract_keywords", return_value=[]),
            patch(f"{_JOBS}.compute_entity_minhash", return_value=None),
            patch(f"{_JOBS}.extract_identifiers", return_value=[]),
            patch(f"{_JOBS}.match_templates", return_value=None),
            patch(f"{_JOBS}.load_templates_for_topic", new_callable=AsyncMock, return_value=[]) as mock_load,
            patch(f"{_JOBS}.analyst_nlp_jobs_total"),
            patch(f"{_JOBS}.analyst_nlp_duration_seconds"),
            patch(f"{_JOBS}.analyst_relevance_score"),
            patch(f"{_JOBS}.analyst_embedding_completed_total"),
            patch(f"{_JOBS}.analyst_identifiers_extracted_total"),
        ):
            from anveshak.analyst.jobs import analyse_content
            await analyse_content({"db_pool": pool}, "ci-1")

        # Must have called load_templates_for_topic with conn and topic_id
        mock_load.assert_called_once()
        call_args = mock_load.call_args
        # Second arg should be topic_id
        assert call_args.args[1] == "topic-1" or call_args.kwargs.get("topic_id") == "topic-1"
