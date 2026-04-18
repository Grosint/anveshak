"""006_cross_topic_signals

Add partial index for cross_topic_convergence signal type.

Revision ID: 006
Revises: 005
Create Date: 2026-04-18 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX idx_signals_cross_topic
        ON signals(signal_type)
        WHERE signal_type = 'cross_topic_convergence'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_signals_cross_topic")
