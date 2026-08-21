"""005_add_analyst_pins

Create analyst_pins table for manual analyst map annotations.
Org-scoped, topic-scoped, with mandatory labels JSONB.

Revision ID: 005
Revises: 004
Create Date: 2026-07-10 12:00:00.000000
"""

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE analyst_pins (
            id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
            topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            org_id TEXT NOT NULL REFERENCES organizations(id),
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            analyst_id TEXT NOT NULL REFERENCES users(id),
            labels JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX idx_analyst_pins_topic
        ON analyst_pins(topic_id)
    """)

    op.execute("""
        CREATE INDEX idx_analyst_pins_org
        ON analyst_pins(org_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS analyst_pins")
