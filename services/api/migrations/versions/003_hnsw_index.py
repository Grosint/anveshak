"""003_hnsw_index

Replace IVFFlat index with HNSW for self-tuning recall at scale.
HNSW requires no training phase and maintains high recall regardless of corpus size.

Revision ID: 003
Revises: 002
Create Date: 2026-04-18 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing IVFFlat index
    op.execute("DROP INDEX IF EXISTS idx_content_items_embedding")
    # Create HNSW index — self-tuning, no training phase, better recall
    # m=16: max connections per layer (hardware.md default)
    # ef_construction=64: build-time search width
    op.execute("""
        CREATE INDEX idx_content_items_embedding
        ON content_items
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_content_items_embedding")
    op.execute("""
        CREATE INDEX idx_content_items_embedding
        ON content_items
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
