"""003_add_social_handle_identifier_types

Add FACEBOOK_HANDLE and X_HANDLE to the partial index on extracted_entities.
Existing URL_DOMAIN rows are unaffected — new extractions will use the
updated logic that routes social platform URLs to handle types.

Revision ID: 003
Revises: 002
Create Date: 2026-06-29 12:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_entities_identifier_types")
    op.execute("""
        CREATE INDEX idx_entities_identifier_types
        ON extracted_entities(entity_type, entity_text)
        WHERE entity_type IN (
            'PHONE_IN', 'PHONE_INTL', 'UPI', 'EMAIL',
            'CRYPTO_BTC', 'CRYPTO_ETH', 'CRYPTO_TRC20',
            'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE',
            'FACEBOOK_HANDLE', 'X_HANDLE',
            'URL_DOMAIN', 'GSTIN', 'UDYAM', 'PAN', 'IFSC',
            'BANK_ACCOUNT', 'SEBI_REG'
        )
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_entities_identifier_types")
    op.execute("""
        CREATE INDEX idx_entities_identifier_types
        ON extracted_entities(entity_type, entity_text)
        WHERE entity_type IN (
            'PHONE_IN', 'PHONE_INTL', 'UPI', 'EMAIL',
            'CRYPTO_BTC', 'CRYPTO_ETH', 'CRYPTO_TRC20',
            'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE',
            'URL_DOMAIN', 'GSTIN', 'UDYAM', 'PAN', 'IFSC',
            'BANK_ACCOUNT', 'SEBI_REG'
        )
    """)
