"""013_phone_intl

Add PHONE_INTL to extracted_entities partial index for international phone
number extraction (Engine C). Updates scam templates to expect PHONE_INTL.

Revision ID: 013
Revises: 012
Create Date: 2026-06-23 00:00:00.000000
"""
from alembic import op

revision = "013"
down_revision = "012"


def upgrade() -> None:
    # Recreate partial index with PHONE_INTL added
    op.execute("DROP INDEX IF EXISTS idx_entities_identifier_types")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_entities_identifier_types
            ON extracted_entities(entity_type, entity_text)
            WHERE entity_type IN (
                'PHONE_IN', 'PHONE_INTL', 'UPI', 'EMAIL', 'CRYPTO_BTC',
                'CRYPTO_ETH', 'CRYPTO_TRC20', 'TELEGRAM_HANDLE',
                'INSTAGRAM_HANDLE', 'URL_DOMAIN', 'GSTIN', 'UDYAM',
                'PAN', 'IFSC', 'BANK_ACCOUNT', 'SEBI_REG'
            )
    """)

    # Add PHONE_INTL to relevant scam templates' expected_identifiers
    op.execute("""
        UPDATE scam_templates
        SET expected_identifiers = array_append(expected_identifiers, 'PHONE_INTL')
        WHERE name IN ('mule_recruitment', 'maas', 'drug_sale', 'crypto_cashout')
          AND NOT ('PHONE_INTL' = ANY(expected_identifiers))
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_entities_identifier_types")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_entities_identifier_types
            ON extracted_entities(entity_type, entity_text)
            WHERE entity_type IN (
                'PHONE_IN', 'UPI', 'EMAIL', 'CRYPTO_BTC', 'CRYPTO_ETH',
                'CRYPTO_TRC20', 'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE',
                'URL_DOMAIN', 'GSTIN', 'UDYAM', 'PAN', 'IFSC',
                'BANK_ACCOUNT', 'SEBI_REG'
            )
    """)

    op.execute("""
        UPDATE scam_templates
        SET expected_identifiers = array_remove(expected_identifiers, 'PHONE_INTL')
        WHERE 'PHONE_INTL' = ANY(expected_identifiers)
    """)
