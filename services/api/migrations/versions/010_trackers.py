"""010_trackers

Trackers — persistent analyst-owned case files.

New tables:
  - trackers: permanent case files seeded from narrative clusters
  - tracker_content_items: provenance-tracked content linkage (seed/auto/manual)
  - tracker_content_exclusions: rejected items never re-suggested
  - tracker_notes: append-only immutable analyst notes
  - tracker_signals: M:M link between trackers and signals
  - tracker_audit_log: every action logged for audit trail

Modified tables:
  - reports: add nullable tracker_id FK

Sequences:
  - tracker_case_seq: org-scoped case number generator (TRK-YYYY-NNNN)

Revision ID: 010
Revises: 009
Create Date: 2026-06-17 00:00:00.000000
"""
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Sequence for case numbers --
    op.execute("CREATE SEQUENCE IF NOT EXISTS tracker_case_seq START 1")

    # -- 1. trackers (root entity, needs org_id per multi-tenancy rules) --
    op.execute("""
        CREATE TABLE IF NOT EXISTS trackers (
            id                  TEXT        NOT NULL PRIMARY KEY,
            case_number         TEXT        NOT NULL,
            org_id              TEXT,
            topic_id            TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            origin_cluster_id   TEXT        REFERENCES narrative_clusters(id) ON DELETE SET NULL,
            title               TEXT        NOT NULL,
            external_case_ref   TEXT,
            centroid            vector(384),
            centroid_threshold  FLOAT       NOT NULL DEFAULT 0.70,
            status              TEXT        NOT NULL DEFAULT 'watching'
                                            CHECK (status IN ('watching', 'active', 'concluded')),
            priority            TEXT        NOT NULL DEFAULT 'medium'
                                            CHECK (priority IN ('low', 'medium', 'high', 'critical')),
            assigned_to         TEXT,
            created_by          TEXT        NOT NULL,
            concluded_by        TEXT,
            concluded_at        TIMESTAMPTZ,
            closing_summary     TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels              JSONB       NOT NULL DEFAULT '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
        )
    """)

    # -- 2. tracker_content_items (provenance-tracked join table) --
    op.execute("""
        CREATE TABLE IF NOT EXISTS tracker_content_items (
            tracker_id       TEXT NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            content_item_id  TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            attached_by      TEXT NOT NULL CHECK (attached_by IN ('seed', 'auto', 'manual')),
            status           TEXT NOT NULL DEFAULT 'confirmed'
                             CHECK (status IN ('pending', 'confirmed')),
            similarity_score FLOAT,
            confirmed_by     TEXT,
            confirmed_at     TIMESTAMPTZ,
            attached_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (tracker_id, content_item_id)
        )
    """)

    # -- 3. tracker_content_exclusions (rejected items never re-suggested) --
    op.execute("""
        CREATE TABLE IF NOT EXISTS tracker_content_exclusions (
            tracker_id       TEXT NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            content_item_id  TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            excluded_by      TEXT NOT NULL,
            excluded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (tracker_id, content_item_id)
        )
    """)

    # -- 4. tracker_notes (append-only, immutable) --
    op.execute("""
        CREATE TABLE IF NOT EXISTS tracker_notes (
            id          TEXT        NOT NULL PRIMARY KEY,
            tracker_id  TEXT        NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            user_id     TEXT        NOT NULL,
            body        TEXT        NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels      JSONB       NOT NULL DEFAULT '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
        )
    """)

    # -- 5. tracker_signals (M:M) --
    op.execute("""
        CREATE TABLE IF NOT EXISTS tracker_signals (
            tracker_id  TEXT NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            signal_id   TEXT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
            linked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            linked_by   TEXT,
            PRIMARY KEY (tracker_id, signal_id)
        )
    """)

    # -- 6. tracker_audit_log --
    op.execute("""
        CREATE TABLE IF NOT EXISTS tracker_audit_log (
            id          TEXT        NOT NULL PRIMARY KEY,
            tracker_id  TEXT        NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            action      TEXT        NOT NULL,
            actor_id    TEXT        NOT NULL,
            detail      JSONB       NOT NULL DEFAULT '{}',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # -- 7. Add tracker_id FK to reports (nullable, backward-compatible) --
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'reports' AND column_name = 'tracker_id'
            ) THEN
                ALTER TABLE reports ADD COLUMN tracker_id TEXT REFERENCES trackers(id) ON DELETE SET NULL;
            END IF;
        END $$
    """)

    # -- Indexes --
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trackers_case_number ON trackers(case_number)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_trackers_org ON trackers(org_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_trackers_topic ON trackers(topic_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_trackers_status ON trackers(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_trackers_assigned ON trackers(assigned_to)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tracker_content_tracker ON tracker_content_items(tracker_id, attached_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tracker_content_status ON tracker_content_items(tracker_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tracker_notes_tracker ON tracker_notes(tracker_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tracker_audit_tracker ON tracker_audit_log(tracker_id, created_at DESC)")

    # -- Grants --
    op.execute("GRANT ALL ON trackers TO anveshak_worker")
    op.execute("GRANT ALL ON tracker_content_items TO anveshak_worker")
    op.execute("GRANT ALL ON tracker_content_exclusions TO anveshak_worker")
    op.execute("GRANT ALL ON tracker_notes TO anveshak_worker")
    op.execute("GRANT ALL ON tracker_signals TO anveshak_worker")
    op.execute("GRANT ALL ON tracker_audit_log TO anveshak_worker")
    op.execute("GRANT USAGE, SELECT ON SEQUENCE tracker_case_seq TO anveshak_worker")


def downgrade() -> None:
    op.execute("ALTER TABLE reports DROP COLUMN IF EXISTS tracker_id")
    op.execute("DROP TABLE IF EXISTS tracker_audit_log")
    op.execute("DROP TABLE IF EXISTS tracker_signals")
    op.execute("DROP TABLE IF EXISTS tracker_notes")
    op.execute("DROP TABLE IF EXISTS tracker_content_exclusions")
    op.execute("DROP TABLE IF EXISTS tracker_content_items")
    op.execute("DROP TABLE IF EXISTS trackers")
    op.execute("DROP SEQUENCE IF EXISTS tracker_case_seq")
    op.execute("DROP INDEX IF EXISTS idx_trackers_case_number")
    op.execute("DROP INDEX IF EXISTS idx_trackers_org")
    op.execute("DROP INDEX IF EXISTS idx_trackers_topic")
    op.execute("DROP INDEX IF EXISTS idx_trackers_status")
    op.execute("DROP INDEX IF EXISTS idx_trackers_assigned")
    op.execute("DROP INDEX IF EXISTS idx_tracker_content_tracker")
    op.execute("DROP INDEX IF EXISTS idx_tracker_content_status")
    op.execute("DROP INDEX IF EXISTS idx_tracker_notes_tracker")
    op.execute("DROP INDEX IF EXISTS idx_tracker_audit_tracker")
