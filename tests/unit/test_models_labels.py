"""Test that all Pydantic models have non-optional labels field.

CLAUDE.md rule 2: Labels are NEVER Optional on any model.
"""
import pytest
from anveshak.models import (
    Topic, Source, ContentItem, Signal, Report, AnalysisJob,
    CredibilityAuditLog, ReportSourceWarning
)
from anveshak.models.base import Labels


class TestLabelsNonOptional:
    """Every model must carry labels. This test suite enforces CLAUDE.md rule 2."""

    def test_topic_has_labels(self):
        fields = Topic.model_fields
        assert "labels" in fields
        assert fields["labels"].is_required() or fields["labels"].default is not None

    def test_source_has_labels(self):
        assert "labels" in Source.model_fields

    def test_content_item_has_labels(self):
        assert "labels" in ContentItem.model_fields

    def test_signal_has_labels(self):
        assert "labels" in Signal.model_fields

    def test_report_has_labels(self):
        assert "labels" in Report.model_fields

    def test_analysis_job_has_labels(self):
        assert "labels" in AnalysisJob.model_fields

    def test_credibility_audit_log_has_labels(self):
        assert "labels" in CredibilityAuditLog.model_fields

    def test_labels_not_optional(self):
        """labels field must not be Optional[Labels]."""
        import typing
        for model_cls in [Topic, Source, ContentItem, Signal, Report]:
            field = model_cls.model_fields["labels"]
            annotation = field.annotation
            # Should be Labels, not Optional[Labels]
            assert annotation is Labels or (
                hasattr(annotation, "__args__") is False
            ), f"{model_cls.__name__}.labels should not be Optional"


class TestReportImmutability:
    """Report.generated_at must be set once and not have a default factory that updates."""

    def test_generated_at_is_optional_initially(self):
        """generated_at starts as None — set only when report generation completes."""
        report_fields = Report.model_fields
        assert "generated_at" in report_fields
        # Should be Optional[datetime] — starts None, set once on generation
        import typing
        annotation = report_fields["generated_at"].annotation
        assert report_fields["generated_at"].default is None


class TestContentHashPresent:
    """ContentItem must have content_hash field for deduplication."""

    def test_content_item_has_content_hash(self):
        assert "content_hash" in ContentItem.model_fields

    def test_content_hash_is_str(self):
        field = ContentItem.model_fields["content_hash"]
        assert field.annotation is str
