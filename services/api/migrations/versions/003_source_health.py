"""003_source_health

Add health tracking columns to sources table:
  - health_status:        healthy | degraded | down | unverified
  - consecutive_failures: incremented each failed check, reset to 0 on success
  - health_error:         last failure reason (NULL when healthy)

Checked on registration (RSS hard-blocked if unreachable).
Updated daily by scraper check_all_source_health ARQ job.

Revision ID: 003
Revises: 002
Create Date: 2026-04-16
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sources
        ADD COLUMN IF NOT EXISTS health_status TEXT NOT NULL DEFAULT 'unverified'
    """)
    op.execute("""
        ALTER TABLE sources
        ADD COLUMN IF NOT EXISTS consecutive_failures INT NOT NULL DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE sources
        ADD COLUMN IF NOT EXISTS health_error TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE sources DROP COLUMN IF EXISTS health_error")
    op.execute("ALTER TABLE sources DROP COLUMN IF EXISTS consecutive_failures")
    op.execute("ALTER TABLE sources DROP COLUMN IF EXISTS health_status")
