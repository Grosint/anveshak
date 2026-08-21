"""002_add_orphan_enqueued_at

Add orphan_enqueued_at column to content_items.
The orphan sweep (analyst scheduler) uses this to prevent re-enqueueing
the same content_item within 10 minutes. Without this column, the sweep
query crashes with UndefinedColumnError.

Revision ID: 002
Revises: 001
Create Date: 2026-06-28 12:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE content_items
        ADD COLUMN IF NOT EXISTS orphan_enqueued_at TIMESTAMPTZ
    """)
    # Partial index for orphan sweep query performance
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_orphan_sweep
        ON content_items (created_at)
        WHERE embedding IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_content_orphan_sweep")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS orphan_enqueued_at")
