"""007_candidate_recorded_status

Adds a 'recorded' status to candidate_topics.

Detection records every cluster large enough to consider, so that a cluster
which does not yet qualify still accumulates the persistence history it will
need later. Migration 006 gave that no state to live in: status was
constrained to pending, accepted and dismissed, so a recorded-but-not-yet-
qualifying cluster was written as 'pending' and appeared in the analyst's
inbox exactly like one that had passed all four gates.

That defeated the novelty gate, which exists precisely to keep rediscoveries
of already-tracked Topics out of the inbox, and the persistence gate, which
exists to keep single spikes out of it.

Per the role-constraint-migration-order rule, the CHECK constraint is
replaced before anything writes the new value.

Backfill: existing pending rows are left pending. Detection re-evaluates
every cluster on its next pass and will demote any that do not qualify.

Revision ID: 007
Revises: 006
Create Date: 2026-09-08 14:30:00.000000
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE candidate_topics DROP CONSTRAINT IF EXISTS candidate_topics_status_check"
    )
    op.execute("""
        ALTER TABLE candidate_topics
        ADD CONSTRAINT candidate_topics_status_check
        CHECK (status IN ('recorded', 'pending', 'accepted', 'dismissed'))
    """)

    # The inbox reads pending only, so the index that serves it should too.
    op.execute("DROP INDEX IF EXISTS idx_candidate_topics_inbox")
    op.execute("""
        CREATE INDEX idx_candidate_topics_inbox
        ON candidate_topics(org_id, status, created_at DESC)
    """)


def downgrade() -> None:
    # 'recorded' has no home in the old constraint. Demote those rows rather
    # than let the constraint fail, since a recorded row is by definition one
    # the analyst was never shown.
    op.execute("DELETE FROM candidate_topics WHERE status = 'recorded'")
    op.execute(
        "ALTER TABLE candidate_topics DROP CONSTRAINT IF EXISTS candidate_topics_status_check"
    )
    op.execute("""
        ALTER TABLE candidate_topics
        ADD CONSTRAINT candidate_topics_status_check
        CHECK (status IN ('pending', 'accepted', 'dismissed'))
    """)
