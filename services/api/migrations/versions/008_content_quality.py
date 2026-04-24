"""008_content_quality

Add content_quality flag, clean_hash for display-time dedup, and title column
for meaningful content display.

Revision ID: 008
Revises: 007
Create Date: 2026-04-23 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # content_quality: 'good' (default) or 'low_quality'
    op.execute("""
        ALTER TABLE content_items
        ADD COLUMN IF NOT EXISTS content_quality TEXT NOT NULL DEFAULT 'good'
    """)

    # clean_hash: SHA-256 of normalised clean_text — for display-time dedup
    op.execute("""
        ALTER TABLE content_items
        ADD COLUMN IF NOT EXISTS clean_hash TEXT
    """)

    # title: extracted from <title> tag or first sentence of clean_text
    op.execute("""
        ALTER TABLE content_items
        ADD COLUMN IF NOT EXISTS title TEXT
    """)

    # Index on clean_hash for DISTINCT ON queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_items_clean_hash
        ON content_items (clean_hash)
    """)

    # executive_summary on narrative_clusters — LLM-generated 2-3 sentence summary
    op.execute("""
        ALTER TABLE narrative_clusters
        ADD COLUMN IF NOT EXISTS executive_summary TEXT
    """)

    # Index on content_quality for filtering
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_items_quality
        ON content_items (content_quality)
        WHERE content_quality = 'low_quality'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_content_items_quality")
    op.execute("DROP INDEX IF EXISTS idx_content_items_clean_hash")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS title")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS clean_hash")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS content_quality")
    op.execute("ALTER TABLE narrative_clusters DROP COLUMN IF EXISTS executive_summary")
