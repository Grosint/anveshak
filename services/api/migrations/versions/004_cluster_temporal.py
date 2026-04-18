"""004_cluster_temporal

Add archived_at column to narrative_clusters for temporal windowing.
Archived clusters are excluded from signal engine checks.

Revision ID: 004
Revises: 003
Create Date: 2026-04-18 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE narrative_clusters
        ADD COLUMN archived_at TIMESTAMPTZ
    """)
    op.execute("""
        CREATE INDEX idx_clusters_archived
        ON narrative_clusters(archived_at)
        WHERE archived_at IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_clusters_archived")
    op.execute("ALTER TABLE narrative_clusters DROP COLUMN IF EXISTS archived_at")
