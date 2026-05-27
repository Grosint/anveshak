"""Add source discovery tables and forwarding columns.

source_catalog: curated OSINT source knowledge base (Level 0).
catalog_approvals: tracks which catalog entries were approved for which topics.
discovered_sources: unified table for all discovery methods (snowball, forwarding,
    entity_search, llm_suggestion).
content_items: add forwarding columns for Telegram forwarding chain (Level 2).

Revision ID: 006
"""
from alembic import op

revision = "006"
down_revision = "005"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # source_catalog — curated OSINT source knowledge base
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS source_catalog (
            id                          TEXT        PRIMARY KEY,
            name                        TEXT        NOT NULL,
            url_or_handle               TEXT        NOT NULL,
            platform                    TEXT        NOT NULL,
            domain_tags                 TEXT[]      DEFAULT '{}',
            reliability_tier            TEXT        DEFAULT 'C',
            bias_indicator              TEXT        DEFAULT 'unknown',
            risk_level                  TEXT        DEFAULT 'low',
            language                    TEXT        DEFAULT 'en',
            category                    TEXT        DEFAULT 'news',
            description                 TEXT        DEFAULT '',
            subscriber_count            INT,
            activity_frequency          TEXT        DEFAULT 'unknown',
            signal_contribution_count   INT         DEFAULT 0,
            relevance_hit_rate          REAL,
            cluster_participation_rate  REAL,
            topics_approved_count       INT         DEFAULT 0,
            recommendation_rank         TEXT        DEFAULT 'curated',
            created_at                  TIMESTAMPTZ DEFAULT NOW(),
            updated_at                  TIMESTAMPTZ DEFAULT NOW(),
            labels                      JSONB       NOT NULL DEFAULT '{}'
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_source_catalog_handle "
        "ON source_catalog(platform, url_or_handle)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_source_catalog_domain_tags "
        "ON source_catalog USING GIN(domain_tags)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_source_catalog_rank "
        "ON source_catalog(recommendation_rank)"
    )

    # ------------------------------------------------------------------
    # catalog_approvals — tracks analyst approvals of catalog entries
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS catalog_approvals (
            catalog_entry_id    TEXT        NOT NULL REFERENCES source_catalog(id) ON DELETE CASCADE,
            topic_id            TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            source_id           TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            approved_by         TEXT        NOT NULL,
            approved_at         TIMESTAMPTZ DEFAULT NOW(),
            labels              JSONB       NOT NULL DEFAULT '{}',
            PRIMARY KEY (catalog_entry_id, topic_id)
        )
    """)

    # ------------------------------------------------------------------
    # discovered_sources — all discovery methods in one table
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS discovered_sources (
            id                  TEXT        PRIMARY KEY,
            topic_id            TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            domain_or_handle    TEXT        NOT NULL,
            platform            TEXT        DEFAULT 'web',
            discovery_method    TEXT        NOT NULL,
            citation_count      INT         DEFAULT 1,
            confidence_score    REAL,
            evidence            JSONB       DEFAULT '{}',
            status              TEXT        DEFAULT 'pending',
            source_id           TEXT        REFERENCES sources(id),
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW(),
            labels              JSONB       NOT NULL DEFAULT '{}'
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_unique "
        "ON discovered_sources(topic_id, domain_or_handle, discovery_method)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovered_topic_status "
        "ON discovered_sources(topic_id, status)"
    )

    # ------------------------------------------------------------------
    # content_items — Telegram forwarding metadata (Level 2)
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE content_items "
        "ADD COLUMN IF NOT EXISTS forwarded_from_channel_id TEXT"
    )
    op.execute(
        "ALTER TABLE content_items "
        "ADD COLUMN IF NOT EXISTS forwarded_from_channel_name TEXT"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS forwarded_from_channel_name")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS forwarded_from_channel_id")
    op.execute("DROP TABLE IF EXISTS discovered_sources CASCADE")
    op.execute("DROP TABLE IF EXISTS catalog_approvals CASCADE")
    op.execute("DROP TABLE IF EXISTS source_catalog CASCADE")
