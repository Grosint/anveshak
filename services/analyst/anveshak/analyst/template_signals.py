"""Engine C Step 4b — Scam Template Match Signals.

Fire signals when content matches known scam templates above
severity-gated thresholds:
  CRITICAL templates → 1+ match fires immediately
  HIGH templates     → 2+ matches in 24h window
  MEDIUM templates   → 3+ matches in 24h window

Integrates with existing signal engine: same signals table, same WebSocket
delivery, same status flow (new -> acknowledged -> dismissed).

Signals table cluster_id FK references narrative_clusters — template
signal references go in evidence JSONB instead, cluster_id set NULL.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

import asyncpg
import structlog
from anveshak.db import DBConnection

from .metrics import analyst_signals_fired_total

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIGNAL_TYPE_TEMPLATE_MATCH = "scam_template_match"

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

SQL_BREACHING_TEMPLATE_MATCHES = """
    SELECT
        ci.labels->>'scam_template'      AS template_name,
        st.display                       AS template_display,
        st.severity                      AS template_severity,
        st.legal_sections                AS template_legal_sections,
        ci.topic_id,
        COUNT(*)                         AS match_count,
        MAX((ci.labels->>'template_confidence')::float) AS max_confidence
    FROM content_items ci
    JOIN topics t ON t.id = ci.topic_id
    JOIN scam_templates st ON st.name = ci.labels->>'scam_template'
    WHERE ci.labels->>'scam_template' IS NOT NULL
      AND t.status = 'active'
      AND ci.created_at > NOW() - INTERVAL '24 hours'
    GROUP BY ci.labels->>'scam_template', st.display, st.severity,
             st.legal_sections, ci.topic_id
"""

SQL_DUPLICATE_TEMPLATE_SIGNAL_CHECK = """
    SELECT id FROM signals
    WHERE signal_type = 'scam_template_match'
      AND evidence->>'template_name' = $1
      AND topic_id = $2
      AND created_at > NOW() - INTERVAL '24 hours'
    LIMIT 1
"""

SQL_LATEST_TEMPLATE_MATCH_ITEM = """
    SELECT
        ci.id                                    AS content_item_id,
        ci.labels->>'template_confidence'        AS confidence,
        ci.labels::text                          AS item_labels
    FROM content_items ci
    WHERE ci.topic_id = $1
      AND ci.labels->>'scam_template' = $2
      AND ci.created_at > NOW() - INTERVAL '24 hours'
    ORDER BY (ci.labels->>'template_confidence')::float DESC
    LIMIT 1
"""

SQL_INSERT_SIGNAL = """
    INSERT INTO signals (
        id, topic_id, cluster_id, signal_type, description, evidence,
        status, created_at, updated_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, $6::jsonb, 'new', $7, $7,
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
    RETURNING id
"""


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def compute_template_match_threshold(severity: str) -> int:
    """Map template severity to required match count in 24h window.

    CRITICAL → 1 (fire immediately on first match)
    HIGH     → 2 (need corroboration)
    MEDIUM   → 3 (need pattern confirmation)
    LOW/other → 3 (most conservative)
    """
    if severity == "CRITICAL":
        return 1
    if severity == "HIGH":
        return 2
    return 3


def build_template_evidence(
    *,
    template_name: str,
    template_display: str,
    confidence: float,
    matched_keywords: list[str],
    extracted_identifiers: dict,
    legal_sections: list[str],
    content_item_id: str,
    match_count: int,
) -> dict:
    """Build evidence JSONB for scam template match signal."""
    return {
        "template_name": template_name,
        "template_display": template_display,
        "confidence": confidence,
        "matched_keywords": matched_keywords,
        "extracted_identifiers": extracted_identifiers,
        "legal_sections": legal_sections,
        "content_item_id": content_item_id,
        "match_count": match_count,
    }


def build_template_description(
    *,
    template_display: str,
    match_count: int,
    max_confidence: float,
) -> str:
    """Build human-readable signal description."""
    return (
        f"Scam template '{template_display}' matched {match_count} content "
        f"items (highest confidence: {max_confidence:.0%})"
    )


def build_template_signal_payload(
    *,
    signal_id: str,
    topic_id: str,
    template_name: str,
    template_display: str,
    template_severity: str,
    match_count: int,
    max_confidence: float,
) -> dict:
    """Build WebSocket push message for template match signal."""
    return {
        "type": "signal",
        "signal_type": SIGNAL_TYPE_TEMPLATE_MATCH,
        "signal_id": signal_id,
        "topic_id": topic_id,
        "template_name": template_name,
        "template_display": template_display,
        "severity": template_severity,
        "match_count": match_count,
        "max_confidence": max_confidence,
    }


# ---------------------------------------------------------------------------
# Async DB functions
# ---------------------------------------------------------------------------


async def is_duplicate_template_signal(
    conn: DBConnection,
    template_name: str,
    topic_id: str,
) -> bool:
    """Return True if scam_template_match signal fired for this template+topic in last 24h."""
    row = await conn.fetchrow(
        SQL_DUPLICATE_TEMPLATE_SIGNAL_CHECK,
        template_name,
        topic_id,
    )
    return row is not None


async def fire_template_signal(
    conn: DBConnection,
    *,
    topic_id: str,
    template_name: str,
    template_display: str,
    template_severity: str,
    confidence: float,
    matched_keywords: list[str],
    extracted_identifiers: dict,
    legal_sections: list[str],
    content_item_id: str,
    match_count: int,
    now: datetime,
) -> str | None:
    """Insert scam_template_match signal. Returns signal_id or None if deduplicated."""
    if await is_duplicate_template_signal(conn, template_name, topic_id):
        log.debug(
            "template_signals.dedup_skipped",
            template_name=template_name,
            topic_id=topic_id,
        )
        return None

    signal_id = str(uuid.uuid4())
    description = build_template_description(
        template_display=template_display,
        match_count=match_count,
        max_confidence=confidence,
    )
    evidence = json.dumps(
        build_template_evidence(
            template_name=template_name,
            template_display=template_display,
            confidence=confidence,
            matched_keywords=matched_keywords,
            extracted_identifiers=extracted_identifiers,
            legal_sections=legal_sections,
            content_item_id=content_item_id,
            match_count=match_count,
        )
    )

    await conn.execute(
        SQL_INSERT_SIGNAL,
        signal_id,
        topic_id,
        None,  # cluster_id is NULL — FK is for narrative_clusters only
        SIGNAL_TYPE_TEMPLATE_MATCH,
        description,
        evidence,
        now,
    )

    analyst_signals_fired_total.labels(severity=template_severity).inc()
    log.info(
        "template_signals.signal_fired",
        signal_id=signal_id,
        topic_id=topic_id,
        template_name=template_name,
        match_count=match_count,
        confidence=confidence,
        severity=template_severity,
    )
    return signal_id


# ---------------------------------------------------------------------------
# Check cycle
# ---------------------------------------------------------------------------

BroadcastFn = Callable[[dict], Awaitable[None]]


async def check_template_signals(
    pool: asyncpg.Pool,
    broadcast: BroadcastFn,
) -> int:
    """One check pass: query breaching template matches, fire signals.

    Returns count of signals fired.
    """
    fired = 0

    async with pool.acquire() as conn:
        matches = await conn.fetch(SQL_BREACHING_TEMPLATE_MATCHES)

        for row in matches:
            template_name: str = row["template_name"]
            template_display: str = row["template_display"]
            template_severity: str = row["template_severity"]
            legal_sections: list[str] = row["template_legal_sections"]
            topic_id: str = row["topic_id"]
            match_count: int = row["match_count"]
            max_confidence: float = row["max_confidence"]

            # Severity-gated threshold check
            threshold = compute_template_match_threshold(template_severity)
            if match_count < threshold:
                continue

            now = datetime.now(timezone.utc)

            # Fetch highest-confidence matching content item for evidence
            latest = await conn.fetchrow(
                SQL_LATEST_TEMPLATE_MATCH_ITEM,
                topic_id,
                template_name,
            )

            content_item_id = latest["content_item_id"] if latest else ""
            confidence = float(latest["confidence"]) if latest else max_confidence
            # Extract matched_keywords and extracted_identifiers from labels
            matched_keywords: list[str] = []
            extracted_identifiers: dict = {}
            if latest and latest["item_labels"]:
                try:
                    raw = latest["item_labels"]
                    labels = json.loads(raw) if isinstance(raw, str) else raw
                    matched_keywords = labels.get("matched_keywords", [])
                    extracted_identifiers = labels.get("extracted_identifiers", {})
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass

            signal_id = await fire_template_signal(
                conn,
                topic_id=topic_id,
                template_name=template_name,
                template_display=template_display,
                template_severity=template_severity,
                confidence=confidence,
                matched_keywords=matched_keywords,
                extracted_identifiers=extracted_identifiers,
                legal_sections=legal_sections,
                content_item_id=content_item_id,
                match_count=match_count,
                now=now,
            )

            if signal_id:
                payload = build_template_signal_payload(
                    signal_id=signal_id,
                    topic_id=topic_id,
                    template_name=template_name,
                    template_display=template_display,
                    template_severity=template_severity,
                    match_count=match_count,
                    max_confidence=max_confidence,
                )
                try:
                    await broadcast(payload)
                except Exception as exc:
                    log.warning(
                        "template_signals.broadcast_failed",
                        signal_id=signal_id,
                        error=str(exc),
                    )
                fired += 1

    return fired
