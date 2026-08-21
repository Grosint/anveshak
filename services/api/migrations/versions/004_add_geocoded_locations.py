"""004_add_geocoded_locations

Create geocoded_locations table for Phase 1 map upgrade.
Separate from extracted_entities per NIA/SA requirement:
- One entity text = one geocode (not N duplicates)
- Org-agnostic (same city = same coords)
- Provenance tracked per geocode, not per entity mention
- Analyst can override without touching evidence table

Revision ID: 004
Revises: 003
Create Date: 2026-07-10 10:00:00.000000
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE geocoded_locations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            entity_text_normalized TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            geocode_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            geocode_source TEXT NOT NULL DEFAULT 'geonamescache',
            alternatives_json JSONB DEFAULT '[]'::jsonb,
            geocoded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (entity_text_normalized, entity_type)
        )
    """)

    op.execute("""
        CREATE INDEX idx_geocoded_locations_text
        ON geocoded_locations(entity_text_normalized)
    """)

    op.execute("""
        CREATE INDEX idx_geocoded_locations_type
        ON geocoded_locations(entity_type)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS geocoded_locations")
