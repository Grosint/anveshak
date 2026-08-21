"""Test that all Pydantic models have non-optional labels field.

AGENTS.md rule 2: Labels are NEVER Optional on any model.
"""

from datetime import datetime
from types import UnionType
from typing import Union, get_args, get_origin

from anveshak.models import (
    AnalysisJob,
    ContentItem,
    CredibilityAuditLog,
    Report,
    Signal,
    Source,
    Topic,
)
from anveshak.models.base import Labels


class TestLabelsNonOptional:
    """Every model must carry labels. This test suite enforces AGENTS.md rule 2."""

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
        for model_cls in [Topic, Source, ContentItem, Signal, Report]:
            field = model_cls.model_fields["labels"]
            annotation = field.annotation
            # Should be Labels, not Optional[Labels]
            assert annotation is Labels or (hasattr(annotation, "__args__") is False), (
                f"{model_cls.__name__}.labels should not be Optional"
            )


class TestLabelsVerifierAgreement:
    """The unit test and scripts/verify_labels.py must enforce the same rule.

    They drifted once: this suite passed while `make verify-labels` failed on
    ExtractedEntity, because the test only checked a hand-written list of models
    and the script scanned every class. Rule 2 now scopes to models that are
    persisted or cross a service boundary alone; nested value objects are exempt
    only via an explicit registry. Run the real scanner here so a new unlabelled
    model fails in `make test-unit`, not only in a separate target.
    """

    def test_scanner_reports_no_violations(self):
        import importlib.util
        import sys
        from pathlib import Path

        script = Path(__file__).resolve().parents[2] / "scripts" / "verify_labels.py"
        spec = importlib.util.spec_from_file_location("verify_labels", script)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["verify_labels"] = module
        spec.loader.exec_module(module)

        violations = []
        for module_name in module.MODULES_TO_CHECK:
            violations.extend(module.scan_module(importlib.import_module(module_name)))

        assert violations == [], "\n".join(violations)

    def test_every_exemption_is_justified(self):
        """An exemption with no reason is an exemption nobody can review."""
        import importlib.util
        import sys
        from pathlib import Path

        script = Path(__file__).resolve().parents[2] / "scripts" / "verify_labels.py"
        spec = importlib.util.spec_from_file_location("verify_labels_reasons", script)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["verify_labels_reasons"] = module
        spec.loader.exec_module(module)

        for name, reason in module.EXEMPT_MODELS.items():
            assert reason.strip(), f"{name} is exempt with no stated reason"


class TestReportImmutability:
    """Report.generated_at must be set once and not have a default factory that updates."""

    def test_generated_at_is_optional_initially(self):
        """generated_at starts as None, set only when report generation completes."""
        report_fields = Report.model_fields
        assert "generated_at" in report_fields
        assert report_fields["generated_at"].default is None

        # Must actually be Optional[datetime]. A bare `datetime` annotation with
        # default=None would still pass the default check above while making the
        # None sentinel unrepresentable under strict mode (rule 4).
        annotation = report_fields["generated_at"].annotation
        assert get_origin(annotation) in (Union, UnionType), (
            f"Report.generated_at must be Optional[datetime], got {annotation!r}"
        )
        assert set(get_args(annotation)) == {datetime, type(None)}


class TestContentHashPresent:
    """ContentItem must have content_hash field for deduplication."""

    def test_content_item_has_content_hash(self):
        assert "content_hash" in ContentItem.model_fields

    def test_content_hash_is_str(self):
        field = ContentItem.model_fields["content_hash"]
        assert field.annotation is str
