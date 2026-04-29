"""009_topic_relevance

Add topic_relevance_score to content_items and per-topic threshold override
to topics. Enables filtering irrelevant content before clustering.

Revision ID: 009
Revises: 008
Create Date: 2026-04-27 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # topic_relevance_score: cosine similarity between content embedding and
    # topic query embedding. NULL = not yet scored (backward compat).
    op.execute("""
        ALTER TABLE content_items
        ADD COLUMN IF NOT EXISTS topic_relevance_score REAL
    """)

    # Per-topic threshold override. NULL = use global default from settings.
    op.execute("""
        ALTER TABLE topics
        ADD COLUMN IF NOT EXISTS topic_relevance_threshold REAL
    """)

    # Partial index for clustering WHERE clause filtering
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_items_relevance
        ON content_items (topic_id, topic_relevance_score)
        WHERE embedding IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_content_items_relevance")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS topic_relevance_score")
    op.execute("ALTER TABLE topics DROP COLUMN IF EXISTS topic_relevance_threshold")
