"""Unit tests for Engine C — Scam Template Library (Step 2).

Tests cover:
- ScamTemplate / TemplateMatch dataclass shape
- BUILTIN_TEMPLATES: 11 templates, valid fields
- Keyword scoring: overlap, min_keyword_hits gate
- Identifier scoring: expected vs extracted
- Embedding similarity: cosine sim with reference
- Confidence formula: max(0.6*kw + 0.4*id, emb)
- Match selection: highest confidence wins, ≥0.5 threshold
- Edge cases: empty inputs, no templates, no matches
- Per-template positive/negative: each of 11 built-in templates
"""

from __future__ import annotations

import numpy as np
import pytest
from anveshak.analyst.templates import (
    BUILTIN_TEMPLATES,
    ScamTemplate,
    TemplateMatch,
    match_templates,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit_vec(dim: int = 384, seed: int = 42) -> list[float]:
    """Return a deterministic L2-normalized vector."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim)
    v /= np.linalg.norm(v)
    return v.tolist()


def _perturb(base: list[float], noise: float = 0.02, seed: int = 99) -> list[float]:
    """Perturb a base vector with small noise, re-normalize."""
    rng = np.random.default_rng(seed)
    arr = np.array(base) + rng.standard_normal(len(base)) * noise
    arr /= np.linalg.norm(arr)
    return arr.tolist()


def _make_template(**overrides) -> ScamTemplate:
    """Factory for ScamTemplate with sensible defaults."""
    defaults = dict(
        name="test_template",
        display="Test Template",
        category="fraud",
        keywords=["fraud", "money", "send", "account", "urgent"],
        min_keyword_hits=3,
        expected_identifiers=["PHONE_IN", "UPI"],
        severity="HIGH",
        reference_embedding=None,
        legal_sections=["IPC 420"],
    )
    defaults.update(overrides)
    return ScamTemplate(**defaults)


# ============================================================================
# 1. Data model tests
# ============================================================================


class TestScamTemplateModel:
    """ScamTemplate dataclass shape and immutability."""

    def test_required_fields(self):
        t = _make_template()
        assert t.name == "test_template"
        assert t.display == "Test Template"
        assert t.category == "fraud"
        assert t.keywords == ["fraud", "money", "send", "account", "urgent"]
        assert t.min_keyword_hits == 3
        assert t.expected_identifiers == ["PHONE_IN", "UPI"]
        assert t.severity == "HIGH"
        assert t.reference_embedding is None
        assert t.legal_sections == ["IPC 420"]

    def test_frozen(self):
        t = _make_template()
        with pytest.raises(AttributeError):
            t.name = "changed"  # type: ignore[misc]

    def test_with_embedding(self):
        emb = _unit_vec()
        t = _make_template(reference_embedding=emb)
        assert t.reference_embedding is not None
        assert len(t.reference_embedding) == 384


class TestTemplateMatchModel:
    """TemplateMatch dataclass shape."""

    def test_required_fields(self):
        m = TemplateMatch(
            template_name="investment_fraud",
            template_display="Investment Fraud",
            confidence=0.85,
            matched_keywords=["invest", "guaranteed", "returns"],
            matched_identifier_types=["PHONE_IN"],
            legal_sections=["SEBI PFUTP"],
            severity="CRITICAL",
        )
        assert m.template_name == "investment_fraud"
        assert m.confidence == 0.85
        assert m.matched_keywords == ["invest", "guaranteed", "returns"]
        assert m.matched_identifier_types == ["PHONE_IN"]
        assert m.legal_sections == ["SEBI PFUTP"]
        assert m.severity == "CRITICAL"

    def test_frozen(self):
        m = TemplateMatch(
            template_name="x",
            template_display="X",
            confidence=0.5,
            matched_keywords=[],
            matched_identifier_types=[],
            legal_sections=[],
            severity="LOW",
        )
        with pytest.raises(AttributeError):
            m.confidence = 0.9  # type: ignore[misc]


# ============================================================================
# 2. Built-in templates
# ============================================================================


class TestBuiltinTemplates:
    """11 built-in templates with valid fields."""

    def test_count(self):
        assert len(BUILTIN_TEMPLATES) == 11

    def test_all_are_scam_templates(self):
        for t in BUILTIN_TEMPLATES:
            assert isinstance(t, ScamTemplate)

    def test_unique_names(self):
        names = [t.name for t in BUILTIN_TEMPLATES]
        assert len(names) == len(set(names))

    def test_expected_names(self):
        names = {t.name for t in BUILTIN_TEMPLATES}
        expected = {
            "investment_fraud",
            "mule_recruitment",
            "maas",
            "digital_arrest",
            "job_fraud",
            "pump_and_dump",
            "fake_research_report",
            "drug_sale",
            "drug_delivery_recruitment",
            "fake_sim_sale",
            "crypto_cashout",
        }
        assert names == expected

    def test_valid_categories(self):
        valid = {"fraud", "info_op", "narco", "custom"}
        for t in BUILTIN_TEMPLATES:
            assert t.category in valid, f"{t.name} has invalid category {t.category}"

    def test_valid_severities(self):
        valid = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        for t in BUILTIN_TEMPLATES:
            assert t.severity in valid, f"{t.name} has invalid severity {t.severity}"

    def test_keywords_non_empty(self):
        for t in BUILTIN_TEMPLATES:
            assert len(t.keywords) >= 3, f"{t.name} has too few keywords"

    def test_min_keyword_hits_positive(self):
        for t in BUILTIN_TEMPLATES:
            assert t.min_keyword_hits >= 1, f"{t.name} min_keyword_hits < 1"
            assert t.min_keyword_hits <= len(t.keywords), (
                f"{t.name} min_keyword_hits > len(keywords)"
            )

    def test_legal_sections_present(self):
        for t in BUILTIN_TEMPLATES:
            assert isinstance(t.legal_sections, list), f"{t.name} legal_sections not list"

    def test_severities_per_plan(self):
        """Verify severities match the plan table."""
        sev = {t.name: t.severity for t in BUILTIN_TEMPLATES}
        assert sev["investment_fraud"] == "CRITICAL"
        assert sev["mule_recruitment"] == "CRITICAL"
        assert sev["maas"] == "CRITICAL"
        assert sev["digital_arrest"] == "HIGH"
        assert sev["job_fraud"] == "HIGH"
        assert sev["pump_and_dump"] == "CRITICAL"
        assert sev["fake_research_report"] == "HIGH"
        assert sev["drug_sale"] == "HIGH"
        assert sev["drug_delivery_recruitment"] == "HIGH"
        assert sev["fake_sim_sale"] == "MEDIUM"
        assert sev["crypto_cashout"] == "HIGH"


# ============================================================================
# 3. Keyword scoring
# ============================================================================


class TestKeywordScoring:
    """Keyword overlap and min_keyword_hits gate."""

    def test_all_keywords_match(self):
        t = _make_template(keywords=["fraud", "money", "send"], min_keyword_hits=2)
        result = match_templates(
            content_keywords={"fraud", "money", "send"},
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        assert result is not None
        assert result.confidence >= 0.5

    def test_partial_keywords_above_min(self):
        t = _make_template(
            keywords=["fraud", "money", "send", "account", "urgent"],
            min_keyword_hits=3,
            expected_identifiers=[],
        )
        result = match_templates(
            content_keywords={"fraud", "money", "send"},
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        assert result is not None
        # keyword_score = 3/5 = 0.6, id_match = 1.0 (empty expected)
        # confidence = 0.6 * 0.6 + 0.4 * 1.0 = 0.76

    def test_below_min_keyword_hits_rejected(self):
        t = _make_template(
            keywords=["fraud", "money", "send", "account", "urgent"], min_keyword_hits=3
        )
        result = match_templates(
            content_keywords={"fraud", "money"},  # only 2, min is 3
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        assert result is None

    def test_zero_keyword_overlap_rejected(self):
        t = _make_template(keywords=["fraud", "money", "send"], min_keyword_hits=2)
        result = match_templates(
            content_keywords={"weather", "sports", "news"},
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        assert result is None

    def test_matched_keywords_in_result(self):
        t = _make_template(
            keywords=["fraud", "money", "send", "account", "urgent"],
            min_keyword_hits=2,
            expected_identifiers=[],
        )
        result = match_templates(
            content_keywords={"fraud", "money", "send"},
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        assert result is not None
        assert set(result.matched_keywords) == {"fraud", "money", "send"}

    def test_case_insensitive_keyword_match(self):
        t = _make_template(keywords=["fraud", "money"], min_keyword_hits=2, expected_identifiers=[])
        result = match_templates(
            content_keywords={"FRAUD", "MONEY"},
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        assert result is not None


# ============================================================================
# 4. Identifier scoring
# ============================================================================


class TestIdentifierScoring:
    """Expected vs extracted identifier types."""

    def test_all_identifiers_match_boosts_confidence(self):
        t = _make_template(
            keywords=["fraud", "money", "send", "account", "urgent"],
            min_keyword_hits=3,
            expected_identifiers=["PHONE_IN", "UPI"],
        )
        result = match_templates(
            content_keywords={"fraud", "money", "send"},
            identifier_types={"PHONE_IN", "UPI"},
            content_embedding=None,
            templates=[t],
        )
        assert result is not None
        assert "PHONE_IN" in result.matched_identifier_types
        assert "UPI" in result.matched_identifier_types

    def test_partial_identifier_match(self):
        t = _make_template(
            keywords=["fraud", "money", "send", "account", "urgent"],
            min_keyword_hits=3,
            expected_identifiers=["PHONE_IN", "UPI", "CRYPTO_BTC"],
        )
        result = match_templates(
            content_keywords={"fraud", "money", "send", "account"},
            identifier_types={"PHONE_IN"},
            content_embedding=None,
            templates=[t],
        )
        # keyword_score = 4/5 = 0.8, id_match = 1/3 = 0.333
        # confidence = 0.6 * 0.8 + 0.4 * 0.333 = 0.48 + 0.133 = 0.613
        assert result is not None
        assert result.confidence >= 0.5

    def test_no_expected_identifiers_means_full_id_score(self):
        """Empty expected_identifiers → identifier_match = 1.0 (no penalty)."""
        t = _make_template(
            keywords=["fraud", "money", "send"],
            min_keyword_hits=2,
            expected_identifiers=[],
        )
        result = match_templates(
            content_keywords={"fraud", "money", "send"},
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        assert result is not None
        # keyword_score = 3/3 = 1.0, id_match = 1.0 (empty expected)
        # confidence = 0.6 * 1.0 + 0.4 * 1.0 = 1.0
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_matched_identifier_types_in_result(self):
        t = _make_template(
            keywords=["fraud", "money", "send"],
            min_keyword_hits=2,
            expected_identifiers=["PHONE_IN", "UPI", "EMAIL"],
        )
        result = match_templates(
            content_keywords={"fraud", "money", "send"},
            identifier_types={"PHONE_IN", "EMAIL", "CRYPTO_BTC"},
            content_embedding=None,
            templates=[t],
        )
        assert result is not None
        assert set(result.matched_identifier_types) == {"PHONE_IN", "EMAIL"}


# ============================================================================
# 5. Embedding similarity
# ============================================================================


class TestEmbeddingSimilarity:
    """Cosine similarity with reference embedding."""

    def test_high_similarity_matches(self):
        ref = _unit_vec(seed=42)
        content_emb = _perturb(ref, noise=0.02, seed=99)  # very similar
        t = _make_template(
            keywords=["x"],  # no keyword match possible
            min_keyword_hits=1,
            reference_embedding=ref,
        )
        # keywords won't match but embedding should be high enough
        result = match_templates(
            content_keywords={"x"},
            identifier_types=set(),
            content_embedding=content_emb,
            templates=[t],
        )
        assert result is not None
        assert result.confidence >= 0.5

    def test_low_similarity_no_match(self):
        ref = _unit_vec(seed=42)
        unrelated = _unit_vec(seed=999)  # completely different vector
        t = _make_template(
            keywords=["x", "y", "z"],
            min_keyword_hits=3,
            reference_embedding=ref,
        )
        result = match_templates(
            content_keywords={"a", "b", "c"},  # no keyword match
            identifier_types=set(),
            content_embedding=unrelated,
            templates=[t],
        )
        # No keyword match → gated out. Even embedding sim probably < 0.5
        assert result is None

    def test_no_content_embedding_skips_embedding_score(self):
        ref = _unit_vec(seed=42)
        t = _make_template(
            keywords=["fraud", "money", "send"],
            min_keyword_hits=2,
            expected_identifiers=[],
            reference_embedding=ref,
        )
        result = match_templates(
            content_keywords={"fraud", "money", "send"},
            identifier_types=set(),
            content_embedding=None,  # no embedding
            templates=[t],
        )
        assert result is not None
        # Should still work via keyword scoring alone

    def test_no_reference_embedding_skips_embedding_score(self):
        t = _make_template(
            keywords=["fraud", "money", "send"],
            min_keyword_hits=2,
            expected_identifiers=[],
            reference_embedding=None,
        )
        result = match_templates(
            content_keywords={"fraud", "money", "send"},
            identifier_types=set(),
            content_embedding=_unit_vec(),
            templates=[t],
        )
        assert result is not None

    def test_embedding_can_rescue_low_keyword_score(self):
        """Embedding similarity alone can match via max() in formula."""
        ref = _unit_vec(seed=42)
        content_emb = _perturb(ref, noise=0.01, seed=99)  # very close
        t = _make_template(
            keywords=[
                "fraud",
                "money",
                "send",
                "account",
                "urgent",
                "transfer",
                "bank",
                "commission",
            ],
            min_keyword_hits=2,
            expected_identifiers=["PHONE_IN", "UPI", "CRYPTO_BTC"],
            reference_embedding=ref,
        )
        result = match_templates(
            content_keywords={"fraud", "money"},  # only 2/8 keywords
            identifier_types=set(),  # 0/3 identifiers
            content_embedding=content_emb,
            templates=[t],
        )
        # keyword_score = 2/8 = 0.25, id_match = 0/3 = 0
        # kw+id confidence = 0.6*0.25 + 0.4*0 = 0.15
        # embedding_score ≈ 0.99 (very close vectors)
        # confidence = max(0.15, 0.99) ≈ 0.99
        assert result is not None
        assert result.confidence >= 0.9


# ============================================================================
# 6. Confidence formula
# ============================================================================


class TestConfidenceFormula:
    """confidence = max(0.6*kw + 0.4*id, emb)."""

    def test_formula_keyword_only(self):
        """No embedding → confidence = 0.6*kw + 0.4*id."""
        t = _make_template(
            keywords=["a", "b", "c", "d", "e"],
            min_keyword_hits=2,
            expected_identifiers=["PHONE_IN"],
            reference_embedding=None,
        )
        result = match_templates(
            content_keywords={"a", "b", "c", "d", "e"},  # 5/5 = 1.0
            identifier_types={"PHONE_IN"},  # 1/1 = 1.0
            content_embedding=None,
            templates=[t],
        )
        assert result is not None
        assert result.confidence == pytest.approx(1.0, abs=0.01)

    def test_formula_with_partial_scores(self):
        t = _make_template(
            keywords=["a", "b", "c", "d", "e"],
            min_keyword_hits=2,
            expected_identifiers=["PHONE_IN", "UPI"],
            reference_embedding=None,
        )
        result = match_templates(
            content_keywords={"a", "b", "c"},  # 3/5 = 0.6
            identifier_types={"PHONE_IN"},  # 1/2 = 0.5
            content_embedding=None,
            templates=[t],
        )
        # confidence = 0.6 * 0.6 + 0.4 * 0.5 = 0.36 + 0.20 = 0.56
        assert result is not None
        assert result.confidence == pytest.approx(0.56, abs=0.02)

    def test_below_threshold_rejected(self):
        """confidence < 0.5 → no match."""
        t = _make_template(
            keywords=["a", "b", "c", "d", "e"],
            min_keyword_hits=2,
            expected_identifiers=["PHONE_IN", "UPI", "CRYPTO_BTC"],
            reference_embedding=None,
        )
        result = match_templates(
            content_keywords={"a", "b"},  # 2/5 = 0.4
            identifier_types=set(),  # 0/3 = 0
            content_embedding=None,
            templates=[t],
        )
        # confidence = 0.6 * 0.4 + 0.4 * 0 = 0.24 → below 0.5
        assert result is None

    def test_threshold_boundary_exact_0_5(self):
        """confidence == 0.5 should match (>= 0.5)."""
        # Need kw + id to produce exactly 0.5
        # 0.6 * kw + 0.4 * id = 0.5
        # kw = 5/6 = 0.833, id = 0 → 0.6 * 0.833 = 0.5
        t = _make_template(
            keywords=["a", "b", "c", "d", "e", "f"],
            min_keyword_hits=3,
            expected_identifiers=["PHONE_IN"],
            reference_embedding=None,
        )
        result = match_templates(
            content_keywords={"a", "b", "c", "d", "e"},  # 5/6 ≈ 0.833
            identifier_types=set(),  # 0/1 = 0
            content_embedding=None,
            templates=[t],
        )
        # confidence = 0.6 * 0.833 + 0.4 * 0 = 0.5
        assert result is not None
        assert result.confidence == pytest.approx(0.5, abs=0.01)


# ============================================================================
# 7. Match selection
# ============================================================================


class TestMatchSelection:
    """Highest-confidence match wins."""

    def test_highest_confidence_selected(self):
        low = _make_template(
            name="low_match",
            display="Low",
            keywords=["a", "b", "c", "d", "e"],
            min_keyword_hits=2,
            expected_identifiers=[],
        )
        high = _make_template(
            name="high_match",
            display="High",
            keywords=["a", "b", "c"],
            min_keyword_hits=2,
            expected_identifiers=[],
        )
        result = match_templates(
            content_keywords={"a", "b", "c"},
            identifier_types=set(),
            content_embedding=None,
            templates=[low, high],
        )
        assert result is not None
        # high: 3/3 = 1.0, conf = 0.6*1.0 + 0.4*1.0 = 1.0
        # low: 3/5 = 0.6, conf = 0.6*0.6 + 0.4*1.0 = 0.76
        assert result.template_name == "high_match"

    def test_single_template_returned(self):
        """Even with multiple matches, only ONE result returned."""
        t1 = _make_template(
            name="t1",
            display="T1",
            keywords=["a", "b"],
            min_keyword_hits=2,
            expected_identifiers=[],
        )
        t2 = _make_template(
            name="t2",
            display="T2",
            keywords=["a", "b", "c"],
            min_keyword_hits=2,
            expected_identifiers=[],
        )
        result = match_templates(
            content_keywords={"a", "b", "c"},
            identifier_types=set(),
            content_embedding=None,
            templates=[t1, t2],
        )
        assert result is not None
        assert isinstance(result, TemplateMatch)

    def test_legal_sections_from_matched_template(self):
        t = _make_template(
            keywords=["a", "b", "c"],
            min_keyword_hits=2,
            expected_identifiers=[],
            legal_sections=["PMLA Section 3"],
        )
        result = match_templates(
            content_keywords={"a", "b", "c"},
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        assert result is not None
        assert result.legal_sections == ["PMLA Section 3"]

    def test_severity_from_matched_template(self):
        t = _make_template(
            keywords=["a", "b", "c"],
            min_keyword_hits=2,
            expected_identifiers=[],
            severity="CRITICAL",
        )
        result = match_templates(
            content_keywords={"a", "b", "c"},
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        assert result is not None
        assert result.severity == "CRITICAL"


# ============================================================================
# 8. Edge cases
# ============================================================================


class TestEdgeCases:
    """Empty inputs, no templates, graceful handling."""

    def test_empty_templates_list(self):
        result = match_templates(
            content_keywords={"fraud", "money"},
            identifier_types={"PHONE_IN"},
            content_embedding=None,
            templates=[],
        )
        assert result is None

    def test_empty_content_keywords(self):
        t = _make_template()
        result = match_templates(
            content_keywords=set(),
            identifier_types={"PHONE_IN"},
            content_embedding=None,
            templates=[t],
        )
        assert result is None

    def test_none_embedding_handled(self):
        t = _make_template(
            keywords=["fraud", "money", "send"],
            min_keyword_hits=2,
            expected_identifiers=[],
        )
        result = match_templates(
            content_keywords={"fraud", "money", "send"},
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        # Should work fine without embedding
        assert result is not None

    def test_all_templates_below_threshold(self):
        t = _make_template(
            keywords=["a", "b", "c", "d", "e"],
            min_keyword_hits=2,
            expected_identifiers=["PHONE_IN", "UPI", "CRYPTO_BTC"],
        )
        result = match_templates(
            content_keywords={"a", "b"},  # 2/5 = 0.4, id = 0/3
            identifier_types=set(),
            content_embedding=None,
            templates=[t],
        )
        # confidence = 0.6 * 0.4 + 0.4 * 0 = 0.24
        assert result is None


# ============================================================================
# 9. Per-template positive/negative tests (11 templates)
# ============================================================================


class TestInvestmentFraud:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={
                "invest",
                "guaranteed",
                "returns",
                "profit",
                "double",
                "money",
                "daily",
            },
            identifier_types={"PHONE_IN", "UPI"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "investment_fraud"

    def test_negative_no_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={"weather", "cricket", "sports"},
            identifier_types=set(),
            content_embedding=None,
            templates=templates,
        )
        assert result is None


class TestMuleRecruitment:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={
                "bank",
                "account",
                "commission",
                "per transaction",
                "easy money",
                "salary",
                "income",
            },
            identifier_types={"PHONE_IN", "TELEGRAM_HANDLE"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "mule_recruitment"


class TestMaas:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={
                "account",
                "rent",
                "bank account",
                "monthly",
                "payment",
                "kyc",
                "documents",
            },
            identifier_types={"PHONE_IN", "UPI"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "maas"


class TestDigitalArrest:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={"police", "arrest", "warrant", "case", "legal", "pay", "fine"},
            identifier_types={"PHONE_IN"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "digital_arrest"


class TestJobFraud:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={
                "job",
                "work from home",
                "salary",
                "hiring",
                "vacancy",
                "apply",
                "registration fee",
            },
            identifier_types={"PHONE_IN", "UPI"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "job_fraud"


class TestPumpAndDump:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={
                "stock",
                "buy",
                "target",
                "multibagger",
                "tip",
                "profit",
                "guaranteed",
            },
            identifier_types={"PHONE_IN", "TELEGRAM_HANDLE"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "pump_and_dump"


class TestFakeResearchReport:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={
                "research",
                "report",
                "analyst",
                "target price",
                "buy",
                "strong buy",
                "recommendation",
            },
            identifier_types={"TELEGRAM_HANDLE"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "fake_research_report"


class TestDrugSale:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={"maal", "stuff", "delivery", "gram", "pure", "quality", "available"},
            identifier_types={"PHONE_IN", "TELEGRAM_HANDLE"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "drug_sale"


class TestDrugDeliveryRecruitment:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={"delivery", "driver", "parcel", "pickup", "drop", "payment", "cash"},
            identifier_types={"PHONE_IN"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "drug_delivery_recruitment"


class TestFakeSimSale:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={
                "sim",
                "sim card",
                "pre-activated",
                "bulk",
                "no kyc",
                "available",
                "whatsapp",
            },
            identifier_types={"PHONE_IN", "TELEGRAM_HANDLE"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "fake_sim_sale"


class TestCryptoCashout:
    def test_positive_match(self):
        templates = BUILTIN_TEMPLATES
        result = match_templates(
            content_keywords={"usdt", "cash", "convert", "rate", "exchange", "crypto", "withdraw"},
            identifier_types={"CRYPTO_TRC20", "TELEGRAM_HANDLE"},
            content_embedding=None,
            templates=templates,
        )
        assert result is not None
        assert result.template_name == "crypto_cashout"
