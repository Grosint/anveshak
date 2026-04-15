"""002_content_items_cluster_fk

Add narrative_cluster_id FK to content_items for cluster membership tracking.

Revision ID: 002
Revises: 001
Create Date: 2026-04-14 00:00:00.000000
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE content_items
        ADD COLUMN IF NOT EXISTS narrative_cluster_id TEXT
            REFERENCES narrative_clusters(id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_items_cluster
        ON content_items(narrative_cluster_id)
        WHERE narrative_cluster_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_content_items_cluster")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS narrative_cluster_id")
