"""Tests for Engine C Step 4b — Scam Template Match Signals.

Covers:
- Severity-based match thresholds (CRITICAL=1, HIGH=2, MEDIUM=3)
- Evidence JSONB building
- Description building
- WebSocket payload building
- Dedup check (24h per template_name + topic_id)
- Signal insertion with correct params
- Check cycle with severity-gated firing
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool_and_conn():
    """Build mock asyncpg pool + connection with context manager support."""
    conn = AsyncMock()
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


def _breaching_row(
    *,
    template_name: str = "mule_recruitment",
    template_display: str = "Mule Account Recruitment",
    template_severity: str = "CRITICAL",
    template_legal_sections: list[str] | None = None,
    topic_id: str = "topic-1",
    match_count: int = 1,
    max_confidence: float = 0.85,
):
    """Build a fake row from SQL_BREACHING_TEMPLATE_MATCHES."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "template_name": template_name,
        "template_display": template_display,
        "template_severity": template_severity,
        "template_legal_sections": template_legal_sections or ["PMLA Section 3"],
        "topic_id": topic_id,
        "match_count": match_count,
        "max_confidence": max_confidence,
    }[key]
    return row


def _latest_match_row(
    *,
    content_item_id: str = "ci-1",
    confidence: float = 0.85,
    matched_keywords: list[str] | None = None,
    extracted_identifiers: dict | None = None,
):
    """Build a fake row from SQL_LATEST_TEMPLATE_MATCH_ITEM."""
    row = MagicMock()
    labels = {
        "scam_template": "mule_recruitment",
        "template_confidence": confidence,
    }
    if matched_keywords is not None:
        labels["matched_keywords"] = matched_keywords
    if extracted_identifiers is not None:
        labels["extracted_identifiers"] = extracted_identifiers
    row.__getitem__ = lambda self, key: {
        "content_item_id": content_item_id,
        "confidence": str(confidence),
        "item_labels": json.dumps(labels),
    }[key]
    return row


# ===================================================================
# 1. compute_template_match_threshold
# ===================================================================


class TestComputeTemplateMatchThreshold:
    """Severity-based match thresholds: CRITICAL=1, HIGH=2, MEDIUM=3."""

    def test_critical_threshold_is_1(self):
        from anveshak.analyst.template_signals import compute_template_match_threshold

        assert compute_template_match_threshold("CRITICAL") == 1

    def test_high_threshold_is_2(self):
        from anveshak.analyst.template_signals import compute_template_match_threshold

        assert compute_template_match_threshold("HIGH") == 2

    def test_medium_threshold_is_3(self):
        from anveshak.analyst.template_signals import compute_template_match_threshold

        assert compute_template_match_threshold("MEDIUM") == 3

    def test_low_threshold_is_3(self):
        """LOW uses same threshold as MEDIUM (most conservative)."""
        from anveshak.analyst.template_signals import compute_template_match_threshold

        assert compute_template_match_threshold("LOW") == 3

    def test_unknown_severity_defaults_to_3(self):
        from anveshak.analyst.template_signals import compute_template_match_threshold

        assert compute_template_match_threshold("UNKNOWN") == 3


# ===================================================================
# 2. build_template_evidence
# ===================================================================


class TestBuildTemplateEvidence:
    """Evidence JSONB matches plan spec."""

    def test_all_keys_present(self):
        from anveshak.analyst.template_signals import build_template_evidence

        ev = build_template_evidence(
            template_name="mule_recruitment",
            template_display="Mule Account Recruitment",
            confidence=0.85,
            matched_keywords=["bank account", "commission"],
            extracted_identifiers={"PHONE_IN": ["+919876543210"]},
            legal_sections=["PMLA Section 3"],
            content_item_id="ci-1",
            match_count=3,
        )
        assert ev["template_name"] == "mule_recruitment"
        assert ev["template_display"] == "Mule Account Recruitment"
        assert ev["confidence"] == 0.85
        assert ev["matched_keywords"] == ["bank account", "commission"]
        assert ev["extracted_identifiers"] == {"PHONE_IN": ["+919876543210"]}
        assert ev["legal_sections"] == ["PMLA Section 3"]
        assert ev["content_item_id"] == "ci-1"
        assert ev["match_count"] == 3

    def test_returns_dict(self):
        from anveshak.analyst.template_signals import build_template_evidence

        ev = build_template_evidence(
            template_name="x",
            template_display="X",
            confidence=0.5,
            matched_keywords=[],
            extracted_identifiers={},
            legal_sections=[],
            content_item_id="ci-1",
            match_count=1,
        )
        assert isinstance(ev, dict)

    def test_json_serializable(self):
        from anveshak.analyst.template_signals import build_template_evidence

        ev = build_template_evidence(
            template_name="drug_sale",
            template_display="Drug Sale",
            confidence=0.72,
            matched_keywords=["maal", "delivery"],
            extracted_identifiers={"TELEGRAM_HANDLE": ["dealer_bot"]},
            legal_sections=["NDPS Act Section 20"],
            content_item_id="ci-2",
            match_count=2,
        )
        serialized = json.dumps(ev)
        assert isinstance(serialized, str)

    def test_empty_identifiers_allowed(self):
        from anveshak.analyst.template_signals import build_template_evidence

        ev = build_template_evidence(
            template_name="fake_sim_sale",
            template_display="Fake SIM Sale",
            confidence=0.55,
            matched_keywords=["sim", "bulk"],
            extracted_identifiers={},
            legal_sections=["Indian Telegraph Act Section 20"],
            content_item_id="ci-3",
            match_count=3,
        )
        assert ev["extracted_identifiers"] == {}


# ===================================================================
# 3. build_template_description
# ===================================================================


class TestBuildTemplateDescription:
    """Human-readable description for analysts."""

    def test_contains_template_display(self):
        from anveshak.analyst.template_signals import build_template_description

        desc = build_template_description(
            template_display="Mule Account Recruitment",
            match_count=3,
            max_confidence=0.85,
        )
        assert "Mule Account Recruitment" in desc

    def test_contains_match_count(self):
        from anveshak.analyst.template_signals import build_template_description

        desc = build_template_description(
            template_display="Investment Fraud",
            match_count=5,
            max_confidence=0.9,
        )
        assert "5" in desc

    def test_returns_string(self):
        from anveshak.analyst.template_signals import build_template_description

        desc = build_template_description(
            template_display="Drug Sale",
            match_count=2,
            max_confidence=0.7,
        )
        assert isinstance(desc, str)


# ===================================================================
# 4. build_template_signal_payload
# ===================================================================


class TestBuildTemplateSignalPayload:
    """WebSocket payload for template match signals."""

    def test_signal_type_field(self):
        from anveshak.analyst.template_signals import build_template_signal_payload

        payload = build_template_signal_payload(
            signal_id="sig-1",
            topic_id="topic-1",
            template_name="mule_recruitment",
            template_display="Mule Account Recruitment",
            template_severity="CRITICAL",
            match_count=2,
            max_confidence=0.85,
        )
        assert payload["signal_type"] == "scam_template_match"

    def test_type_is_signal(self):
        from anveshak.analyst.template_signals import build_template_signal_payload

        payload = build_template_signal_payload(
            signal_id="sig-1",
            topic_id="topic-1",
            template_name="mule_recruitment",
            template_display="Mule Account Recruitment",
            template_severity="CRITICAL",
            match_count=1,
            max_confidence=0.85,
        )
        assert payload["type"] == "signal"

    def test_severity_from_template(self):
        """Severity comes from template, not computed from match_count."""
        from anveshak.analyst.template_signals import build_template_signal_payload

        payload = build_template_signal_payload(
            signal_id="sig-1",
            topic_id="topic-1",
            template_name="fake_sim_sale",
            template_display="Fake SIM Sale",
            template_severity="MEDIUM",
            match_count=5,
            max_confidence=0.6,
        )
        assert payload["severity"] == "MEDIUM"

    def test_all_fields_present(self):
        from anveshak.analyst.template_signals import build_template_signal_payload

        payload = build_template_signal_payload(
            signal_id="sig-1",
            topic_id="topic-1",
            template_name="investment_fraud",
            template_display="Investment Fraud",
            template_severity="CRITICAL",
            match_count=3,
            max_confidence=0.92,
        )
        expected_keys = {
            "type",
            "signal_type",
            "signal_id",
            "topic_id",
            "template_name",
            "template_display",
            "severity",
            "match_count",
            "max_confidence",
        }
        assert set(payload.keys()) == expected_keys


# ===================================================================
# 5. is_duplicate_template_signal
# ===================================================================


class TestIsDuplicateTemplateSignal:
    """24h dedup per (template_name, topic_id)."""

    @pytest.mark.asyncio
    async def test_existing_returns_true(self):
        from anveshak.analyst.template_signals import is_duplicate_template_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = {"id": "existing-signal"}
        result = await is_duplicate_template_signal(conn, "mule_recruitment", "topic-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_none_returns_false(self):
        from anveshak.analyst.template_signals import is_duplicate_template_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None
        result = await is_duplicate_template_signal(conn, "mule_recruitment", "topic-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_query_uses_both_template_name_and_topic_id(self):
        from anveshak.analyst.template_signals import is_duplicate_template_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None
        await is_duplicate_template_signal(conn, "drug_sale", "topic-42")
        args = conn.fetchrow.call_args[0]
        # SQL is $1, params are template_name and topic_id
        assert "drug_sale" in args
        assert "topic-42" in args


# ===================================================================
# 6. fire_template_signal
# ===================================================================


class TestFireTemplateSignal:
    """Insert signal row with correct params."""

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_dedup_returns_none(self, mock_metric):
        from anveshak.analyst.template_signals import fire_template_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = {"id": "existing"}  # dedup hit
        result = await fire_template_signal(
            conn,
            topic_id="topic-1",
            template_name="mule_recruitment",
            template_display="Mule Account Recruitment",
            template_severity="CRITICAL",
            confidence=0.85,
            matched_keywords=["bank", "commission"],
            extracted_identifiers={"PHONE_IN": ["+91123"]},
            legal_sections=["PMLA Section 3"],
            content_item_id="ci-1",
            match_count=1,
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        assert result is None

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_inserts_with_uuid(self, mock_metric):
        from anveshak.analyst.template_signals import fire_template_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None  # no dedup
        result = await fire_template_signal(
            conn,
            topic_id="topic-1",
            template_name="mule_recruitment",
            template_display="Mule Account Recruitment",
            template_severity="CRITICAL",
            confidence=0.85,
            matched_keywords=["bank", "commission"],
            extracted_identifiers={},
            legal_sections=["PMLA Section 3"],
            content_item_id="ci-1",
            match_count=1,
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        assert result is not None
        # Valid UUID
        uuid.UUID(result)

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_evidence_is_json(self, mock_metric):
        from anveshak.analyst.template_signals import fire_template_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None
        await fire_template_signal(
            conn,
            topic_id="topic-1",
            template_name="drug_sale",
            template_display="Drug Sale",
            template_severity="HIGH",
            confidence=0.72,
            matched_keywords=["maal"],
            extracted_identifiers={"TELEGRAM_HANDLE": ["dealer"]},
            legal_sections=["NDPS Act Section 20"],
            content_item_id="ci-2",
            match_count=2,
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        # Evidence arg to conn.execute: SQL[0], sig_id[1], topic[2], cluster[3], type[4], desc[5], evidence[6]
        call_args = conn.execute.call_args[0]
        evidence_json = call_args[6]
        parsed = json.loads(evidence_json)
        assert parsed["template_name"] == "drug_sale"
        assert parsed["confidence"] == 0.72

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_cluster_id_is_null(self, mock_metric):
        """cluster_id FK is for narrative_clusters only — NULL for template signals."""
        from anveshak.analyst.template_signals import fire_template_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None
        await fire_template_signal(
            conn,
            topic_id="topic-1",
            template_name="mule_recruitment",
            template_display="Mule Account Recruitment",
            template_severity="CRITICAL",
            confidence=0.85,
            matched_keywords=[],
            extracted_identifiers={},
            legal_sections=[],
            content_item_id="ci-1",
            match_count=1,
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        call_args = conn.execute.call_args[0]
        # cluster_id: SQL[0], sig_id[1], topic[2], cluster[3]
        assert call_args[3] is None

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_signal_type_constant(self, mock_metric):
        from anveshak.analyst.template_signals import fire_template_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None
        await fire_template_signal(
            conn,
            topic_id="topic-1",
            template_name="mule_recruitment",
            template_display="Mule Account Recruitment",
            template_severity="CRITICAL",
            confidence=0.85,
            matched_keywords=[],
            extracted_identifiers={},
            legal_sections=[],
            content_item_id="ci-1",
            match_count=1,
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        call_args = conn.execute.call_args[0]
        # signal_type: SQL[0], sig_id[1], topic[2], cluster[3], type[4]
        assert call_args[4] == "scam_template_match"

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_severity_metric_incremented(self, mock_metric):
        from anveshak.analyst.template_signals import fire_template_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None
        await fire_template_signal(
            conn,
            topic_id="topic-1",
            template_name="mule_recruitment",
            template_display="Mule Account Recruitment",
            template_severity="CRITICAL",
            confidence=0.85,
            matched_keywords=[],
            extracted_identifiers={},
            legal_sections=[],
            content_item_id="ci-1",
            match_count=1,
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        mock_metric.labels.assert_called_with(severity="CRITICAL")
        mock_metric.labels().inc.assert_called_once()


# ===================================================================
# 7. check_template_signals — check cycle
# ===================================================================


class TestCheckTemplateSignals:
    """Integration of severity gating, dedup, fire, broadcast."""

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_no_matches_returns_zero(self, mock_metric):
        from anveshak.analyst.template_signals import check_template_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.return_value = []  # no breaching matches
        broadcast = AsyncMock()
        result = await check_template_signals(pool, broadcast)
        assert result == 0
        broadcast.assert_not_called()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_critical_fires_on_single_match(self, mock_metric):
        """CRITICAL templates fire signal on 1 match."""
        from anveshak.analyst.template_signals import check_template_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            # First call: breaching template matches
            [
                _breaching_row(
                    template_name="mule_recruitment",
                    template_severity="CRITICAL",
                    match_count=1,
                )
            ],
        ]
        # fetchrow sequence: latest_match_item, then dedup inside fire_template_signal
        conn.fetchrow.side_effect = [
            _latest_match_row(content_item_id="ci-1", confidence=0.85),  # latest match
            None,  # dedup check inside fire — no existing signal
        ]
        broadcast = AsyncMock()
        result = await check_template_signals(pool, broadcast)
        assert result == 1
        broadcast.assert_called_once()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_high_skips_single_match(self, mock_metric):
        """HIGH templates need 2+ matches — skip if only 1."""
        from anveshak.analyst.template_signals import check_template_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [
                _breaching_row(
                    template_name="digital_arrest",
                    template_severity="HIGH",
                    match_count=1,  # below threshold of 2
                )
            ],
        ]
        broadcast = AsyncMock()
        result = await check_template_signals(pool, broadcast)
        assert result == 0

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_high_fires_on_two_matches(self, mock_metric):
        """HIGH templates fire on 2+ matches."""
        from anveshak.analyst.template_signals import check_template_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [
                _breaching_row(
                    template_name="digital_arrest",
                    template_severity="HIGH",
                    match_count=2,
                )
            ],
        ]
        conn.fetchrow.side_effect = [
            _latest_match_row(content_item_id="ci-5", confidence=0.78),  # latest match
            None,  # dedup inside fire
        ]
        broadcast = AsyncMock()
        result = await check_template_signals(pool, broadcast)
        assert result == 1

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_medium_needs_three_matches(self, mock_metric):
        """MEDIUM templates need 3+ matches."""
        from anveshak.analyst.template_signals import check_template_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [
                _breaching_row(
                    template_name="fake_sim_sale",
                    template_severity="MEDIUM",
                    match_count=2,  # below threshold of 3
                )
            ],
        ]
        broadcast = AsyncMock()
        result = await check_template_signals(pool, broadcast)
        assert result == 0

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_dedup_skips_duplicate(self, mock_metric):
        """Already-fired signal in 24h → skip."""
        from anveshak.analyst.template_signals import check_template_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [_breaching_row(template_severity="CRITICAL", match_count=3)],
        ]
        conn.fetchrow.side_effect = [
            _latest_match_row(),  # latest match item
            {"id": "existing-signal"},  # dedup hit inside fire
        ]
        broadcast = AsyncMock()
        result = await check_template_signals(pool, broadcast)
        assert result == 0

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_broadcast_failure_still_counts(self, mock_metric):
        """Broadcast failure doesn't crash; signal still counted."""
        from anveshak.analyst.template_signals import check_template_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [_breaching_row(template_severity="CRITICAL", match_count=1)],
        ]
        conn.fetchrow.side_effect = [
            _latest_match_row(),  # latest match
            None,  # dedup inside fire
        ]
        broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
        result = await check_template_signals(pool, broadcast)
        assert result == 1

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_multiple_templates_mixed_severity(self, mock_metric):
        """Multiple templates in one cycle — some fire, some skip."""
        from anveshak.analyst.template_signals import check_template_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [
                _breaching_row(
                    template_name="mule_recruitment",
                    template_severity="CRITICAL",
                    match_count=1,
                    topic_id="topic-1",
                ),
                _breaching_row(
                    template_name="fake_sim_sale",
                    template_severity="MEDIUM",
                    match_count=2,  # below 3 threshold
                    topic_id="topic-1",
                ),
                _breaching_row(
                    template_name="digital_arrest",
                    template_severity="HIGH",
                    match_count=4,  # above 2 threshold
                    topic_id="topic-2",
                ),
            ],
        ]
        # Sequence: mule latest, mule dedup, (fake_sim skipped), digital latest, digital dedup
        conn.fetchrow.side_effect = [
            _latest_match_row(content_item_id="ci-1"),  # mule latest match
            None,  # mule dedup inside fire
            # fake_sim_sale skipped by threshold — no DB calls
            _latest_match_row(content_item_id="ci-2"),  # digital latest match
            None,  # digital dedup inside fire
        ]
        broadcast = AsyncMock()
        result = await check_template_signals(pool, broadcast)
        assert result == 2  # mule_recruitment + digital_arrest
        assert broadcast.call_count == 2

    @pytest.mark.asyncio
    @patch("anveshak.analyst.template_signals.analyst_signals_fired_total")
    async def test_payload_has_template_name(self, mock_metric):
        """Broadcast payload includes template_name."""
        from anveshak.analyst.template_signals import check_template_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [
                _breaching_row(
                    template_name="investment_fraud",
                    template_display="Investment Fraud",
                    template_severity="CRITICAL",
                    match_count=1,
                )
            ],
        ]
        conn.fetchrow.side_effect = [
            _latest_match_row(),  # latest match
            None,  # dedup inside fire
        ]
        broadcast = AsyncMock()
        await check_template_signals(pool, broadcast)
        payload = broadcast.call_args[0][0]
        assert payload["template_name"] == "investment_fraud"


# ===================================================================
# 8. Signal type constant
# ===================================================================


class TestSignalTypeConstant:
    """Module exports match expected values."""

    def test_signal_type_value(self):
        from anveshak.analyst.template_signals import SIGNAL_TYPE_TEMPLATE_MATCH

        assert SIGNAL_TYPE_TEMPLATE_MATCH == "scam_template_match"

    def test_sql_constants_exported(self):
        from anveshak.analyst import template_signals

        assert hasattr(template_signals, "SQL_BREACHING_TEMPLATE_MATCHES")
        assert hasattr(template_signals, "SQL_DUPLICATE_TEMPLATE_SIGNAL_CHECK")
        assert hasattr(template_signals, "SQL_LATEST_TEMPLATE_MATCH_ITEM")
