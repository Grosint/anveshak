"""004_report_source_warnings_unique

Add UNIQUE(report_id, source_id) to report_source_warnings to prevent
the check_source_warnings cron from inserting duplicate warning rows on
every 6-hour cycle for the same (report, source) pair.

Deduplication: keeps the earliest row per pair before applying the constraint.

Revision ID: 004
Revises: 003
Create Date: 2026-04-15 00:00:00.000000
"""
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicate rows — keep earliest created_at per (report_id, source_id)
    op.execute("""
        DELETE FROM report_source_warnings a
        USING report_source_warnings b
        WHERE a.id > b.id
          AND a.report_id = b.report_id
          AND a.source_id = b.source_id
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_report_source_warnings_pair
        ON report_source_warnings(report_id, source_id)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_report_source_warnings_pair")
