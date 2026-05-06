"""Report generator — fills docs/accuracy_benchmark.md with benchmark results."""
from __future__ import annotations

import re
from pathlib import Path

import structlog

from .metrics import BenchmarkMetrics
from .settings import settings

log = structlog.get_logger(__name__)


def fill_template(metrics: BenchmarkMetrics, template_path: Path | None = None) -> Path:
    """Replace ___ placeholders in docs/accuracy_benchmark.md with real numbers."""
    if template_path is None:
        template_path = Path(settings.docs_template)

    content = template_path.read_text()

    # Overall performance table
    content = _replace_table_row(content, "**Precision**", f"{metrics.precision} %")
    content = _replace_table_row(content, "**Recall**", f"{metrics.recall} %")
    content = _replace_table_row(content, "**F1 Score**", f"{metrics.f1_score} %")
    content = _replace_table_row(content, "**Median Time Advantage**", f"{metrics.median_time_advantage_hours} hours before mainstream media")
    content = _replace_table_row(content, "**Mean Time Advantage**", f"{metrics.mean_time_advantage_hours} hours before mainstream media")

    # Per-category table
    category_map = {
        "Information operations": "information_operations",
        "Cross-border security": "cross_border_security",
        "Deepfake / manipulated media": "deepfake_manipulated_media",
        "Protest / civil unrest": "protest_civil_unrest",
        "Critical infrastructure": "critical_infrastructure",
    }
    for display_name, key in category_map.items():
        if key in metrics.per_category:
            cat = metrics.per_category[key]
            content = _replace_category_row(
                content, display_name,
                cat["precision"], cat["recall"], cat["avg_time_advantage"],
            )

    # Per-language table
    lang_map = {
        "English": "en",
        "Hindi": "hi",
        "Urdu": "ur",
        "Chinese (Simplified)": "zh",
        "Arabic": "ar",
        "Russian": "ru",
    }
    for display_name, code in lang_map.items():
        if code in metrics.per_language:
            lang = metrics.per_language[code]
            content = _replace_language_row(
                content, display_name,
                lang["precision"], lang["recall"],
            )

    template_path.write_text(content)
    log.info("benchmark.report_filled", path=str(template_path))
    return template_path


def _replace_table_row(content: str, label: str, value: str) -> str:
    """Replace ___ in a markdown table row identified by label."""
    pattern = re.compile(
        rf"(\| {re.escape(label)} \|)\s*___\s*(%?\s*\|?)",
        re.MULTILINE,
    )
    replacement = rf"\1 {value} |"
    result = pattern.sub(replacement, content)
    if result == content:
        # Try simpler pattern
        content = content.replace(f"| {label} | ___ ", f"| {label} | {value} ")
    return result


def _replace_category_row(
    content: str, category: str, precision: float, recall: float, time_adv: float,
) -> str:
    """Replace ___ in category performance row."""
    pattern = re.compile(
        rf"(\| {re.escape(category)} \|)\s*___\s*%\s*\|\s*___\s*%\s*\|\s*___\s*hrs\s*\|",
        re.MULTILINE,
    )
    replacement = rf"\1 {precision} % | {recall} % | {time_adv} hrs |"
    return pattern.sub(replacement, content)


def _replace_language_row(
    content: str, language: str, precision: float, recall: float,
) -> str:
    """Replace ___ in language performance row."""
    pattern = re.compile(
        rf"(\| {re.escape(language)} \|)\s*___\s*%\s*\|\s*___\s*%\s*\|",
        re.MULTILINE,
    )
    replacement = rf"\1 {precision} % | {recall} % |"
    return pattern.sub(replacement, content)
