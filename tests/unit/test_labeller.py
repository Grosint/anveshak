"""Unit tests for cluster label generation (labeller.py).

TDD RED phase — these tests define the expected interface for:
- parse_context_rows: parse CTE UNION ALL rows into structured context
- build_label_prompt: assemble enriched prompt with structured context
- fallback_label: template-driven fallback using topic name + scam templates
- parse_label: validate LLM JSON output
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers — fake DB rows matching CTE UNION ALL shape
# ---------------------------------------------------------------------------

def _text_row(text: str, labels_json: str | None = None):
    """Simulate a 'texts' row from SQL_CLUSTER_LABEL_CONTEXT."""
    return {
        "section": "texts",
        "val1": text,
        "val2": None,
        "val3": None,
        "val4": labels_json,
        "val5": None,
        "val6": None,
        "val7": None,
    }


def _entity_row(entity_type: str, entity_text: str, cnt: int):
    return {
        "section": "entity",
        "val1": entity_type,
        "val2": entity_text,
        "val3": None,
        "val4": None,
        "val5": cnt,
        "val6": None,
        "val7": None,
    }


def _platform_row(platform: str, source_name: str, item_count: int,
                   earliest: datetime, latest: datetime):
    return {
        "section": "platform",
        "val1": platform,
        "val2": source_name,
        "val3": None,
        "val4": None,
        "val5": item_count,
        "val6": earliest,
        "val7": latest,
    }


def _topic_row(topic_name: str, topic_keywords: str = ""):
    return {
        "section": "topic",
        "val1": topic_name,
        "val2": topic_keywords,
        "val3": None,
        "val4": None,
        "val5": None,
        "val6": None,
        "val7": None,
    }


def _make_context_rows():
    """Full set of context rows for a cyber fraud cluster."""
    t1 = datetime(2026, 6, 20, tzinfo=timezone.utc)
    t2 = datetime(2026, 6, 26, tzinfo=timezone.utc)
    labels_with_template = json.dumps({"scam_template": "mule_recruitment"})
    labels_with_identifiers = json.dumps({
        "identifiers": {"PHONE": ["9876543210"], "UPI": ["scammer@paytm"]},
    })
    return [
        _topic_row("Telangana Cyber Fraud Intelligence", "cyber fraud, TGCSB, telangana"),
        _text_row("Fake investment scheme targeting youth via Telegram", labels_with_template),
        _text_row("Mule account recruitment post on social media", labels_with_identifiers),
        _text_row("Police arrest 5 in online fraud case"),
        _entity_row("ORG", "TGCSB", 30),
        _entity_row("GPE", "Hyderabad", 15),
        _entity_row("PERSON", "John Doe", 5),
        _platform_row("telegram", "indiabankaccs", 30, t1, t2),
        _platform_row("rss", "siasat.com", 8, t1, t2),
        _platform_row("web", "tgcsb.tspolice.gov.in", 6, t1, t2),
    ]


# ---------------------------------------------------------------------------
# Tests: parse_context_rows
# ---------------------------------------------------------------------------

class TestParseContextRows:
    """parse_context_rows extracts structured data from CTE UNION ALL rows."""

    def test_extracts_texts(self):
        from anveshak.analyst.labeller import parse_context_rows

        rows = _make_context_rows()
        ctx = parse_context_rows(rows)
        assert len(ctx.texts) == 3
        assert "Fake investment scheme" in ctx.texts[0]

    def test_extracts_entities_with_type(self):
        from anveshak.analyst.labeller import parse_context_rows

        rows = _make_context_rows()
        ctx = parse_context_rows(rows)
        assert len(ctx.entities) >= 3
        assert ctx.entities[0] == ("ORG", "TGCSB", 30)

    def test_extracts_platform_summary(self):
        from anveshak.analyst.labeller import parse_context_rows

        rows = _make_context_rows()
        ctx = parse_context_rows(rows)
        assert len(ctx.platforms) == 3
        assert ctx.platforms[0][0] == "telegram"  # platform
        assert ctx.platforms[0][2] == 30  # item_count

    def test_extracts_topic_name(self):
        from anveshak.analyst.labeller import parse_context_rows

        rows = _make_context_rows()
        ctx = parse_context_rows(rows)
        assert ctx.topic_name == "Telangana Cyber Fraud Intelligence"

    def test_extracts_scam_templates_from_labels(self):
        from anveshak.analyst.labeller import parse_context_rows

        rows = _make_context_rows()
        ctx = parse_context_rows(rows)
        assert "mule_recruitment" in ctx.scam_templates

    def test_extracts_identifier_counts(self):
        from anveshak.analyst.labeller import parse_context_rows

        rows = _make_context_rows()
        ctx = parse_context_rows(rows)
        # Exact counts: 1 PHONE, 1 UPI from test data
        assert ctx.identifier_counts["PHONE"] == 1
        assert ctx.identifier_counts["UPI"] == 1

    def test_empty_rows(self):
        from anveshak.analyst.labeller import parse_context_rows

        ctx = parse_context_rows([])
        assert ctx.texts == []
        assert ctx.entities == []
        assert ctx.platforms == []
        assert ctx.topic_name == ""
        assert ctx.scam_templates == []


# ---------------------------------------------------------------------------
# Tests: build_label_prompt
# ---------------------------------------------------------------------------

class TestBuildLabelPrompt:
    """build_label_prompt assembles enriched prompt with structured context."""

    def test_includes_topic_name(self):
        from anveshak.analyst.labeller import build_label_prompt, parse_context_rows

        ctx = parse_context_rows(_make_context_rows())
        prompt = build_label_prompt(ctx)
        assert "Telangana Cyber Fraud Intelligence" in prompt

    def test_includes_entity_table(self):
        from anveshak.analyst.labeller import build_label_prompt, parse_context_rows

        ctx = parse_context_rows(_make_context_rows())
        prompt = build_label_prompt(ctx)
        assert "ORG: TGCSB" in prompt
        assert "GPE: Hyderabad" in prompt

    def test_includes_platform_summary(self):
        from anveshak.analyst.labeller import build_label_prompt, parse_context_rows

        ctx = parse_context_rows(_make_context_rows())
        prompt = build_label_prompt(ctx)
        assert "telegram" in prompt.lower()
        assert "rss" in prompt.lower()

    def test_includes_scam_templates(self):
        from anveshak.analyst.labeller import build_label_prompt, parse_context_rows

        ctx = parse_context_rows(_make_context_rows())
        prompt = build_label_prompt(ctx)
        assert "mule_recruitment" in prompt

    def test_includes_identifier_counts(self):
        from anveshak.analyst.labeller import build_label_prompt, parse_context_rows

        ctx = parse_context_rows(_make_context_rows())
        prompt = build_label_prompt(ctx)
        assert "PHONE" in prompt
        assert "UPI" in prompt

    def test_includes_text_excerpts(self):
        from anveshak.analyst.labeller import build_label_prompt, parse_context_rows

        ctx = parse_context_rows(_make_context_rows())
        prompt = build_label_prompt(ctx)
        assert "Fake investment scheme" in prompt

    def test_includes_sensitivity_guard(self):
        from anveshak.analyst.labeller import build_label_prompt, parse_context_rows

        ctx = parse_context_rows(_make_context_rows())
        prompt = build_label_prompt(ctx)
        # MEA blocker: attribution words appear in NEVER/forbidden section only
        assert "NEVER" in prompt
        lower = prompt.lower()
        for word in ["propaganda", "influence operation", "disinformation", "psyop"]:
            assert word in lower, f"Forbidden word '{word}' missing from prompt"
            # Verify word appears after NEVER instruction, not in examples
            never_pos = prompt.index("NEVER")
            word_pos = lower.index(word)
            assert word_pos > never_pos, f"'{word}' must appear after NEVER instruction"

    def test_includes_good_bad_examples(self):
        from anveshak.analyst.labeller import build_label_prompt, parse_context_rows

        ctx = parse_context_rows(_make_context_rows())
        prompt = build_label_prompt(ctx)
        assert "GOOD" in prompt or "Good" in prompt
        assert "BAD" in prompt or "Bad" in prompt

    def test_boundary_markers_present(self):
        from anveshak.analyst.labeller import build_label_prompt, parse_context_rows

        ctx = parse_context_rows(_make_context_rows())
        prompt = build_label_prompt(ctx)
        # Security: user text wrapped in boundary markers
        assert "===CONTEXT===" in prompt

    def test_empty_context_still_produces_valid_prompt(self):
        from anveshak.analyst.labeller import build_label_prompt, parse_context_rows

        ctx = parse_context_rows([])
        prompt = build_label_prompt(ctx)
        assert "JSON" in prompt  # still asks for JSON output


# ---------------------------------------------------------------------------
# Tests: fallback_label
# ---------------------------------------------------------------------------

class TestFallbackLabel:
    """fallback_label produces readable labels, not entity-soup."""

    def test_with_scam_template_and_topic(self):
        from anveshak.analyst.labeller import fallback_label

        label = fallback_label(
            top_entities=["TGCSB", "Hyderabad"],
            topic_name="Telangana Cyber Fraud Intelligence",
            scam_templates=["mule_recruitment"],
        )
        assert "Mule Recruitment" in label
        assert "Telangana" in label

    def test_with_scam_template_no_topic(self):
        from anveshak.analyst.labeller import fallback_label

        label = fallback_label(
            top_entities=["TGCSB"],
            scam_templates=["investment_fraud"],
        )
        assert "Investment Fraud" in label

    def test_with_entities_and_topic_no_template(self):
        from anveshak.analyst.labeller import fallback_label

        label = fallback_label(
            top_entities=["TGCSB", "Hyderabad", "GamingPay"],
            topic_name="Telangana Cyber Fraud Intelligence",
        )
        assert "Telangana" in label
        assert "TGCSB" in label
        # Should NOT be entity-soup "TGCSB — Hyderabad — GamingPay"
        assert " — " not in label

    def test_with_entities_no_topic_no_template(self):
        from anveshak.analyst.labeller import fallback_label

        label = fallback_label(top_entities=["TGCSB", "Hyderabad", "GamingPay"])
        assert "Activity" in label
        assert "TGCSB" in label
        assert " — " not in label

    def test_no_entities_no_topic(self):
        from anveshak.analyst.labeller import fallback_label

        label = fallback_label(top_entities=[])
        assert label == "Unclassified cluster"

    def test_old_entity_soup_eliminated(self):
        """The old format 'X — Y — Z' must never be produced."""
        from anveshak.analyst.labeller import fallback_label

        # All combinations should NOT produce entity-soup
        for entities in [["A", "B", "C"], ["A", "B"], ["A"]]:
            label = fallback_label(top_entities=entities)
            assert " — " not in label, f"Entity-soup detected: {label}"


# ---------------------------------------------------------------------------
# Tests: parse_label
# ---------------------------------------------------------------------------

class TestParseLabel:
    """parse_label validates LLM JSON output through ClusterLabel."""

    def test_valid_json(self):
        from anveshak.analyst.labeller import parse_label

        raw = '{"label": "Investment fraud via Telegram", "summary": "Multiple accounts recruiting mules.", "confidence": 0.85}'
        result = parse_label(raw)
        assert result.label == "Investment fraud via Telegram"
        assert result.confidence == 0.85

    def test_json_wrapped_in_markdown_fences(self):
        from anveshak.analyst.labeller import parse_label

        raw = '```json\n{"label": "Drug trafficking discussion", "summary": "Test.", "confidence": 0.7}\n```'
        result = parse_label(raw)
        assert result.label == "Drug trafficking discussion"

    def test_json_with_preamble_text(self):
        from anveshak.analyst.labeller import parse_label

        raw = 'Here is the analysis:\n{"label": "Test label", "summary": "Test summary.", "confidence": 0.5}'
        result = parse_label(raw)
        assert result.label == "Test label"

    def test_invalid_json_raises(self):
        from anveshak.analyst.labeller import parse_label

        with pytest.raises((ValueError, Exception)):
            parse_label("This is not JSON at all")

    def test_missing_required_field_raises(self):
        from anveshak.analyst.labeller import parse_label

        with pytest.raises(Exception):
            parse_label('{"label": "Test", "summary": "Test."}')  # missing confidence
