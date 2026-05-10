"""RBAC hardening: token blocklist table and role CHECK constraint.

- token_blocklist: stores revoked JWT IDs (jti) with TTL for logout support
- CHECK constraint on users.role: only 'admin', 'analyst', 'viewer' allowed

Revision ID: 004
"""
from alembic import op

revision = "004"
down_revision = "003"


def upgrade() -> None:
    # Token blocklist for JWT revocation (logout, compromise response)
    op.execute("""
        CREATE TABLE IF NOT EXISTS token_blocklist (
            jti         TEXT        PRIMARY KEY,
            user_id     TEXT        NOT NULL,
            revoked_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at  TIMESTAMPTZ NOT NULL,
            labels      JSONB       NOT NULL DEFAULT '{}'
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_token_blocklist_expires "
        "ON token_blocklist(expires_at)"
    )

    # Add CHECK constraint on users.role (allows viewer for read-only analysts)
    op.execute("""
        ALTER TABLE users
        DROP CONSTRAINT IF EXISTS chk_users_role
    """)
    op.execute("""
        ALTER TABLE users
        ADD CONSTRAINT chk_users_role
        CHECK (role IN ('admin', 'analyst', 'viewer'))
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_role")
    op.execute("DROP TABLE IF EXISTS token_blocklist CASCADE")
