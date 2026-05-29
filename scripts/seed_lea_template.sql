-- =============================================================================
-- ANVESHAK — LEA Demo Seed Template
-- =============================================================================
-- INSTRUCTIONS:
--   1. Copy this file: cp seed_lea_template.sql seed_<org_slug>.sql
--   2. Replace all placeholders below with your LEA-specific values
--   3. Add topics, sources, and topic_sources relevant to the LEA
--   4. Run: psql -U anveshak -d anveshak < scripts/seed_<org_slug>.sql
--
-- PLACEHOLDERS TO REPLACE:
--   __ORG_ID__      → e.g. 'org-nia'
--   __ORG_NAME__    → e.g. 'National Investigation Agency'
--   __ORG_SLUG__    → e.g. 'nia'
--   __USER_ID__     → e.g. 'usr-nia-demo-001'
--   __USERNAME__    → e.g. 'demo@nia.anveshak.local'
--   __PASSWORD__    → bcrypt hash (generate: uv run python -c "import bcrypt; print(bcrypt.hashpw(b'YourPassword!', bcrypt.gensalt(12)).decode())")
--   __ADMIN_ID__    → e.g. 'usr-nia-admin-001'
--   __ADMIN_USER__  → e.g. 'admin@nia.anveshak.local'
--   __ADMIN_PASS__  → bcrypt hash for admin password
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. ORGANIZATION
-- =============================================================================

INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
VALUES (
    '__ORG_ID__',
    '__ORG_NAME__',
    '__ORG_SLUG__',
    NOW(),
    NOW(),
    '{"classification": "OPEN", "domain": "platform"}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 2. USERS (analyst + admin for this org)
-- =============================================================================

INSERT INTO users (id, username, password_hash, role, org_id, created_at, updated_at, labels)
VALUES (
    '__USER_ID__',
    '__USERNAME__',
    '__PASSWORD__',
    'analyst',
    '__ORG_ID__',
    NOW(),
    NOW(),
    '{"classification": "OPEN", "domain": "osint", "owner_org": "__ORG_SLUG__"}'::jsonb
)
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (id, username, password_hash, role, org_id, created_at, updated_at, labels)
VALUES (
    '__ADMIN_ID__',
    '__ADMIN_USER__',
    '__ADMIN_PASS__',
    'admin',
    '__ORG_ID__',
    NOW(),
    NOW(),
    '{"classification": "OPEN", "domain": "osint", "owner_org": "__ORG_SLUG__"}'::jsonb
)
ON CONFLICT (username) DO NOTHING;

-- =============================================================================
-- 3. TOPICS (customize per LEA)
-- =============================================================================
-- Add your LEA-specific monitoring topics here.
-- IMPORTANT: include org_id = '__ORG_ID__' on every INSERT.
--
-- Example:
-- INSERT INTO topics (id, name, keywords, org_id, signal_threshold, status, labels, created_at, updated_at)
-- VALUES (
--     'topic-nia-001',
--     'Cross-border Terror Financing',
--     ARRAY['hawala', 'terror finance', 'FATF', 'money laundering'],
--     '__ORG_ID__',
--     3,
--     'active',
--     '{"classification": "OPEN", "domain": "osint", "owner_org": "__ORG_SLUG__"}'::jsonb,
--     NOW(),
--     NOW()
-- );

-- =============================================================================
-- 4. SOURCES (customize per LEA)
-- =============================================================================
-- Add sources relevant to this LEA's monitoring topics.
-- Sources are global — if the source already exists (e.g. same URL),
-- just link it via org_sources and topic_sources.
--
-- Example:
-- INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, labels, created_at, updated_at)
-- VALUES (
--     'src-nia-001',
--     'FATF Reports',
--     'https://www.fatf-gafi.org',
--     'web',
--     85.0,
--     true,
--     '{"classification": "OPEN", "domain": "web", "owner_org": "__ORG_SLUG__"}'::jsonb,
--     NOW(),
--     NOW()
-- )
-- ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 5. LINK SOURCES TO ORG (visibility)
-- =============================================================================
-- INSERT INTO org_sources (org_id, source_id) VALUES
--     ('__ORG_ID__', 'src-nia-001')
-- ON CONFLICT DO NOTHING;

-- =============================================================================
-- 6. LINK SOURCES TO TOPICS
-- =============================================================================
-- INSERT INTO topic_sources (topic_id, source_id) VALUES
--     ('topic-nia-001', 'src-nia-001')
-- ON CONFLICT DO NOTHING;

COMMIT;

DO $$
BEGIN
    RAISE NOTICE 'LEA seed complete for: __ORG_NAME__';
    RAISE NOTICE 'Analyst: __USERNAME__';
    RAISE NOTICE 'Admin:   __ADMIN_USER__';
END $$;
