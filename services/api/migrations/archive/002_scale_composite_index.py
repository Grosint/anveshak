"""Add composite index for windowed topic queries at scale.

Without this index, queries like:
  WHERE topic_id = $1 AND captured_at >= NOW() - INTERVAL '30 days'
use the single-column idx_content_items_topic, load ALL items for a topic,
then filter by date in memory. At 100K items per topic, this causes
full table scans every 5 minutes (clustering scheduler cycle).

The composite index lets PostgreSQL jump directly to the right topic + date range.

Revision ID: 002
"""

from alembic import op

revision = "002"
down_revision = "001"


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_items_topic_captured
          ON content_items(topic_id, captured_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_content_items_topic_captured")
