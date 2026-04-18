"""002_near_duplicates

Near-duplicate detection table for semantic dedup.
Prevents inflated independent_source_count from paraphrased content.

Revision ID: 002
Revises: 001
Create Date: 2026-04-18 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE near_duplicates (
            content_item_a_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            content_item_b_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            similarity_score  FLOAT NOT NULL,
            detected_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels            JSONB NOT NULL DEFAULT
                '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb,
            PRIMARY KEY (content_item_a_id, content_item_b_id),
            CHECK (content_item_a_id < content_item_b_id)
        )
    """)
    op.execute(
        "CREATE INDEX idx_near_dup_a ON near_duplicates(content_item_a_id)"
    )
    op.execute(
        "CREATE INDEX idx_near_dup_b ON near_duplicates(content_item_b_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS near_duplicates")
