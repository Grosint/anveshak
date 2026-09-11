"""008_content_feed_publication_time_index

Indexes the expression the content feed's date filter reads.

The feed filters on COALESCE(published_at, captured_at), because publication
time is what an analyst means by a date and capture time is the fallback for
items the platform gave no timestamp for. Migration 006 indexed the bare
column, partially, on published_at IS NOT NULL, and PostgreSQL cannot use
either that index or idx_content_items_topic_captured for a COALESCE
expression. A filtered feed page therefore scans every row of the topic.

The expression index below matches the predicate exactly and leads with
topic_id, which is the first clause of every feed query.

Revision ID: 008
Revises: 007
Create Date: 2026-09-11 14:05:00.000000
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_items_topic_pubtime
        ON content_items(topic_id, (COALESCE(published_at, captured_at)) DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_content_items_topic_pubtime")
