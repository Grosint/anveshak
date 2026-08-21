"""Add audit_trail and failed_jobs tables.

audit_trail: records who did what, when, and from where — defence/LEA requirement.
failed_jobs: dead-letter queue for ARQ jobs that fail after max retries.

Revision ID: 005
"""

from alembic import op

revision = "005"
down_revision = "004"


def upgrade() -> None:
    # Audit trail — user action log
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            id              TEXT        PRIMARY KEY,
            user_id         TEXT        NOT NULL,
            action          TEXT        NOT NULL,
            resource_type   TEXT        NOT NULL,
            resource_id     TEXT        NOT NULL,
            details         JSONB       NOT NULL DEFAULT '{}',
            ip_address      TEXT        NOT NULL DEFAULT '',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels          JSONB       NOT NULL DEFAULT '{}'
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_trail_resource "
        "ON audit_trail(resource_type, resource_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_trail_user ON audit_trail(user_id, created_at DESC)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_created ON audit_trail(created_at DESC)")

    # Dead-letter queue — failed ARQ jobs
    op.execute("""
        CREATE TABLE IF NOT EXISTS failed_jobs (
            id              TEXT        PRIMARY KEY,
            job_id          TEXT        NOT NULL UNIQUE,
            function_name   TEXT        NOT NULL,
            args            TEXT        NOT NULL DEFAULT '',
            error           TEXT        NOT NULL DEFAULT '',
            queue_name      TEXT        NOT NULL DEFAULT '',
            failed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels          JSONB       NOT NULL DEFAULT '{}'
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_failed_jobs_queue "
        "ON failed_jobs(queue_name, failed_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS failed_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_trail CASCADE")
