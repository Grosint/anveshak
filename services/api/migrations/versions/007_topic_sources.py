"""007_topic_sources

Add topic_sources join table so each topic monitors a specific set of sources.
Backfill existing associations from content_items.

Revision ID: 007
Revises: 006
Create Date: 2026-04-20 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE topic_sources (
            topic_id   TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            source_id  TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (topic_id, source_id)
        )
    """)

    # Backfill: derive existing associations from content_items
    op.execute("""
        INSERT INTO topic_sources (topic_id, source_id)
        SELECT DISTINCT ci.topic_id, ci.source_id
        FROM content_items ci
        WHERE ci.topic_id IS NOT NULL
          AND ci.source_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)

    # Also associate all existing active sources with all active topics
    # so current behaviour is preserved until users curate their source lists
    op.execute("""
        INSERT INTO topic_sources (topic_id, source_id)
        SELECT t.id, s.id
        FROM topics t
        CROSS JOIN sources s
        WHERE t.status = 'active' AND s.is_active = TRUE
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS topic_sources")
