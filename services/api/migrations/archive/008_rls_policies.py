"""008_rls_policies

Row-Level Security safety net for multi-tenancy.

Policies enforce org isolation at the database level as a secondary
defense behind application-level filtering. Even if a developer forgets
a WHERE clause in a new API endpoint, RLS blocks cross-org data access.

Pattern:
  - Each policy uses current_setting('app.current_org', true)
  - Empty setting ('') bypasses RLS (super-admin / background services)
  - API service sets SET LOCAL app.current_org = <org_id> per request
  - Background services use anveshak_worker role with BYPASSRLS

Revision ID: 008
Revises: 007
Create Date: 2026-05-29 00:00:00.000000
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Enable RLS on org_id tables
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE topics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE content_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE credibility_audit_log ENABLE ROW LEVEL SECURITY")

    # ------------------------------------------------------------------
    # 2. Create policies
    #
    # Pattern: allow access when:
    #   a) org_id matches the session's app.current_org setting, OR
    #   b) the setting is empty '' (super-admin / no context set)
    #
    # current_setting('app.current_org', true) returns '' if not set
    # (the 'true' means missing_ok — no error on unset).
    # ------------------------------------------------------------------

    op.execute("""
        CREATE POLICY org_isolation_topics ON topics
        FOR ALL
        USING (
            current_setting('app.current_org', true) = ''
            OR org_id = current_setting('app.current_org', true)
        )
    """)

    op.execute("""
        CREATE POLICY org_isolation_content_items ON content_items
        FOR ALL
        USING (
            current_setting('app.current_org', true) = ''
            OR org_id = current_setting('app.current_org', true)
        )
    """)

    op.execute("""
        CREATE POLICY org_isolation_users ON users
        FOR ALL
        USING (
            current_setting('app.current_org', true) = ''
            OR org_id = current_setting('app.current_org', true)
            OR org_id IS NULL
        )
    """)

    op.execute("""
        CREATE POLICY org_isolation_credibility_audit ON credibility_audit_log
        FOR ALL
        USING (
            current_setting('app.current_org', true) = ''
            OR org_id = current_setting('app.current_org', true)
        )
    """)

    # ------------------------------------------------------------------
    # 3. Worker role with BYPASSRLS
    #
    # Background services (scraper, analyst, reporter, social, vision)
    # connect with this role to bypass RLS. They have topic_id context
    # from job payloads and don't need row-level filtering.
    # ------------------------------------------------------------------

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anveshak_worker') THEN
                CREATE ROLE anveshak_worker WITH LOGIN BYPASSRLS;
            END IF;
        END $$
    """)

    # Grant the worker role access to all tables
    op.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO anveshak_worker")
    op.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anveshak_worker")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS org_isolation_topics ON topics")
    op.execute("DROP POLICY IF EXISTS org_isolation_content_items ON content_items")
    op.execute("DROP POLICY IF EXISTS org_isolation_users ON users")
    op.execute("DROP POLICY IF EXISTS org_isolation_credibility_audit ON credibility_audit_log")

    op.execute("ALTER TABLE topics DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE content_items DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE credibility_audit_log DISABLE ROW LEVEL SECURITY")

    op.execute("DROP ROLE IF EXISTS anveshak_worker")
