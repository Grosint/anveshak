"""Source discovery jobs — snowball, Telegram forwarding, entity search, LLM.

Pure functions for extraction/ranking + async job functions for ARQ scheduling.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from urllib.parse import urlparse

import asyncpg
import structlog

log = structlog.get_logger(__name__)

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

SQL_OUTBOUND_LINKS = r"""
    SELECT DISTINCT ci.url AS source_url,
           unnest(
               regexp_matches(ci.clean_text, 'https?://[^\s<>"'']+', 'g')
           ) AS outbound_url
    FROM content_items ci
    WHERE ci.topic_id = $1
      AND ci.clean_text ~ 'https?://'
    LIMIT 2000
"""

SQL_EXISTING_SOURCE_URLS = """
    SELECT url_or_handle FROM sources WHERE is_active = TRUE
"""

SQL_UPSERT_DISCOVERED = """
    INSERT INTO discovered_sources
        (id, topic_id, domain_or_handle, platform, discovery_method,
         citation_count, confidence_score, evidence, status,
         created_at, updated_at, labels)
    VALUES ($1, $2, $3, 'web', 'snowball', $4, $5, $6, 'pending', $7, $7, $8)
    ON CONFLICT (topic_id, domain_or_handle, discovery_method)
    DO UPDATE SET
        citation_count = EXCLUDED.citation_count,
        confidence_score = EXCLUDED.confidence_score,
        updated_at = EXCLUDED.updated_at
"""

SQL_FORWARDING_AGGREGATION = """
    SELECT forwarded_from_channel_id,
           forwarded_from_channel_name,
           COUNT(*) AS forward_count
    FROM content_items
    WHERE topic_id = $1
      AND forwarded_from_channel_id IS NOT NULL
    GROUP BY forwarded_from_channel_id, forwarded_from_channel_name
    ORDER BY forward_count DESC
    LIMIT 50
"""

SQL_UPSERT_DISCOVERED_FORWARDING = """
    INSERT INTO discovered_sources
        (id, topic_id, domain_or_handle, platform, discovery_method,
         citation_count, confidence_score, evidence, status,
         created_at, updated_at, labels)
    VALUES ($1, $2, $3, 'telegram', 'forwarding', $4, $5, $6, 'pending', $7, $7, $8)
    ON CONFLICT (topic_id, domain_or_handle, discovery_method)
    DO UPDATE SET
        citation_count = EXCLUDED.citation_count,
        confidence_score = EXCLUDED.confidence_score,
        updated_at = EXCLUDED.updated_at
"""

SQL_TOP_ENTITIES = """
    SELECT entity_text, entity_type, COUNT(*) AS mention_count
    FROM extracted_entities
    WHERE content_item_id IN (
        SELECT id FROM content_items WHERE topic_id = $1
    )
    GROUP BY entity_text, entity_type
    ORDER BY mention_count DESC
    LIMIT $2
"""

SQL_UPSERT_DISCOVERED_ENTITY = """
    INSERT INTO discovered_sources
        (id, topic_id, domain_or_handle, platform, discovery_method,
         citation_count, confidence_score, evidence, status,
         created_at, updated_at, labels)
    VALUES ($1, $2, $3, $4, 'entity_search', $5, $6, $7, 'pending', $8, $8, $9)
    ON CONFLICT (topic_id, domain_or_handle, discovery_method)
    DO UPDATE SET
        citation_count = EXCLUDED.citation_count,
        updated_at = EXCLUDED.updated_at
"""


# ---------------------------------------------------------------------------
# Pure functions — snowball
# ---------------------------------------------------------------------------


def extract_domains_with_frequency(
    link_rows: list[dict[str, str]],
) -> dict[str, int]:
    """Extract domains from outbound URLs and count citation frequency.

    Args:
        link_rows: rows with 'outbound_url' key from SQL_OUTBOUND_LINKS.

    Returns:
        Dict mapping domain → citation count.
    """
    domain_counts: Counter[str] = Counter()
    for row in link_rows:
        url = row.get("outbound_url", "")
        if not url:
            continue
        try:
            parsed = urlparse(url)
            if parsed.netloc:
                domain_counts[parsed.netloc] += 1
        except Exception as exc:
            log.debug("discovery.url_parse_error", url=url[:100], error=str(exc))
            continue
    return dict(domain_counts)


def filter_existing_domains(
    domain_counts: dict[str, int],
    existing_domains: set[str],
) -> dict[str, int]:
    """Remove domains that are already registered as sources."""
    return {
        domain: count for domain, count in domain_counts.items() if domain not in existing_domains
    }


def sorted_suggestions(
    domain_counts: dict[str, int],
) -> list[tuple[str, int]]:
    """Sort domain suggestions by citation frequency DESC."""
    return sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# ARQ job — snowball discovery
# ---------------------------------------------------------------------------


async def discover_snowball_sources(
    pool: asyncpg.Pool,
    topic_id: str,
) -> int:
    """Extract outbound URLs from content, rank by frequency, persist to discovered_sources.

    Returns number of new/updated discovered sources.
    """
    async with pool.acquire() as conn:
        # Fetch outbound links
        link_rows = await conn.fetch(SQL_OUTBOUND_LINKS, topic_id)
        if not link_rows:
            log.info("discovery.snowball.no_links", topic_id=topic_id)
            return 0

        # Extract domains with frequency
        domain_counts = extract_domains_with_frequency([dict(r) for r in link_rows])

        # Fetch existing source domains
        existing_rows = await conn.fetch(SQL_EXISTING_SOURCE_URLS)
        existing_domains: set[str] = set()
        for row in existing_rows:
            try:
                parsed = urlparse(row["url_or_handle"])
                if parsed.netloc:
                    existing_domains.add(parsed.netloc)
            except Exception:
                existing_domains.add(row["url_or_handle"])  # non-URL handle (e.g. @channel)

        # Filter and sort
        new_domains = filter_existing_domains(domain_counts, existing_domains)
        suggestions = sorted_suggestions(new_domains)

        # Upsert top 50
        now = datetime.now(UTC)
        count = 0
        for domain, citation_count in suggestions[:50]:
            confidence = min(1.0, citation_count / 10.0)
            await conn.execute(
                SQL_UPSERT_DISCOVERED,
                str(uuid.uuid4()),
                topic_id,
                domain,
                citation_count,
                confidence,
                json.dumps({"citation_count": citation_count}),
                now,
                LABELS_JSON,
            )
            count += 1

        log.info(
            "discovery.snowball.complete",
            topic_id=topic_id,
            total_outbound=len(domain_counts),
            new_suggestions=count,
        )
        return count


# ---------------------------------------------------------------------------
# ARQ job — Telegram forwarding chain discovery
# ---------------------------------------------------------------------------


async def discover_telegram_channels(
    pool: asyncpg.Pool,
    topic_id: str,
) -> int:
    """Discover Telegram channels from forwarding metadata.

    Aggregates forwarded_from_channel_id from content_items and upserts
    into discovered_sources with discovery_method='forwarding'.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(SQL_FORWARDING_AGGREGATION, topic_id)
        if not rows:
            log.info("discovery.forwarding.no_forwards", topic_id=topic_id)
            return 0

        # Filter out already-registered channels
        existing_rows = await conn.fetch(SQL_EXISTING_SOURCE_URLS)
        existing_handles = {r["url_or_handle"] for r in existing_rows}

        now = datetime.now(UTC)
        count = 0
        for row in rows:
            channel_id = row["forwarded_from_channel_id"]
            channel_name = row["forwarded_from_channel_name"] or channel_id
            forward_count = row["forward_count"]

            # Skip if already registered
            handle = f"@{channel_id}" if not channel_id.startswith("@") else channel_id
            if handle in existing_handles or channel_id in existing_handles:
                continue

            confidence = min(1.0, forward_count / 10.0)
            evidence = {
                "channel_name": channel_name,
                "forward_count": forward_count,
            }

            await conn.execute(
                SQL_UPSERT_DISCOVERED_FORWARDING,
                str(uuid.uuid4()),
                topic_id,
                handle,
                forward_count,
                confidence,
                json.dumps(evidence),
                now,
                LABELS_JSON,
            )
            count += 1

        log.info(
            "discovery.forwarding.complete",
            topic_id=topic_id,
            channels_found=count,
        )
        return count


# ---------------------------------------------------------------------------
# ARQ job — Entity-based discovery
# ---------------------------------------------------------------------------


async def discover_entity_sources(
    pool: asyncpg.Pool,
    topic_id: str,
    top_n_entities: int = 10,
) -> int:
    """Search for entities across platforms not yet monitored.

    Extracts top entities from NLP output, searches each enabled platform
    adapter, and upserts results into discovered_sources.
    """
    async with pool.acquire() as conn:
        entity_rows = await conn.fetch(SQL_TOP_ENTITIES, topic_id, top_n_entities)
        if not entity_rows:
            log.info("discovery.entity.no_entities", topic_id=topic_id)
            return 0

        entities = [
            {"text": r["entity_text"], "type": r["entity_type"], "count": r["mention_count"]}
            for r in entity_rows
        ]

        # Fetch existing source handles
        existing_rows = await conn.fetch(SQL_EXISTING_SOURCE_URLS)
        existing_handles = {r["url_or_handle"] for r in existing_rows}

        now = datetime.now(UTC)
        count = 0

        # For now, create entity-based suggestions as web search recommendations
        # Platform adapter search() methods will be added in implementation
        for entity in entities:
            search_domain = f"search:{entity['text']}"
            if search_domain in existing_handles:
                continue

            evidence = {
                "entity_text": entity["text"],
                "entity_type": entity["type"],
                "mention_count": entity["count"],
            }
            await conn.execute(
                SQL_UPSERT_DISCOVERED_ENTITY,
                str(uuid.uuid4()),
                topic_id,
                search_domain,
                "web",
                entity["count"],
                min(1.0, entity["count"] / 20.0),
                json.dumps(evidence),
                now,
                LABELS_JSON,
            )
            count += 1

        log.info(
            "discovery.entity.complete",
            topic_id=topic_id,
            entities_searched=len(entities),
            suggestions=count,
        )
        return count
