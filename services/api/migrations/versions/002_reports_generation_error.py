"""002_reports_generation_error

Add generation_error column to reports table so the reporter worker
can write failure reasons that the API can immediately surface to the frontend.

Revision ID: 002
Revises: 001
Create Date: 2026-04-15
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE reports
        ADD COLUMN IF NOT EXISTS generation_error TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE reports DROP COLUMN IF EXISTS generation_error")
