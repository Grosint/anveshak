"""Keyword alert matching — checks content against analyst-defined rules.

Called at the end of analyse_content after NLP enrichment.
Fires are inserted into keyword_alert_triggers table.
Non-critical enrichment: failures are logged, never crash the pipeline.
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

import asyncpg
import structlog

log = structlog.get_logger(__name__)

SQL_ACTIVE_RULES = """
    SELECT id, keywords, match_mode
    FROM keyword_alert_rules
    WHERE topic_id = $1 AND is_active = TRUE
"""

SQL_INSERT_TRIGGER = """
    INSERT INTO keyword_alert_triggers
        (id, rule_id, content_item_id, matched_keywords, triggered_at, labels)
    VALUES ($1, $2, $3, $4, $5,
            '{"classification":"OPEN","domain":"alert","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT DO NOTHING
"""


async def check_keyword_alerts(
    pool: asyncpg.Pool,
    content_item_id: str,
    topic_id: str,
    clean_text: str,
) -> int:
    """Check content against active keyword alert rules for this topic.

    Returns number of rules triggered. Never raises — logs and returns 0 on error.
    """
    try:
        async with pool.acquire() as conn:
            rules = await conn.fetch(SQL_ACTIVE_RULES, topic_id)
            if not rules:
                return 0

            text_lower = clean_text.lower()
            fired = 0
            now = datetime.now(UTC)

            for rule in rules:
                matched = [kw for kw in rule["keywords"] if kw.lower() in text_lower]

                if rule["match_mode"] == "any" and matched:
                    fire = True
                elif rule["match_mode"] == "all" and len(matched) == len(rule["keywords"]):
                    fire = True
                else:
                    fire = False

                if fire:
                    await conn.execute(
                        SQL_INSERT_TRIGGER,
                        str(uuid.uuid4()),
                        rule["id"],
                        content_item_id,
                        matched,
                        now,
                    )
                    fired += 1
                    log.info(
                        "keyword_alert.triggered",
                        rule_id=rule["id"],
                        content_item_id=content_item_id,
                        matched_keywords=matched,
                    )

            return fired
    except Exception as exc:
        log.warning("keyword_alert.check_failed", error=str(exc), topic_id=topic_id)
        return 0
