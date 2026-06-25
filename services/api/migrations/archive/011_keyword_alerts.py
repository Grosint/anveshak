"""011_keyword_alerts

Keyword alert rules and triggers for social media monitoring.

New tables:
  - keyword_alert_rules: analyst-defined keyword monitoring rules per topic
  - keyword_alert_triggers: content items that matched alert rules

Revision ID: 011
Revises: 010
Create Date: 2026-06-20 00:00:00.000000
"""
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS keyword_alert_rules (
            id TEXT NOT NULL PRIMARY KEY,
            topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            keywords TEXT[] NOT NULL,
            match_mode TEXT NOT NULL DEFAULT 'any'
                CHECK (match_mode IN ('any', 'all')),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            notify_websocket BOOLEAN NOT NULL DEFAULT TRUE,
            created_by TEXT,
            org_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels JSONB NOT NULL DEFAULT '{"classification":"OPEN","domain":"alert","owner_org":"anveshak"}'
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_keyword_alerts_topic_active
            ON keyword_alert_rules(topic_id) WHERE is_active = TRUE
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS keyword_alert_triggers (
            id TEXT NOT NULL PRIMARY KEY,
            rule_id TEXT NOT NULL REFERENCES keyword_alert_rules(id) ON DELETE CASCADE,
            content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            matched_keywords TEXT[] NOT NULL,
            triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels JSONB NOT NULL DEFAULT '{"classification":"OPEN","domain":"alert","owner_org":"anveshak"}'
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_keyword_triggers_rule_time
            ON keyword_alert_triggers(rule_id, triggered_at DESC)
    """)

    op.execute("GRANT ALL ON keyword_alert_rules TO anveshak_worker")
    op.execute("GRANT ALL ON keyword_alert_triggers TO anveshak_worker")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS keyword_alert_triggers")
    op.execute("DROP TABLE IF EXISTS keyword_alert_rules")
