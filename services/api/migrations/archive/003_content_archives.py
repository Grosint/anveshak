"""Add content_archives table for tracking archived content items.

When CONTENT_RETENTION_DAYS > 0, old clustered items are archived to
compressed JSONL files on disk, then deleted from PostgreSQL. This table
tracks what was archived: topic, month, file path, item count.

Revision ID: 003
"""
from alembic import op

revision = "003"
down_revision = "002"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS content_archives (
            id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
            topic_id    TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            month       TEXT        NOT NULL,
            file_path   TEXT        NOT NULL,
            item_count  INTEGER     NOT NULL DEFAULT 0,
            file_size   BIGINT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels      JSONB       NOT NULL DEFAULT '{}',
            UNIQUE (topic_id, month)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_content_archives_topic ON content_archives(topic_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS content_archives CASCADE")
