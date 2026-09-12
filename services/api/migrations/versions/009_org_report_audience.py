"""009_org_report_audience

Gives an organisation the audience its reports are addressed to (#57).

Recommended actions in a report were a fixed list of prosecution steps: file an
FIR, request a CDR, refer to ED under PMLA. That is right for the agencies the
scam templates were written for and wrong for a domestic intelligence consumer,
which has none of those powers and produces an assessment rather than a case.

The audience sits on the organisation rather than on the report request,
because a deployment serves one service and every report it generates is
addressed to that service. The column is nullable: an organisation that states
nothing gets the default in infra/configs/audiences/report_actions.yaml, which
ships as the prosecution set, so existing deployments read exactly as before.

No CHECK constraint on the value. The set of audiences is defined in a
versioned file the customer owns, and a constraint here would mean a migration
every time they add one.

Revision ID: 009
Revises: 008
Create Date: 2026-09-12 10:30:00.000000
"""

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS report_audience TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS report_audience")
