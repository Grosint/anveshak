"""Stance and hostility scoring — issue #28.

Two measures produced by two models, because they are independent. Stance is
direction toward a narrative: supporting, opposing, or neutral. Hostility is
intensity, 0.0 to 1.0. Neither predicts the other, and a single sentiment
score cannot separate a furious supporter from a calm objector.

Stance needs a target, and the target is the cluster label, which is unknown
at ingest time. Scoring therefore runs in a job chained from clustering
rather than in the ingest enrichment sequence where the lexicon sentiment
score lives.

Both models are multilingual so content is read in its own language rather
than through a translation. Content in a language the models handle poorly
is marked ``unsupported_language`` rather than silently scored, so an analyst
knows which part of a chart to distrust.

Every model name, device string and batch size is a setting. See hardware.md.
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
import structlog

from .settings import settings

log = structlog.get_logger(__name__)

# Stance values. Mirrors the content_items_stance_check constraint in
# migration 006, so a value added here needs a migration.
STANCE_SUPPORTING = "supporting"
STANCE_OPPOSING = "opposing"
STANCE_NEUTRAL = "neutral"
STANCE_UNSUPPORTED_LANGUAGE = "unsupported_language"

# Hypothesis templates for zero-shot natural language inference. The model
# scores each against the content and the highest wins.
_STANCE_HYPOTHESES = {
    STANCE_SUPPORTING: "This text supports {target}.",
    STANCE_OPPOSING: "This text opposes {target}.",
    STANCE_NEUTRAL: "This text is neutral about {target}.",
}

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

SQL_GET_CLUSTER = """
    SELECT nc.label, nc.item_count
    FROM narrative_clusters nc
    WHERE nc.id = $1 AND nc.archived_at IS NULL
"""

# Scores the content the timeline will plot. Quality gate applied here as at
# every other consumption point.
SQL_CLUSTER_ITEMS_TO_SCORE = """
    SELECT ci.id,
           COALESCE(NULLIF(ci.clean_text, ''), ci.raw_text) AS work_text,
           ci.language
    FROM content_items ci
    WHERE ci.narrative_cluster_id = $1
      AND (ci.stance IS NULL OR ci.hostility IS NULL)
      AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
    LIMIT $2
"""

SQL_UPDATE_SCORES = """
    UPDATE content_items
    SET stance = $2, hostility = $3, updated_at = NOW()
    WHERE id = $1
"""


# ---------------------------------------------------------------------------
# Model singletons — loaded once per worker process
# ---------------------------------------------------------------------------

_stance_classifier = None
_hostility_classifier = None


def _get_stance_classifier() -> Any:
    """Multilingual zero-shot NLI classifier. Loaded on first use."""
    global _stance_classifier
    if _stance_classifier is None:
        from transformers import pipeline

        _stance_classifier = pipeline(
            "zero-shot-classification",
            model=settings.stance_model,
            device=settings.stance_device,
            batch_size=settings.stance_batch_size,
        )
        log.info(
            "stance.model_loaded",
            model=settings.stance_model,
            device=settings.stance_device,
            batch_size=settings.stance_batch_size,
        )
    return _stance_classifier


def _get_hostility_classifier() -> Any:
    """Multilingual toxicity classifier. Loaded on first use."""
    global _hostility_classifier
    if _hostility_classifier is None:
        from transformers import pipeline

        _hostility_classifier = pipeline(
            "text-classification",
            model=settings.hostility_model,
            device=settings.hostility_device,
            batch_size=settings.hostility_batch_size,
        )
        log.info(
            "hostility.model_loaded",
            model=settings.hostility_model,
            device=settings.hostility_device,
            batch_size=settings.hostility_batch_size,
        )
    return _hostility_classifier


# ---------------------------------------------------------------------------
# Pure scoring functions
# ---------------------------------------------------------------------------


def is_language_supported(language: str | None) -> bool:
    """True when both models read this language well enough to be trusted.

    Filtering here rather than in detect_language keeps language detection
    honest: detection reports what it found, and this decides what to score.
    """
    if not language:
        return False
    return language.lower() in {code.lower() for code in settings.stance_supported_languages}


def score_stance(text: str, cluster_label: str, *, language: str | None) -> str | None:
    """Return a stance value, or None when scoring did not happen.

    None is an error signal and forces a null check at the call site. It is
    distinct from ``unsupported_language``, which is a measured outcome: the
    content was seen, and the models cannot read it.
    """
    if not text or not text.strip():
        return None
    if not cluster_label or not cluster_label.strip():
        # Stance is direction toward a target. Without one there is nothing
        # to be for or against.
        return None
    if not is_language_supported(language):
        return STANCE_UNSUPPORTED_LANGUAGE

    hypotheses = {
        stance: template.format(target=cluster_label)
        for stance, template in _STANCE_HYPOTHESES.items()
    }
    by_hypothesis = {hypothesis: stance for stance, hypothesis in hypotheses.items()}

    try:
        classifier = _get_stance_classifier()
        result = classifier(
            text[: settings.stance_max_chars],
            candidate_labels=list(hypotheses.values()),
            multi_label=False,
        )
    except Exception as exc:
        log.warning("stance.scoring_failed", error=str(exc), language=language)
        return None

    # The pipeline is typed as returning a union covering batched and
    # streaming shapes. A single-string call returns one dict.
    if not isinstance(result, dict):
        log.warning("stance.unexpected_result_shape", result_type=type(result).__name__)
        return None

    labels = result.get("labels") or []
    scores = result.get("scores") or []
    if not labels or not scores:
        log.warning("stance.empty_result", language=language)
        return None

    top_label, top_score = labels[0], float(scores[0])
    if top_score < settings.stance_confidence_floor:
        # Below the floor the model is guessing between three options. Saying
        # neutral is honest; saying supporting or opposing is not.
        return STANCE_NEUTRAL

    return by_hypothesis.get(top_label, STANCE_NEUTRAL)


def score_hostility(text: str, *, language: str | None) -> float | None:
    """Return hostility 0.0 to 1.0, or None when scoring did not happen.

    Never returns 0.0 on error. 0.0 means measured and not hostile; None
    means not measured, and the call site must tell them apart.
    """
    if not text or not text.strip():
        return None
    if not is_language_supported(language):
        return None

    try:
        classifier = _get_hostility_classifier()
        result = classifier(text[: settings.hostility_max_chars])
    except Exception as exc:
        log.warning("hostility.scoring_failed", error=str(exc), language=language)
        return None

    if not isinstance(result, list) or not result:
        log.warning("hostility.empty_result", language=language)
        return None

    top = result[0]
    if not isinstance(top, dict):
        log.warning("hostility.unexpected_result_shape", result_type=type(top).__name__)
        return None

    label = str(top.get("label", "")).lower()
    score = float(top.get("score", 0.0))

    # The head reports the winning class, which may be the benign one. A
    # confident "neutral" is a low hostility rather than a high one.
    hostile = any(marker in label for marker in settings.hostility_positive_labels)
    value = score if hostile else 1.0 - score

    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# Cluster-level job
# ---------------------------------------------------------------------------


def _score_item(
    text: str, cluster_label: str, language: str | None
) -> tuple[str | None, float | None]:
    """Score one item with both models. Runs in a worker thread."""
    return (
        score_stance(text, cluster_label, language=language),
        score_hostility(text, language=language),
    )


async def score_cluster(pool: asyncpg.Pool, cluster_id: str) -> int:
    """Score every unscored item in a cluster. Returns the count scored.

    Bounded by stance_min_cluster_size, because a timeline is only drawn
    where there is something to draw, and both models are expensive on CPU.

    Failures degrade rather than propagate: this step is additive enrichment,
    and clustering to signals produces valid output without it.
    """
    async with pool.acquire() as conn:
        cluster = await conn.fetchrow(SQL_GET_CLUSTER, cluster_id)
        if cluster is None:
            log.info("stance.cluster_missing", cluster_id=cluster_id)
            return 0

        item_count = cluster["item_count"] or 0
        if item_count < settings.stance_min_cluster_size:
            log.info(
                "stance.cluster_too_small",
                cluster_id=cluster_id,
                item_count=item_count,
                threshold=settings.stance_min_cluster_size,
                reason="a timeline is only drawn where there is something to draw",
            )
            return 0

        label = cluster["label"] or ""
        rows = await conn.fetch(
            SQL_CLUSTER_ITEMS_TO_SCORE, cluster_id, settings.stance_max_items_per_cluster
        )

    # Inference runs off the event loop and outside the pool connection.
    # Both models are synchronous and CPU-bound, and up to
    # stance_max_items_per_cluster of them in a row would otherwise block
    # every other job on this worker and hold a connection for the duration.
    scored_rows: list[tuple[str, str | None, float | None]] = []
    for row in rows:
        try:
            stance, hostility = await asyncio.to_thread(
                _score_item, row["work_text"], label, row["language"]
            )
        except Exception as exc:
            log.warning(
                "stance.item_scoring_failed",
                cluster_id=cluster_id,
                content_item_id=row["id"],
                error=str(exc),
            )
            continue

        if stance is None and hostility is None:
            continue
        scored_rows.append((row["id"], stance, hostility))

    if scored_rows:
        async with pool.acquire() as conn:
            await conn.executemany(SQL_UPDATE_SCORES, scored_rows)

    log.info(
        "stance.cluster_scored",
        cluster_id=cluster_id,
        items_scored=len(scored_rows),
        candidates=len(rows),
    )
    return len(scored_rows)
