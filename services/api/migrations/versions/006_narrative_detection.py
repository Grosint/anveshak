"""006_narrative_detection

Schema for epic #21: publication time, stance and hostility, Watch Spaces,
and the Candidate Topic inbox.

See docs/narrative_detection_plan.md.

Backfill decision for content_items.published_at (issue #24): pre-existing
rows are left NULL. Before this migration a single column served both
publication time and collection time, and adapters wrote now() whenever the
platform gave them nothing. The two cases are indistinguishable afterwards,
so copying captured_at forward would manufacture publication times that were
never observed. A NULL is honest and the timeline reports it as an excluded
count rather than plotting it.

stance and hostility are columns rather than labels JSONB because the
Sentiment Timeline aggregates them per day across the whole content table,
and per-row JSONB extraction does not hold at that scale.

Revision ID: 006
Revises: 005
Create Date: 2026-09-08 12:00:00.000000
"""

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- content_items: publication time, stance, hostility -----------------
    op.execute("""
        ALTER TABLE content_items
        ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS stance       TEXT,
        ADD COLUMN IF NOT EXISTS hostility    REAL
    """)

    # Stance is a closed set. unsupported_language marks content the model
    # handles poorly, so an analyst knows which part of a chart to distrust
    # rather than seeing it silently scored.
    op.execute("""
        ALTER TABLE content_items
        DROP CONSTRAINT IF EXISTS content_items_stance_check
    """)
    op.execute("""
        ALTER TABLE content_items
        ADD CONSTRAINT content_items_stance_check
        CHECK (stance IS NULL OR stance IN (
            'supporting', 'opposing', 'neutral', 'unsupported_language'
        ))
    """)

    op.execute("""
        ALTER TABLE content_items
        DROP CONSTRAINT IF EXISTS content_items_hostility_range_check
    """)
    op.execute("""
        ALTER TABLE content_items
        ADD CONSTRAINT content_items_hostility_range_check
        CHECK (hostility IS NULL OR (hostility >= 0.0 AND hostility <= 1.0))
    """)

    # The timeline aggregates per topic over publication time and excludes
    # NULLs, so the partial index matches the query exactly.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_items_published
        ON content_items(topic_id, published_at)
        WHERE published_at IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_items_cluster_stance
        ON content_items(narrative_cluster_id, stance)
        WHERE stance IS NOT NULL
    """)

    # -- topics: Watch Space marker and lineage -----------------------------
    op.execute("""
        ALTER TABLE topics
        ADD COLUMN IF NOT EXISTS is_watch_space  BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS parent_topic_id TEXT
            REFERENCES topics(id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_topics_watch_space
        ON topics(is_watch_space) WHERE is_watch_space = TRUE
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_topics_parent
        ON topics(parent_topic_id) WHERE parent_topic_id IS NOT NULL
    """)

    # -- candidate_topics ---------------------------------------------------
    # org_id sits directly on this table because a candidate is reachable by
    # its own UUID. Everything else in the epic inherits organisation scope
    # through topic_id, per the root-tables-only rule.
    op.execute("""
        CREATE TABLE IF NOT EXISTS candidate_topics (
            id                       TEXT        NOT NULL PRIMARY KEY,
            cluster_id               TEXT        NOT NULL
                REFERENCES narrative_clusters(id) ON DELETE CASCADE,
            watch_space_id           TEXT        NOT NULL
                REFERENCES topics(id) ON DELETE CASCADE,
            org_id                   TEXT        NOT NULL REFERENCES organizations(id),
            status                   TEXT        NOT NULL DEFAULT 'pending',
            promoted_topic_id        TEXT        REFERENCES topics(id) ON DELETE SET NULL,
            independent_source_count INTEGER     NOT NULL DEFAULT 0,
            item_count               INTEGER     NOT NULL DEFAULT 0,
            contributing_account_count INTEGER   NOT NULL DEFAULT 0,
            novelty_score            REAL,
            run_count                INTEGER     NOT NULL DEFAULT 1,
            evidence                 JSONB       NOT NULL DEFAULT '{}'::jsonb,
            labels                   JSONB       NOT NULL DEFAULT '{}'::jsonb,
            created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            decided_at               TIMESTAMPTZ
        )
    """)
    op.execute("""
        ALTER TABLE candidate_topics
        DROP CONSTRAINT IF EXISTS candidate_topics_status_check
    """)
    op.execute("""
        ALTER TABLE candidate_topics
        ADD CONSTRAINT candidate_topics_status_check
        CHECK (status IN ('pending', 'accepted', 'dismissed'))
    """)

    # One candidate per cluster. A cluster that persists across runs updates
    # its run_count rather than producing a second inbox row, and a dismissal
    # therefore survives the next detection pass.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_candidate_topics_cluster
        ON candidate_topics(cluster_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_candidate_topics_inbox
        ON candidate_topics(org_id, status, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_candidate_topics_watch_space
        ON candidate_topics(watch_space_id)
    """)

    # Row-level security, matching the policy shape the other org-scoped
    # tables use.
    #
    # It is a safety net that is not yet armed: nothing in services/ executes
    # SET LOCAL app.current_org, so current_setting returns '' and the policy
    # passes everything through. Isolation on this table therefore rests on
    # verify_topic_access() plus the explicit org_id in every query. The
    # policy exists so that arming the request-scoped setting later covers
    # candidate_topics without another migration.
    op.execute("ALTER TABLE candidate_topics ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS org_isolation_candidate_topics ON candidate_topics")
    op.execute("""
        CREATE POLICY org_isolation_candidate_topics ON candidate_topics
        USING (
            current_setting('app.current_org', true) = ''
            OR org_id = current_setting('app.current_org', true)
        )
    """)

    # 001 granted on ALL TABLES once, at 001 time, and there is no ALTER
    # DEFAULT PRIVILEGES anywhere, so a table created later is not covered.
    # Background services connect as anveshak_worker (BYPASSRLS).
    op.execute("GRANT ALL ON candidate_topics TO anveshak_worker")


def downgrade() -> None:
    """Reverses the schema. Note the data this discards.

    Dropping stance, hostility and published_at throws away every scored item
    and every collected publication time. Re-upgrading gives back the columns
    but not the values: the scoring pass has to be re-run, and publication
    times are only recoverable for content collected after the re-upgrade.
    """
    # The table takes its policy with it, and DROP POLICY IF EXISTS still
    # raises when the relation is absent, so the table goes first.
    op.execute("DROP TABLE IF EXISTS candidate_topics")

    op.execute("DROP INDEX IF EXISTS idx_topics_parent")
    op.execute("DROP INDEX IF EXISTS idx_topics_watch_space")
    op.execute("ALTER TABLE topics DROP COLUMN IF EXISTS parent_topic_id")
    op.execute("ALTER TABLE topics DROP COLUMN IF EXISTS is_watch_space")

    op.execute("DROP INDEX IF EXISTS idx_content_items_cluster_stance")
    op.execute("DROP INDEX IF EXISTS idx_content_items_published")
    op.execute(
        "ALTER TABLE content_items DROP CONSTRAINT IF EXISTS content_items_hostility_range_check"
    )
    op.execute("ALTER TABLE content_items DROP CONSTRAINT IF EXISTS content_items_stance_check")
    op.execute("""
        ALTER TABLE content_items
        DROP COLUMN IF EXISTS hostility,
        DROP COLUMN IF EXISTS stance,
        DROP COLUMN IF EXISTS published_at
    """)
