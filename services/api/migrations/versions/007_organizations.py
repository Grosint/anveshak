"""007_organizations

Add multi-tenancy: organizations table, org_id on users/topics/sources/
content_items/credibility_audit_log, org_sources visibility table.

Revision ID: 007
Revises: 006
Create Date: 2026-05-29 00:00:00.000000
"""
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Organizations table
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE organizations (
            id          TEXT        NOT NULL PRIMARY KEY,
            name        TEXT        NOT NULL UNIQUE,
            slug        TEXT        NOT NULL UNIQUE,
            is_active   BOOLEAN     NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels      JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)

    # ------------------------------------------------------------------
    # 2. Default organization — backfill target
    # ------------------------------------------------------------------
    op.execute("""
        INSERT INTO organizations (id, name, slug, labels)
        VALUES (
            'org-anshul',
            'Anshul',
            'anshul',
            '{"classification":"OPEN","domain":"platform"}'::jsonb
        )
    """)

    # ------------------------------------------------------------------
    # 3. Add org_id columns (nullable first for backfill)
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE users ADD COLUMN org_id TEXT")
    op.execute("ALTER TABLE topics ADD COLUMN org_id TEXT")
    op.execute("ALTER TABLE sources ADD COLUMN org_id TEXT")
    op.execute("ALTER TABLE content_items ADD COLUMN org_id TEXT")
    op.execute("ALTER TABLE credibility_audit_log ADD COLUMN org_id TEXT")

    # ------------------------------------------------------------------
    # 4. Backfill existing data to default org
    # ------------------------------------------------------------------
    op.execute("UPDATE users SET org_id = 'org-anshul' WHERE org_id IS NULL")
    op.execute("UPDATE topics SET org_id = 'org-anshul' WHERE org_id IS NULL")
    op.execute("UPDATE sources SET org_id = 'org-anshul' WHERE org_id IS NULL")
    op.execute("UPDATE content_items SET org_id = 'org-anshul' WHERE org_id IS NULL")
    op.execute(
        "UPDATE credibility_audit_log SET org_id = 'org-anshul' WHERE org_id IS NULL"
    )

    # ------------------------------------------------------------------
    # 5. Set NOT NULL + FK constraints
    #    users.org_id stays NULLABLE (super-admin has NULL)
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE topics
        ALTER COLUMN org_id SET NOT NULL,
        ADD CONSTRAINT fk_topics_org FOREIGN KEY (org_id) REFERENCES organizations(id)
    """)
    op.execute("""
        ALTER TABLE content_items
        ALTER COLUMN org_id SET NOT NULL,
        ADD CONSTRAINT fk_content_items_org FOREIGN KEY (org_id) REFERENCES organizations(id)
    """)
    op.execute("""
        ALTER TABLE credibility_audit_log
        ALTER COLUMN org_id SET NOT NULL,
        ADD CONSTRAINT fk_credibility_audit_org FOREIGN KEY (org_id) REFERENCES organizations(id)
    """)
    # sources.org_id: NOT NULL but no FK (sources are global, org_id is creator's org)
    op.execute("ALTER TABLE sources ALTER COLUMN org_id SET NOT NULL")
    # users.org_id: nullable FK (super-admin has NULL)
    op.execute("""
        ALTER TABLE users
        ADD CONSTRAINT fk_users_org FOREIGN KEY (org_id) REFERENCES organizations(id)
    """)

    # ------------------------------------------------------------------
    # 6. Indexes for filtered list queries
    # ------------------------------------------------------------------
    op.execute("CREATE INDEX idx_topics_org ON topics(org_id)")
    op.execute("CREATE INDEX idx_sources_org ON sources(org_id)")
    op.execute("CREATE INDEX idx_users_org ON users(org_id)")
    op.execute("CREATE INDEX idx_content_items_org ON content_items(org_id)")
    op.execute("CREATE INDEX idx_credibility_audit_org ON credibility_audit_log(org_id)")

    # ------------------------------------------------------------------
    # 7. org_sources visibility table
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE org_sources (
            org_id    TEXT NOT NULL REFERENCES organizations(id),
            source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            PRIMARY KEY (org_id, source_id)
        )
    """)
    op.execute("CREATE INDEX idx_org_sources_org ON org_sources(org_id)")

    # Backfill org_sources from existing topic_sources
    op.execute("""
        INSERT INTO org_sources (org_id, source_id)
        SELECT DISTINCT t.org_id, ts.source_id
        FROM topic_sources ts
        JOIN topics t ON t.id = ts.topic_id
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS org_sources")
    op.execute("ALTER TABLE credibility_audit_log DROP COLUMN IF EXISTS org_id")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS org_id")
    op.execute("ALTER TABLE sources DROP COLUMN IF EXISTS org_id")
    op.execute("ALTER TABLE topics DROP COLUMN IF EXISTS org_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS org_id")
    op.execute("DROP TABLE IF EXISTS organizations")
