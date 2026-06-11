"""009_engine_c

Engine C — Identifier Intelligence schema.

New tables:
  - scam_templates: fraud/info-op template definitions with keywords and embeddings
  - topic_templates: many-to-many join between topics and templates
  - identifier_clusters: groups content items sharing the same identifier
  - identifier_cluster_items: junction table for identifier clusters

Modified tables:
  - topics: add identifier_signal_threshold column

New indexes:
  - idx_entities_identifier_types: partial index for fast Engine C identifier filtering
  - idx_ic_topic_type_value: UNIQUE on (topic_id, identifier_type, identifier_value)
  - idx_ic_source_count: sort index on (topic_id, source_count DESC)

Seed data:
  - 11 built-in scam/narco templates with keywords, severity, legal sections

Revision ID: 009
Revises: 008
Create Date: 2026-06-11 00:00:00.000000
"""
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. scam_templates table
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS scam_templates (
            id                   TEXT PRIMARY KEY,
            org_id               TEXT REFERENCES organizations(id),
            name                 TEXT NOT NULL,
            display              TEXT NOT NULL,
            category             TEXT NOT NULL
                CHECK (category IN ('fraud', 'info_op', 'narco', 'custom')),
            keywords             TEXT[] NOT NULL DEFAULT '{}',
            min_keyword_hits     INT NOT NULL DEFAULT 3,
            expected_identifiers TEXT[] DEFAULT '{}',
            severity             TEXT NOT NULL DEFAULT 'MEDIUM'
                CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
            reference_embedding  vector(384),
            legal_sections       TEXT[] DEFAULT '{}',
            is_builtin           BOOLEAN DEFAULT FALSE,
            is_active            BOOLEAN DEFAULT TRUE,
            created_at           TIMESTAMPTZ DEFAULT NOW(),
            updated_at           TIMESTAMPTZ DEFAULT NOW(),
            labels               JSONB NOT NULL DEFAULT
                '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
        )
    """)

    # ------------------------------------------------------------------
    # 2. topic_templates join table
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS topic_templates (
            topic_id    TEXT REFERENCES topics(id) ON DELETE CASCADE,
            template_id TEXT REFERENCES scam_templates(id) ON DELETE CASCADE,
            PRIMARY KEY (topic_id, template_id)
        )
    """)

    # ------------------------------------------------------------------
    # 3. identifier_clusters table
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS identifier_clusters (
            id                  TEXT PRIMARY KEY,
            topic_id            TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            identifier_type     TEXT NOT NULL,
            identifier_value    TEXT NOT NULL,
            source_count        INT NOT NULL DEFAULT 0,
            content_item_count  INT NOT NULL DEFAULT 0,
            first_seen_at       TIMESTAMPTZ,
            last_seen_at        TIMESTAMPTZ,
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW(),
            labels              JSONB NOT NULL DEFAULT
                '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ic_topic_type_value
            ON identifier_clusters(topic_id, identifier_type, identifier_value)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ic_source_count
            ON identifier_clusters(topic_id, source_count DESC)
    """)

    # ------------------------------------------------------------------
    # 4. identifier_cluster_items junction table
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS identifier_cluster_items (
            identifier_cluster_id TEXT REFERENCES identifier_clusters(id)
                ON DELETE CASCADE,
            content_item_id       TEXT REFERENCES content_items(id)
                ON DELETE CASCADE,
            source_id             TEXT NOT NULL,
            PRIMARY KEY (identifier_cluster_id, content_item_id)
        )
    """)

    # ------------------------------------------------------------------
    # 5. topics: add identifier_signal_threshold
    # ------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'topics'
                  AND column_name = 'identifier_signal_threshold'
            ) THEN
                ALTER TABLE topics
                    ADD COLUMN identifier_signal_threshold INT NOT NULL DEFAULT 2;
            END IF;
        END $$
    """)

    # ------------------------------------------------------------------
    # 6. Partial index on extracted_entities for Engine C identifier types
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 7. Seed 11 built-in templates
    # ------------------------------------------------------------------
    op.execute("""
        INSERT INTO scam_templates
            (id, org_id, name, display, category, keywords, min_keyword_hits,
             expected_identifiers, severity, legal_sections, is_builtin, is_active, labels)
        VALUES
            ('tpl-investment-fraud', NULL, 'investment_fraud',
             'Investment Fraud', 'fraud',
             ARRAY['guaranteed returns', 'double your money', 'investment opportunity',
                   'high returns', 'risk free', 'fixed income', 'monthly returns',
                   'trading platform', 'forex', 'binary options'],
             3, ARRAY['UPI', 'CRYPTO_BTC', 'CRYPTO_ETH', 'PHONE_IN', 'BANK_ACCOUNT'],
             'CRITICAL',
             ARRAY['IPC 420', 'SEBI (PFUTP) Regulations', 'PMLA Section 3'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-mule-recruitment', NULL, 'mule_recruitment',
             'Mule Account Recruitment', 'fraud',
             ARRAY['bank account', 'commission', 'per transaction', 'easy money',
                   'rent your account', 'lend account', 'account for sale',
                   'daily income', 'no risk', 'passive income'],
             3, ARRAY['PHONE_IN', 'UPI', 'TELEGRAM_HANDLE', 'BANK_ACCOUNT'],
             'CRITICAL',
             ARRAY['PMLA Section 3', 'PMLA Section 4', 'IPC 420', 'IT Act 66D'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-maas', NULL, 'maas',
             'Mule-as-a-Service', 'fraud',
             ARRAY['mule service', 'account provider', 'clean account', 'fresh account',
                   'bulk accounts', 'verified account', 'KYC done', 'ready to use',
                   'account supply', 'wholesale accounts'],
             3, ARRAY['PHONE_IN', 'UPI', 'TELEGRAM_HANDLE', 'BANK_ACCOUNT'],
             'CRITICAL',
             ARRAY['PMLA Section 3', 'PMLA Section 4', 'IT Act 66D'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-digital-arrest', NULL, 'digital_arrest',
             'Digital Arrest Scam', 'fraud',
             ARRAY['police', 'arrest warrant', 'CBI', 'narcotics', 'money laundering',
                   'Aadhaar linked', 'court order', 'video call verification',
                   'stay on the line', 'do not tell anyone'],
             3, ARRAY['PHONE_IN', 'UPI', 'BANK_ACCOUNT'],
             'HIGH',
             ARRAY['IPC 419', 'IPC 420', 'IT Act 66C', 'IT Act 66D'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-job-fraud', NULL, 'job_fraud',
             'Job Fraud', 'fraud',
             ARRAY['work from home', 'data entry job', 'part time job', 'registration fee',
                   'guaranteed placement', 'earn daily', 'typing job',
                   'no experience needed', 'immediate joining', 'refundable deposit'],
             3, ARRAY['PHONE_IN', 'UPI', 'EMAIL', 'TELEGRAM_HANDLE'],
             'HIGH',
             ARRAY['IPC 420', 'IT Act 66D'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-pump-and-dump', NULL, 'pump_and_dump',
             'Pump and Dump', 'fraud',
             ARRAY['multibagger', 'target price', 'buy now', 'insider tip',
                   'guaranteed profit', 'small cap gem', 'operator stock',
                   'breaking out', 'SEBI registered', 'free tips'],
             3, ARRAY['PHONE_IN', 'TELEGRAM_HANDLE', 'SEBI_REG'],
             'CRITICAL',
             ARRAY['SEBI (PFUTP) Regulations 2003', 'SEBI Act Section 12A',
                   'IPC 420', 'Companies Act Section 447'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-fake-research-report', NULL, 'fake_research_report',
             'Fake Research Report', 'fraud',
             ARRAY['research report', 'analyst recommendation', 'strong buy',
                   'price target', 'institutional pick', 'confidential report',
                   'leaked report', 'brokerage recommendation', 'fundamental analysis'],
             3, ARRAY['TELEGRAM_HANDLE', 'EMAIL', 'PHONE_IN'],
             'HIGH',
             ARRAY['SEBI (Research Analysts) Regulations 2014',
                   'SEBI (PFUTP) Regulations 2003', 'IPC 468'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-drug-sale', NULL, 'drug_sale',
             'Drug Sale', 'narco',
             ARRAY['stuff', 'maal', 'product available', 'best quality',
                   'delivery available', 'discreet shipping', 'bulk order',
                   'sample available', 'wickr', 'drop location'],
             3, ARRAY['PHONE_IN', 'TELEGRAM_HANDLE', 'CRYPTO_BTC', 'CRYPTO_TRC20'],
             'HIGH',
             ARRAY['NDPS Act Section 20', 'NDPS Act Section 22',
                   'NDPS Act Section 25', 'NDPS Act Section 29'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-drug-delivery-recruitment', NULL, 'drug_delivery_recruitment',
             'Drug Delivery Recruitment', 'narco',
             ARRAY['delivery boy', 'courier needed', 'parcel delivery', 'good pay',
                   'no questions asked', 'cash on delivery', 'pickup and drop',
                   'night shift', 'own vehicle', 'local delivery'],
             3, ARRAY['PHONE_IN', 'TELEGRAM_HANDLE'],
             'HIGH',
             ARRAY['NDPS Act Section 25', 'NDPS Act Section 27A',
                   'NDPS Act Section 29'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-fake-sim-sale', NULL, 'fake_sim_sale',
             'Fake SIM Card Sale', 'fraud',
             ARRAY['SIM card', 'pre-activated', 'no KYC', 'anonymous SIM',
                   'bulk SIM', 'ready to use SIM', 'Jio SIM', 'Airtel SIM',
                   'document not required', 'instant activation'],
             3, ARRAY['PHONE_IN', 'TELEGRAM_HANDLE', 'UPI'],
             'MEDIUM',
             ARRAY['Indian Telegraph Act Section 20', 'IT Act 66C',
                   'IPC 420', 'IPC 468'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-crypto-cashout', NULL, 'crypto_cashout',
             'Crypto Cashout Service', 'fraud',
             ARRAY['crypto to cash', 'USDT to INR', 'BTC to bank', 'cash out',
                   'no KYC exchange', 'P2P transfer', 'instant withdrawal',
                   'best rate', 'OTC deal', 'hawala crypto'],
             3, ARRAY['CRYPTO_BTC', 'CRYPTO_ETH', 'CRYPTO_TRC20', 'UPI',
                      'BANK_ACCOUNT', 'PHONE_IN'],
             'HIGH',
             ARRAY['PMLA Section 3', 'FEMA Section 3', 'IT Act 66D'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)

        ON CONFLICT (id) DO NOTHING
    """)

    # Grant worker role access to new tables
    op.execute("GRANT ALL ON scam_templates TO anveshak_worker")
    op.execute("GRANT ALL ON topic_templates TO anveshak_worker")
    op.execute("GRANT ALL ON identifier_clusters TO anveshak_worker")
    op.execute("GRANT ALL ON identifier_cluster_items TO anveshak_worker")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS identifier_cluster_items")
    op.execute("DROP TABLE IF EXISTS identifier_clusters")
    op.execute("DROP TABLE IF EXISTS topic_templates")
    op.execute("DROP TABLE IF EXISTS scam_templates")
    op.execute("DROP INDEX IF EXISTS idx_entities_identifier_types")
    op.execute("""
        ALTER TABLE topics DROP COLUMN IF EXISTS identifier_signal_threshold
    """)
