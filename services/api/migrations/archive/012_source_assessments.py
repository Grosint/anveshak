"""012_source_assessments

Source Assessment — immutable, topic-scoped source intelligence cards.

New tables:
  - source_assessments: deterministic stats + optional LLM brief per source per topic

Revision ID: 012
Revises: 011
Create Date: 2026-06-22 00:00:00.000000
"""
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS source_assessments (
            id                  TEXT NOT NULL PRIMARY KEY,
            topic_id            TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            source_id           TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            org_id              TEXT NOT NULL,
            time_window_start   TIMESTAMPTZ NOT NULL,
            time_window_end     TIMESTAMPTZ NOT NULL,
            stats               JSONB NOT NULL DEFAULT '{}',
            platform_metadata   JSONB,
            brief_md            TEXT,
            confidence_score    FLOAT,
            source_snapshot     JSONB NOT NULL DEFAULT '{}',
            content_item_count  INT NOT NULL DEFAULT 0,
            generated_at        TIMESTAMPTZ,
            generation_error    TEXT,
            arq_job_id          TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels              JSONB NOT NULL DEFAULT '{}'
        );

        CREATE UNIQUE INDEX IF NOT EXISTS ix_assessment_dedup
            ON source_assessments(topic_id, source_id, time_window_start, time_window_end);
        CREATE INDEX IF NOT EXISTS ix_assessment_list
            ON source_assessments(topic_id, source_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_assessment_org
            ON source_assessments(org_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS source_assessments CASCADE")
