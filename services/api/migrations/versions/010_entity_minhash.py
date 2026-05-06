"""010_entity_minhash

Add entity_minhash column to content_items for entity-boosted clustering.
MinHash fingerprint (128 integers) computed from extracted entity texts
at ingestion time. Used to blend entity similarity into HDBSCAN distance
matrix, improving clustering of semantically diverse articles about the
same event.

Revision ID: 010
Revises: 009
Create Date: 2026-05-06 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE content_items
        ADD COLUMN IF NOT EXISTS entity_minhash BIGINT[]
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS entity_minhash")
