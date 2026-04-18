"""005_label_staleness

Add label_generated_at and label_item_hash to narrative_clusters
for detecting stale cluster labels that need regeneration.

Revision ID: 005
Revises: 004
Create Date: 2026-04-18 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE narrative_clusters
        ADD COLUMN label_generated_at TIMESTAMPTZ
    """)
    op.execute("""
        ALTER TABLE narrative_clusters
        ADD COLUMN label_item_hash TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE narrative_clusters DROP COLUMN IF EXISTS label_item_hash")
    op.execute("ALTER TABLE narrative_clusters DROP COLUMN IF EXISTS label_generated_at")
