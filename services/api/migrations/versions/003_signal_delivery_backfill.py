"""003_signal_delivery_backfill

Two additive changes required for Phase 2 completion:

1. signals.delivered_at — tracks when a signal was pushed to WebSocket clients.
   The API's signal_delivery_loop sets this after a successful broadcast so
   signals are never re-delivered on restart.

2. topic_content_items — join table for historical backfill (criterion 2.9).
   Allows an existing content_item (owned by one topic) to be semantically
   associated with a second topic discovered later.  Does NOT change the
   UNIQUE(content_hash) constraint on content_items — dedup is unchanged.

Revision ID: 003
Revises: 002
Create Date: 2026-04-14 00:00:00.000000
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. signals.delivered_at
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE signals
        ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ
    """)
    # Partial index — only undelivered signals are scanned by delivery loop
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_signals_undelivered
        ON signals(created_at ASC)
        WHERE delivered_at IS NULL
    """)

    # ------------------------------------------------------------------
    # 2. topic_content_items (backfill join table)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS topic_content_items (
            topic_id         TEXT        NOT NULL
                REFERENCES topics(id)        ON DELETE CASCADE,
            content_item_id  TEXT        NOT NULL
                REFERENCES content_items(id) ON DELETE CASCADE,
            similarity_score FLOAT       NOT NULL DEFAULT 0.0,
            assigned_at      TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (topic_id, content_item_id)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_tci_topic
        ON topic_content_items(topic_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_tci_content_item
        ON topic_content_items(content_item_id)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tci_content_item")
    op.execute("DROP INDEX IF EXISTS idx_tci_topic")
    op.execute("DROP TABLE IF EXISTS topic_content_items")
    op.execute("DROP INDEX IF EXISTS idx_signals_undelivered")
    op.execute("ALTER TABLE signals DROP COLUMN IF EXISTS delivered_at")
