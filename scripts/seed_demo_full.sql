-- =============================================================================
-- ANVESHAK — Full Demo Seed Data (Clean Slate)
-- Scenario: Multi-domain OSINT monitoring — defence, maritime, border, internal
-- =============================================================================
-- Usage:
--   make seed-demo-full
--   # or: psql -U anveshak -d anveshak < scripts/seed_demo_full.sql
-- =============================================================================
-- WARNING: This script TRUNCATES all tables before inserting. All existing data
--          will be destroyed. Use only for demo environments.
-- =============================================================================

BEGIN;

-- =============================================================================
-- CLEAN SLATE — truncate all tables (order doesn't matter with CASCADE)
-- =============================================================================

TRUNCATE TABLE
    report_source_warnings,
    reports,
    signals,
    analysis_jobs,
    extracted_entities,
    vision_results,
    media_assets,
    near_duplicates,
    topic_content_items,
    content_items,
    narrative_clusters,
    credibility_audit_log,
    topic_sources,
    org_sources,
    sources,
    topics,
    users,
    organizations
CASCADE;

-- =============================================================================
-- 0. ORGANIZATION
-- =============================================================================

INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
VALUES (
    'org-anshul',
    'Anshul',
    'anshul',
    NOW(),
    NOW(),
    '{"classification": "OPEN", "domain": "platform"}'::jsonb
);

-- =============================================================================
-- 1. USERS
-- =============================================================================
-- Password: AnveshakDemo2024! (bcrypt hash, rounds=12)

INSERT INTO users (id, username, password_hash, role, org_id, created_at, updated_at, labels)
VALUES (
    'demo0001-0000-0000-0000-000000000001',
    'demo@anveshak.local',
    '$2b$12$exK0vBQZHOMCPjg37GTJZ.AtYqz1NI5SXwMLrWjnPvP2IqZMZKaei',
    'analyst',
    'org-anshul',
    NOW() - INTERVAL '30 days',
    NOW(),
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anshul"}'::jsonb
)
ON CONFLICT (username) DO NOTHING;

-- Admin user account
-- Password: AnveshakAdmin2024! (bcrypt hash, rounds=12)

INSERT INTO users (id, username, password_hash, role, org_id, created_at, updated_at, labels)
VALUES (
    'demo0001-0000-0000-0000-000000000002',
    'admin@anveshak.local',
    '$2b$12$S12K1p/iLSVP3VohoNnP1uxB493/aJIMt6lf/xmUWjJjvTJZHmSt.',
    'admin',
    'org-anshul',
    NOW() - INTERVAL '30 days',
    NOW(),
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anshul"}'::jsonb
)
ON CONFLICT (username) DO NOTHING;

-- =============================================================================
-- 2. TOPICS (6)
-- =============================================================================

INSERT INTO topics (id, name, keywords, languages, credibility_min, signal_threshold, status, scheduled_report_cron, scheduled_report_type, labels, created_at, updated_at)
VALUES
-- T1: Strait of Hormuz
(
    'topic001-0000-0000-0000-000000000001',
    'Strait of Hormuz — Maritime Threat Monitoring',
    ARRAY['Hormuz', 'IRGC', 'tanker', 'oil', 'blockade', 'Persian Gulf', 'naval', 'IRGCN', 'strait'],
    ARRAY['en', 'ar'],
    30.0, 3, 'active',
    '0 6 * * 1', 'weekly_digest',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '21 days', NOW()
),
-- T2: Bangladesh Border
(
    'topic001-0000-0000-0000-000000000002',
    'Bangladesh Border Security & Instability',
    ARRAY['Bangladesh', 'Rohingya', 'BSF', 'border', 'smuggling', 'BGB', 'Tripura', 'Dhaka', 'infiltration'],
    ARRAY['en', 'bn', 'hi'],
    30.0, 3, 'active',
    NULL, NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '18 days', NOW()
),
-- T3: China LAC
(
    'topic001-0000-0000-0000-000000000003',
    'China LAC Military Build-up',
    ARRAY['LAC', 'PLA', 'Aksai Chin', 'Ladakh', 'Galwan', 'Depsang', 'infrastructure', 'PLAAF', 'Hotan'],
    ARRAY['en'],
    30.0, 2, 'active',
    '0 6 * * 1', 'intelligence_brief',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '25 days', NOW()
),
-- T4: Pakistan Proxy Networks
(
    'topic001-0000-0000-0000-000000000004',
    'Pakistan Proxy Networks — Terror Financing',
    ARRAY['ISI', 'LeT', 'JeM', 'hawala', 'terror finance', 'FATF', 'grey list', 'Lashkar', 'Jaish'],
    ARRAY['en', 'hi'],
    30.0, 3, 'active',
    NULL, NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '20 days', NOW()
),
-- T5: Indian Ocean Region
(
    'topic001-0000-0000-0000-000000000005',
    'Indian Ocean Region — PLAN Naval Expansion',
    ARRAY['IOR', 'PLAN', 'Djibouti', 'Hambantota', 'naval base', 'string of pearls', 'PLA Navy', 'Indian Ocean'],
    ARRAY['en'],
    30.0, 2, 'active',
    '0 6 * * 1', 'weekly_digest',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '22 days', NOW()
),
-- T6: Internal Security LWE
(
    'topic001-0000-0000-0000-000000000006',
    'Internal Security — Left Wing Extremism',
    ARRAY['LWE', 'Naxal', 'Maoist', 'CRPF', 'Chhattisgarh', 'Bastar', 'Gadchiroli', 'CPI(Maoist)'],
    ARRAY['en', 'hi'],
    30.0, 2, 'active',
    NULL, NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '15 days', NOW()
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 3. SOURCES (15)
-- =============================================================================

INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, auto_score_enabled, is_active, health_status, consecutive_failures, last_checked_at, labels, created_at, updated_at)
VALUES
-- S1: Jane's Defence Weekly
(
    'source01-0000-0000-0000-000000000001',
    'Jane''s Defence Weekly',
    'https://www.janes.com',
    'web', 91.0, true, true, 'healthy', 0, NOW() - INTERVAL '2 hours',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "janes"}'::jsonb,
    NOW() - INTERVAL '25 days', NOW()
),
-- S2: Reuters World News
(
    'source01-0000-0000-0000-000000000002',
    'Reuters World News',
    'https://feeds.reuters.com/reuters/worldNews',
    'rss', 88.0, true, true, 'healthy', 0, NOW() - INTERVAL '1 hour',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "reuters"}'::jsonb,
    NOW() - INTERVAL '25 days', NOW()
),
-- S3: South China Morning Post
(
    'source01-0000-0000-0000-000000000003',
    'South China Morning Post',
    'https://www.scmp.com',
    'web', 74.0, true, true, 'healthy', 0, NOW() - INTERVAL '3 hours',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "scmp"}'::jsonb,
    NOW() - INTERVAL '25 days', NOW()
),
-- S4: Al Jazeera English
(
    'source01-0000-0000-0000-000000000004',
    'Al Jazeera English',
    'https://www.aljazeera.com/xml/rss/all.xml',
    'rss', 70.0, true, true, 'healthy', 0, NOW() - INTERVAL '2 hours',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "aljazeera"}'::jsonb,
    NOW() - INTERVAL '20 days', NOW()
),
-- S5: Times of India Defence
(
    'source01-0000-0000-0000-000000000005',
    'Times of India — Defence',
    'https://timesofindia.indiatimes.com/topic/defence',
    'web', 65.0, true, true, 'healthy', 0, NOW() - INTERVAL '4 hours',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "toi-defence"}'::jsonb,
    NOW() - INTERVAL '20 days', NOW()
),
-- S6: Pakistani Defence Forum
(
    'source01-0000-0000-0000-000000000006',
    'Pakistani Defence Forum',
    'https://www.defence.pk',
    'web', 42.0, true, true, 'degraded', 2, NOW() - INTERVAL '6 hours',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "defence-pk"}'::jsonb,
    NOW() - INTERVAL '20 days', NOW()
),
-- S7: Telegram OSINT Aggregator
(
    'source01-0000-0000-0000-000000000007',
    'Telegram: OSINT Aggregator',
    '@osint_aggregator',
    'telegram', 55.0, true, true, 'healthy', 0, NOW() - INTERVAL '1 hour',
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "source_id": "tg-osint"}'::jsonb,
    NOW() - INTERVAL '18 days', NOW()
),
-- S8: Telegram Gulf Watch
(
    'source01-0000-0000-0000-000000000008',
    'Telegram: Gulf Maritime Watch',
    '@gulf_watch_maritime',
    'telegram', 48.0, true, true, 'healthy', 0, NOW() - INTERVAL '3 hours',
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "source_id": "tg-gulfwatch"}'::jsonb,
    NOW() - INTERVAL '15 days', NOW()
),
-- S9: Reddit r/IndianDefence
(
    'source01-0000-0000-0000-000000000009',
    'Reddit: r/IndianDefence',
    'r/IndianDefence',
    'reddit', 52.0, true, true, 'healthy', 0, NOW() - INTERVAL '2 hours',
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "source_id": "reddit-indiandefence"}'::jsonb,
    NOW() - INTERVAL '18 days', NOW()
),
-- S10: Bellingcat
(
    'source01-0000-0000-0000-000000000010',
    'Bellingcat',
    'https://www.bellingcat.com',
    'web', 89.0, true, true, 'healthy', 0, NOW() - INTERVAL '5 hours',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "bellingcat"}'::jsonb,
    NOW() - INTERVAL '22 days', NOW()
),
-- S11: NDTV India
(
    'source01-0000-0000-0000-000000000011',
    'NDTV India',
    'https://www.ndtv.com',
    'web', 68.0, true, true, 'healthy', 0, NOW() - INTERVAL '2 hours',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "ndtv"}'::jsonb,
    NOW() - INTERVAL '18 days', NOW()
),
-- S12: The Hindu
(
    'source01-0000-0000-0000-000000000012',
    'The Hindu',
    'https://www.thehindu.com/news/national/feeder/default.rss',
    'rss', 72.0, true, true, 'healthy', 0, NOW() - INTERVAL '1 hour',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "thehindu"}'::jsonb,
    NOW() - INTERVAL '20 days', NOW()
),
-- S13: Telegram Dhaka Leaks
(
    'source01-0000-0000-0000-000000000013',
    'Telegram: Dhaka Leaks',
    '@dhaka_leaks_bd',
    'telegram', 35.0, true, true, 'degraded', 1, NOW() - INTERVAL '12 hours',
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "source_id": "tg-dhakaleaks"}'::jsonb,
    NOW() - INTERVAL '14 days', NOW()
),
-- S14: Global Security
(
    'source01-0000-0000-0000-000000000014',
    'Global Security',
    'https://www.globalsecurity.org',
    'web', 82.0, true, true, 'healthy', 0, NOW() - INTERVAL '4 hours',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "globalsecurity"}'::jsonb,
    NOW() - INTERVAL '25 days', NOW()
),
-- S15: Suspicious Propaganda Blog
(
    'source01-0000-0000-0000-000000000015',
    'Kashmir Truth Blog (Suspicious)',
    'https://kashmirtruthblog.example.com',
    'web', 22.0, false, true, 'down', 5, NOW() - INTERVAL '48 hours',
    '{"classification": "OPEN", "domain": "web", "owner_org": "anveshak", "source_id": "kashmir-prop"}'::jsonb,
    NOW() - INTERVAL '10 days', NOW()
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 4. TOPIC_SOURCES (join table)
-- =============================================================================

INSERT INTO topic_sources (topic_id, source_id) VALUES
-- T1 Hormuz: Reuters, Al Jazeera, Telegram Gulf Watch, Bellingcat, OSINT Aggregator
('topic001-0000-0000-0000-000000000001', 'source01-0000-0000-0000-000000000002'),
('topic001-0000-0000-0000-000000000001', 'source01-0000-0000-0000-000000000004'),
('topic001-0000-0000-0000-000000000001', 'source01-0000-0000-0000-000000000008'),
('topic001-0000-0000-0000-000000000001', 'source01-0000-0000-0000-000000000010'),
('topic001-0000-0000-0000-000000000001', 'source01-0000-0000-0000-000000000007'),
-- T2 Bangladesh: TOI, NDTV, The Hindu, Telegram Dhaka Leaks, Reddit
('topic001-0000-0000-0000-000000000002', 'source01-0000-0000-0000-000000000005'),
('topic001-0000-0000-0000-000000000002', 'source01-0000-0000-0000-000000000011'),
('topic001-0000-0000-0000-000000000002', 'source01-0000-0000-0000-000000000012'),
('topic001-0000-0000-0000-000000000002', 'source01-0000-0000-0000-000000000013'),
('topic001-0000-0000-0000-000000000002', 'source01-0000-0000-0000-000000000009'),
-- T3 China LAC: Jane's, SCMP, Global Security, Bellingcat, OSINT Aggregator, Reddit
('topic001-0000-0000-0000-000000000003', 'source01-0000-0000-0000-000000000001'),
('topic001-0000-0000-0000-000000000003', 'source01-0000-0000-0000-000000000003'),
('topic001-0000-0000-0000-000000000003', 'source01-0000-0000-0000-000000000014'),
('topic001-0000-0000-0000-000000000003', 'source01-0000-0000-0000-000000000010'),
('topic001-0000-0000-0000-000000000003', 'source01-0000-0000-0000-000000000007'),
('topic001-0000-0000-0000-000000000003', 'source01-0000-0000-0000-000000000009'),
-- T4 Pakistan Proxy: Jane's, Reuters, TOI, Pak Defence Forum, OSINT Aggregator, Kashmir Blog
('topic001-0000-0000-0000-000000000004', 'source01-0000-0000-0000-000000000001'),
('topic001-0000-0000-0000-000000000004', 'source01-0000-0000-0000-000000000002'),
('topic001-0000-0000-0000-000000000004', 'source01-0000-0000-0000-000000000005'),
('topic001-0000-0000-0000-000000000004', 'source01-0000-0000-0000-000000000006'),
('topic001-0000-0000-0000-000000000004', 'source01-0000-0000-0000-000000000007'),
('topic001-0000-0000-0000-000000000004', 'source01-0000-0000-0000-000000000015'),
-- T5 IOR Naval: Jane's, Reuters, SCMP, Global Security, Bellingcat
('topic001-0000-0000-0000-000000000005', 'source01-0000-0000-0000-000000000001'),
('topic001-0000-0000-0000-000000000005', 'source01-0000-0000-0000-000000000002'),
('topic001-0000-0000-0000-000000000005', 'source01-0000-0000-0000-000000000003'),
('topic001-0000-0000-0000-000000000005', 'source01-0000-0000-0000-000000000014'),
('topic001-0000-0000-0000-000000000005', 'source01-0000-0000-0000-000000000010'),
-- T6 LWE: TOI, NDTV, The Hindu, Reddit, OSINT Aggregator
('topic001-0000-0000-0000-000000000006', 'source01-0000-0000-0000-000000000005'),
('topic001-0000-0000-0000-000000000006', 'source01-0000-0000-0000-000000000011'),
('topic001-0000-0000-0000-000000000006', 'source01-0000-0000-0000-000000000012'),
('topic001-0000-0000-0000-000000000006', 'source01-0000-0000-0000-000000000009'),
('topic001-0000-0000-0000-000000000006', 'source01-0000-0000-0000-000000000007')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 5. NARRATIVE CLUSTERS (10)
-- =============================================================================

INSERT INTO narrative_clusters (
    id, topic_id, label, item_count, independent_source_count,
    executive_summary, label_generated_at, embedding_centroid,
    labels, created_at, updated_at
) VALUES
-- NC1: Hormuz — IRGC fast-boat harassment
(
    'clust001-0000-0000-0000-000000000001',
    'topic001-0000-0000-0000-000000000001',
    'IRGC fast-boat harassment of commercial tankers in Strait of Hormuz',
    5, 4,
    'Multiple independent sources report a surge in IRGC Navy fast-boat intercepts of commercial oil tankers transiting the Strait of Hormuz since April 10. At least 3 incidents involved warning shots. Lloyd''s of London has raised war-risk premiums for the transit zone.',
    NOW() - INTERVAL '3 days', NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '8 days', NOW() - INTERVAL '2 days'
),
-- NC2: Hormuz — Iranian naval exercises
(
    'clust001-0000-0000-0000-000000000002',
    'topic001-0000-0000-0000-000000000001',
    'Iranian Navy "Great Prophet" exercise buildup near Hormuz chokepoint',
    3, 3,
    'Iran has announced a large-scale naval exercise dubbed "Great Prophet 19" in waters adjacent to the Strait of Hormuz. Satellite imagery shows staging of missile boats and coastal defence batteries at Bandar Abbas and Qeshm Island.',
    NOW() - INTERVAL '2 days', NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '5 days', NOW() - INTERVAL '1 day'
),
-- NC3: Bangladesh — Rohingya smuggling networks
(
    'clust001-0000-0000-0000-000000000003',
    'topic001-0000-0000-0000-000000000002',
    'Rohingya smuggling and infiltration networks via Tripura-Bangladesh border',
    4, 3,
    'BSF and BGB joint patrols have intercepted multiple groups attempting illegal crossings near Agartala sector. Intelligence suggests organised smuggling rings are exploiting the monsoon-weakened fence sections. Arms and counterfeit currency also seized.',
    NOW() - INTERVAL '4 days', NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '10 days', NOW() - INTERVAL '3 days'
),
-- NC4: Bangladesh — Political instability Dhaka
(
    'clust001-0000-0000-0000-000000000004',
    'topic001-0000-0000-0000-000000000002',
    'Political unrest in Dhaka with anti-India sentiment amplification',
    3, 3,
    'Coordinated social media campaigns amplifying anti-India rhetoric traced to Dhaka-based accounts. Telegram channels sharing fabricated border incident videos. Sentiment analysis shows 340% spike in anti-India posts over 72 hours.',
    NOW() - INTERVAL '2 days', NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '6 days', NOW() - INTERVAL '1 day'
),
-- NC5: China LAC — Aksai Chin road construction
(
    'clust001-0000-0000-0000-000000000005',
    'topic001-0000-0000-0000-000000000003',
    'PLA road and helipad construction in Aksai Chin near Depsang Plains',
    5, 4,
    'Commercial satellite imagery confirms active road construction by PLA engineering units in the Aksai Chin region, extending toward Depsang Plains. New helipads identified at two locations within 30km of the LAC. Construction pace suggests completion by late Q2 2026.',
    NOW() - INTERVAL '5 days', NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '12 days', NOW() - INTERVAL '3 days'
),
-- NC6: China LAC — PLAAF Hotan activity
(
    'clust001-0000-0000-0000-000000000006',
    'topic001-0000-0000-0000-000000000003',
    'Increased PLAAF fighter and UAV sorties from Hotan and Kashgar airbases',
    4, 3,
    'ADS-B and satellite monitoring indicates a 200% increase in military flight activity from Hotan and Kashgar airbases over the past 14 days. J-16 and Wing Loong II UAV platforms identified. Pattern suggests integrated air-defence exercise or operational readiness drill.',
    NOW() - INTERVAL '3 days', NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '9 days', NOW() - INTERVAL '2 days'
),
-- NC7: Pakistan — Hawala terror finance network
(
    'clust001-0000-0000-0000-000000000007',
    'topic001-0000-0000-0000-000000000004',
    'Hawala networks funding LeT operatives via Dubai-Karachi corridor',
    4, 3,
    'FATF monitoring and open-source financial intelligence reveal continued hawala transfers from Dubai to Karachi-based LeT front organisations. Estimated $2.3M transferred in Q1 2026 via at least 4 identified hawala operators. Pakistan remains on FATF grey list.',
    NOW() - INTERVAL '4 days', NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000004"}'::jsonb,
    NOW() - INTERVAL '11 days', NOW() - INTERVAL '2 days'
),
-- NC8: IOR — Hambantota expansion
(
    'clust001-0000-0000-0000-000000000008',
    'topic001-0000-0000-0000-000000000005',
    'PLA Navy dual-use expansion at Hambantota Port, Sri Lanka',
    4, 3,
    'Satellite imagery and shipping data confirm expansion of pier facilities at Hambantota Port beyond commercial requirements. PLAN survey vessel Hai Yang 26 observed conducting hydrographic survey in adjacent waters. Sri Lankan government denies military use clause in 99-year lease.',
    NOW() - INTERVAL '3 days', NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000005"}'::jsonb,
    NOW() - INTERVAL '10 days', NOW() - INTERVAL '2 days'
),
-- NC9: IOR — Djibouti base upgrade
(
    'clust001-0000-0000-0000-000000000009',
    'topic001-0000-0000-0000-000000000005',
    'PLAN Djibouti Support Base — pier extension for carrier-class vessels',
    3, 2,
    'Construction activity at China''s Djibouti Support Base suggests pier extension capable of accommodating Type 075 LHD or larger vessels. Activity corroborated by two independent satellite providers. If completed, this would be the first overseas PLAN facility with large-vessel berthing capability.',
    NOW() - INTERVAL '2 days', NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000005"}'::jsonb,
    NOW() - INTERVAL '7 days', NOW() - INTERVAL '1 day'
),
-- NC10: LWE — Bastar IED corridor
(
    'clust001-0000-0000-0000-000000000010',
    'topic001-0000-0000-0000-000000000006',
    'CPI(Maoist) IED campaign targeting CRPF convoys in Bastar corridor',
    4, 3,
    'Four IED incidents targeting CRPF road-opening parties in Sukma-Bijapur corridor over 10 days. Explosive signatures suggest common fabrication source. Maoist leaflets recovered at two sites warn of escalation ahead of panchayat elections.',
    NOW() - INTERVAL '3 days', NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000006"}'::jsonb,
    NOW() - INTERVAL '8 days', NOW() - INTERVAL '2 days'
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 6. CONTENT ITEMS (30)
-- =============================================================================

-- --- T1: Strait of Hormuz (5 items) ---

INSERT INTO content_items (
    id, topic_id, source_id, narrative_cluster_id, url,
    title, raw_text, clean_text, content_hash,
    language, captured_at, credibility_score_at_capture,
    labels, created_at, updated_at
) VALUES
-- CI-01: Reuters on IRGC fast-boats
(
    'citem001-0000-0000-0000-000000000001',
    'topic001-0000-0000-0000-000000000001',
    'source01-0000-0000-0000-000000000002',
    'clust001-0000-0000-0000-000000000001',
    'https://www.reuters.com/world/middle-east/irgc-fast-boats-hormuz-2026-04',
    'IRGC fast-boats intercept two oil tankers near Strait of Hormuz',
    'DUBAI (Reuters) — Iran''s Revolutionary Guard Corps Navy intercepted two commercial oil tankers near the Strait of Hormuz on Tuesday, firing warning shots across the bow of a Marshall Islands-flagged vessel. The IRGC said the vessels entered Iranian territorial waters without authorisation.',
    'Iran''s Revolutionary Guard Corps Navy intercepted two commercial oil tankers near the Strait of Hormuz on Tuesday, firing warning shots across the bow of a Marshall Islands-flagged vessel. The IRGC said the vessels entered Iranian territorial waters without authorisation.',
    'aa00000000000000000000000000000000000000000000000000000000000001',
    'en',
    NOW() - INTERVAL '7 days',
    88.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '7 days', NOW() - INTERVAL '7 days'
),
-- CI-02: Al Jazeera on Hormuz shipping risks
(
    'citem001-0000-0000-0000-000000000002',
    'topic001-0000-0000-0000-000000000001',
    'source01-0000-0000-0000-000000000004',
    'clust001-0000-0000-0000-000000000001',
    'https://www.aljazeera.com/news/2026/4/hormuz-shipping-insurance',
    'Lloyd''s raises war-risk premiums for Hormuz transit after IRGC incidents',
    'Lloyd''s of London has increased war-risk insurance premiums for vessels transiting the Strait of Hormuz by 150% following three separate IRGC interception incidents in April. Shipping industry analysts warn of potential rerouting via the Cape of Good Hope.',
    'Lloyd''s of London has increased war-risk insurance premiums for vessels transiting the Strait of Hormuz by 150% following three separate IRGC interception incidents in April. Shipping industry analysts warn of potential rerouting via the Cape of Good Hope.',
    'aa00000000000000000000000000000000000000000000000000000000000002',
    'en',
    NOW() - INTERVAL '6 days',
    70.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '6 days', NOW() - INTERVAL '6 days'
),
-- CI-03: Telegram Gulf Watch — Arabic content with translation
(
    'citem001-0000-0000-0000-000000000003',
    'topic001-0000-0000-0000-000000000001',
    'source01-0000-0000-0000-000000000008',
    'clust001-0000-0000-0000-000000000001',
    NULL,
    NULL,
    'تقارير عن تحركات عسكرية إيرانية غير عادية بالقرب من مضيق هرمز. شهود عيان يؤكدون وجود زوارق هجومية سريعة تابعة للحرس الثوري في المنطقة.',
    'تقارير عن تحركات عسكرية إيرانية غير عادية بالقرب من مضيق هرمز. شهود عيان يؤكدون وجود زوارق هجومية سريعة تابعة للحرس الثوري في المنطقة.',
    'aa00000000000000000000000000000000000000000000000000000000000003',
    'ar',
    NOW() - INTERVAL '5 days',
    48.0,
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days'
),
-- CI-04: Bellingcat on Great Prophet exercise
(
    'citem001-0000-0000-0000-000000000004',
    'topic001-0000-0000-0000-000000000001',
    'source01-0000-0000-0000-000000000010',
    'clust001-0000-0000-0000-000000000002',
    'https://www.bellingcat.com/news/mena/2026/04/iran-great-prophet-exercise',
    'Satellite imagery reveals Iranian naval exercise staging near Bandar Abbas',
    'Bellingcat analysis of Planet Labs imagery dated April 14 reveals staging of at least 12 missile-armed fast attack craft and 3 Ghadir-class midget submarines at Bandar Abbas naval base. Coastal defence TEL vehicles identified at Qeshm Island. Assessment: preparation for Great Prophet 19 exercise.',
    'Bellingcat analysis of Planet Labs imagery dated April 14 reveals staging of at least 12 missile-armed fast attack craft and 3 Ghadir-class midget submarines at Bandar Abbas naval base. Coastal defence TEL vehicles identified at Qeshm Island. Assessment: preparation for Great Prophet 19 exercise.',
    'aa00000000000000000000000000000000000000000000000000000000000004',
    'en',
    NOW() - INTERVAL '4 days',
    89.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days'
),
-- CI-05: OSINT Aggregator on tanker diversion
(
    'citem001-0000-0000-0000-000000000005',
    'topic001-0000-0000-0000-000000000001',
    'source01-0000-0000-0000-000000000007',
    'clust001-0000-0000-0000-000000000001',
    NULL,
    'AIS data shows tankers diverting from Hormuz chokepoint',
    'AIS tracking data for past 72 hours shows at least 8 VLCC tankers altering course to avoid the narrowest section of the Strait of Hormuz. Two vessels have turned back toward Fujairah anchorage. This is the highest rate of Hormuz avoidance since January 2024.',
    'AIS tracking data for past 72 hours shows at least 8 VLCC tankers altering course to avoid the narrowest section of the Strait of Hormuz. Two vessels have turned back toward Fujairah anchorage. This is the highest rate of Hormuz avoidance since January 2024.',
    'aa00000000000000000000000000000000000000000000000000000000000005',
    'en',
    NOW() - INTERVAL '3 days',
    55.0,
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days'
),

-- --- T2: Bangladesh Border (5 items) ---

-- CI-06: TOI on BSF seizures
(
    'citem001-0000-0000-0000-000000000006',
    'topic001-0000-0000-0000-000000000002',
    'source01-0000-0000-0000-000000000005',
    'clust001-0000-0000-0000-000000000003',
    'https://timesofindia.indiatimes.com/india/bsf-seizes-arms-tripura-border/articleshow/12345',
    'BSF seizes arms cache near Tripura-Bangladesh border, 4 arrested',
    'Agartala: BSF personnel on patrol near the Akhaura sector of the Tripura-Bangladesh border seized a cache of arms including 3 AK-47 rifles and 200 rounds of ammunition. Four Bangladeshi nationals were arrested while attempting to cross into India. Officials suspect links to Rohingya smuggling networks operating in the region.',
    'BSF personnel on patrol near the Akhaura sector of the Tripura-Bangladesh border seized a cache of arms including 3 AK-47 rifles and 200 rounds of ammunition. Four Bangladeshi nationals were arrested while attempting to cross into India. Officials suspect links to Rohingya smuggling networks operating in the region.',
    'aa00000000000000000000000000000000000000000000000000000000000006',
    'en',
    NOW() - INTERVAL '9 days',
    65.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '9 days', NOW() - INTERVAL '9 days'
),
-- CI-07: NDTV on border fencing gaps
(
    'citem001-0000-0000-0000-000000000007',
    'topic001-0000-0000-0000-000000000002',
    'source01-0000-0000-0000-000000000011',
    'clust001-0000-0000-0000-000000000003',
    'https://www.ndtv.com/india-news/bangladesh-border-fencing-gaps-monsoon',
    'Monsoon damage creates 47 gaps in India-Bangladesh border fencing',
    'New Delhi: The Ministry of Home Affairs has confirmed that monsoon flooding has damaged border fencing at 47 locations along the India-Bangladesh border in West Bengal and Tripura sectors. BSF has deployed additional patrols but officials acknowledge the gaps are being exploited by smuggling networks.',
    'The Ministry of Home Affairs has confirmed that monsoon flooding has damaged border fencing at 47 locations along the India-Bangladesh border in West Bengal and Tripura sectors. BSF has deployed additional patrols but officials acknowledge the gaps are being exploited by smuggling networks.',
    'aa00000000000000000000000000000000000000000000000000000000000007',
    'en',
    NOW() - INTERVAL '8 days',
    68.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days'
),
-- CI-08: Telegram Dhaka Leaks — Bengali with translation
(
    'citem001-0000-0000-0000-000000000008',
    'topic001-0000-0000-0000-000000000002',
    'source01-0000-0000-0000-000000000013',
    'clust001-0000-0000-0000-000000000004',
    NULL,
    NULL,
    'ভারত সীমান্তে বিএসএফ বাংলাদেশী নাগরিকদের গুলি করেছে বলে অভিযোগ। ঢাকায় ভারত বিরোধী বিক্ষোভ চলছে। সোশ্যাল মিডিয়ায় ভিডিও ভাইরাল হচ্ছে।',
    'ভারত সীমান্তে বিএসএফ বাংলাদেশী নাগরিকদের গুলি করেছে বলে অভিযোগ। ঢাকায় ভারত বিরোধী বিক্ষোভ চলছে। সোশ্যাল মিডিয়ায় ভিডিও ভাইরাল হচ্ছে।',
    'aa00000000000000000000000000000000000000000000000000000000000008',
    'bn',
    NOW() - INTERVAL '5 days',
    35.0,
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days'
),
-- CI-09: The Hindu on Rohingya repatriation
(
    'citem001-0000-0000-0000-000000000009',
    'topic001-0000-0000-0000-000000000002',
    'source01-0000-0000-0000-000000000012',
    'clust001-0000-0000-0000-000000000003',
    'https://www.thehindu.com/news/national/rohingya-repatriation-stalled',
    'Rohingya repatriation to Myanmar stalls as border crossings surge',
    'The UNHCR-brokered Rohingya repatriation process has stalled due to continued instability in Myanmar''s Rakhine state. Meanwhile, Indian intelligence agencies report a 60% increase in Rohingya crossings via Bangladesh into India''s northeast, primarily through Mizoram and Tripura.',
    'The UNHCR-brokered Rohingya repatriation process has stalled due to continued instability in Myanmar''s Rakhine state. Meanwhile, Indian intelligence agencies report a 60% increase in Rohingya crossings via Bangladesh into India''s northeast, primarily through Mizoram and Tripura.',
    'aa00000000000000000000000000000000000000000000000000000000000009',
    'en',
    NOW() - INTERVAL '6 days',
    72.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '6 days', NOW() - INTERVAL '6 days'
),
-- CI-10: Reddit on anti-India social media campaign
(
    'citem001-0000-0000-0000-000000000010',
    'topic001-0000-0000-0000-000000000002',
    'source01-0000-0000-0000-000000000009',
    'clust001-0000-0000-0000-000000000004',
    'https://www.reddit.com/r/IndianDefence/comments/abc123',
    'Analysis: Coordinated anti-India social media campaign originating from Dhaka',
    'A coordinated information campaign targeting India has been detected across Telegram, Facebook, and X. At least 47 accounts created within a 48-hour window are sharing identical fabricated videos of alleged BSF atrocities. Digital forensics indicates the videos are edited clips from unrelated incidents in Myanmar.',
    'A coordinated information campaign targeting India has been detected across Telegram, Facebook, and X. At least 47 accounts created within a 48-hour window are sharing identical fabricated videos of alleged BSF atrocities. Digital forensics indicates the videos are edited clips from unrelated incidents in Myanmar.',
    'aa00000000000000000000000000000000000000000000000000000000000010',
    'en',
    NOW() - INTERVAL '4 days',
    52.0,
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days'
),

-- --- T3: China LAC (5 items) ---

-- CI-11: Jane's on Aksai Chin road construction
(
    'citem001-0000-0000-0000-000000000011',
    'topic001-0000-0000-0000-000000000003',
    'source01-0000-0000-0000-000000000001',
    'clust001-0000-0000-0000-000000000005',
    'https://www.janes.com/defence-news/pla-aksai-chin-road-2026',
    'PLA engineering units accelerate road construction toward Depsang Plains',
    'Jane''s Intelligence Review has confirmed through commercial satellite imagery that PLA engineering units have accelerated road construction in the Aksai Chin region. The new 45km road segment extends from the existing G219 highway toward the Depsang Plains, bringing vehicular access within 25km of Indian positions. Two helicopter landing pads have been constructed at intermediate waypoints.',
    'Jane''s Intelligence Review has confirmed through commercial satellite imagery that PLA engineering units have accelerated road construction in the Aksai Chin region. The new 45km road segment extends from the existing G219 highway toward the Depsang Plains, bringing vehicular access within 25km of Indian positions. Two helicopter landing pads have been constructed at intermediate waypoints.',
    'aa00000000000000000000000000000000000000000000000000000000000011',
    'en',
    NOW() - INTERVAL '10 days',
    91.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '10 days', NOW() - INTERVAL '10 days'
),
-- CI-12: SCMP on PLA Western Theatre readiness
(
    'citem001-0000-0000-0000-000000000012',
    'topic001-0000-0000-0000-000000000003',
    'source01-0000-0000-0000-000000000003',
    'clust001-0000-0000-0000-000000000005',
    'https://www.scmp.com/news/china/military/article/pla-western-theatre',
    'PLA Western Theatre Command conducts high-altitude logistics drill',
    'The PLA''s Western Theatre Command has completed a large-scale logistics exercise simulating rapid deployment of a combined-arms brigade to altitudes above 4,500 metres. The exercise involved 2,000 personnel and tested cold-weather equipment supply chains. Military commentators note the exercise area corresponds to the Aksai Chin-Ladakh frontier.',
    'The PLA''s Western Theatre Command has completed a large-scale logistics exercise simulating rapid deployment of a combined-arms brigade to altitudes above 4,500 metres. The exercise involved 2,000 personnel and tested cold-weather equipment supply chains. Military commentators note the exercise area corresponds to the Aksai Chin-Ladakh frontier.',
    'aa00000000000000000000000000000000000000000000000000000000000012',
    'en',
    NOW() - INTERVAL '8 days',
    74.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days'
),
-- CI-13: Global Security on Hotan PLAAF activity
(
    'citem001-0000-0000-0000-000000000013',
    'topic001-0000-0000-0000-000000000003',
    'source01-0000-0000-0000-000000000014',
    'clust001-0000-0000-0000-000000000006',
    'https://www.globalsecurity.org/military/world/china/hotan-airbase-update',
    'Wing Loong II UAV sorties from Hotan Airbase double in April',
    'Analysis of ADS-B data and satellite imagery indicates Wing Loong II unmanned aerial vehicle sorties from Hotan Airbase have doubled compared to March 2026. Flight tracks suggest surveillance patterns over the Aksai Chin plateau. J-16 multirole fighters have also been observed in increased numbers at the facility.',
    'Analysis of ADS-B data and satellite imagery indicates Wing Loong II unmanned aerial vehicle sorties from Hotan Airbase have doubled compared to March 2026. Flight tracks suggest surveillance patterns over the Aksai Chin plateau. J-16 multirole fighters have also been observed in increased numbers at the facility.',
    'aa00000000000000000000000000000000000000000000000000000000000013',
    'en',
    NOW() - INTERVAL '6 days',
    82.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '6 days', NOW() - INTERVAL '6 days'
),
-- CI-14: Bellingcat on new PLA positions
(
    'citem001-0000-0000-0000-000000000014',
    'topic001-0000-0000-0000-000000000003',
    'source01-0000-0000-0000-000000000010',
    'clust001-0000-0000-0000-000000000005',
    'https://www.bellingcat.com/news/asia/2026/04/pla-lac-positions',
    'New PLA defensive positions identified 8km from LAC near Galwan',
    'Bellingcat geolocation analysis of Maxar imagery from April 12 confirms construction of semi-permanent defensive positions approximately 8km from the LAC in the Galwan Valley sector. Structures include reinforced bunkers, vehicle revetments, and what appear to be pre-positioned supply caches. This represents a forward movement compared to the post-2020 buffer zone arrangements.',
    'Bellingcat geolocation analysis of Maxar imagery from April 12 confirms construction of semi-permanent defensive positions approximately 8km from the LAC in the Galwan Valley sector. Structures include reinforced bunkers, vehicle revetments, and what appear to be pre-positioned supply caches. This represents a forward movement compared to the post-2020 buffer zone arrangements.',
    'aa00000000000000000000000000000000000000000000000000000000000014',
    'en',
    NOW() - INTERVAL '5 days',
    89.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days'
),
-- CI-15: Reddit — OSINT community discussion
(
    'citem001-0000-0000-0000-000000000015',
    'topic001-0000-0000-0000-000000000003',
    'source01-0000-0000-0000-000000000009',
    'clust001-0000-0000-0000-000000000006',
    'https://www.reddit.com/r/IndianDefence/comments/def456',
    'OSINT thread: Tracking PLA infrastructure build-up along LAC',
    'Compilation thread tracking PLA construction activity along the LAC. Users have geolocated 3 new helipads near Depsang, a road extension toward Gogra-Hot Springs, and new antenna arrays consistent with electronic warfare equipment. Multiple contributors corroborate using Google Earth historical imagery comparison.',
    'Compilation thread tracking PLA construction activity along the LAC. Users have geolocated 3 new helipads near Depsang, a road extension toward Gogra-Hot Springs, and new antenna arrays consistent with electronic warfare equipment. Multiple contributors corroborate using Google Earth historical imagery comparison.',
    'aa00000000000000000000000000000000000000000000000000000000000015',
    'en',
    NOW() - INTERVAL '4 days',
    52.0,
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days'
),

-- --- T4: Pakistan Proxy Networks (5 items) ---

-- CI-16: Jane's on FATF grey list
(
    'citem001-0000-0000-0000-000000000016',
    'topic001-0000-0000-0000-000000000004',
    'source01-0000-0000-0000-000000000001',
    'clust001-0000-0000-0000-000000000007',
    'https://www.janes.com/defence-news/pakistan-fatf-grey-list-2026',
    'Pakistan remains on FATF grey list; terror financing gaps persist',
    'Pakistan has failed to exit the Financial Action Task Force (FATF) grey list at the April 2026 plenary session. The FATF cited continued deficiencies in prosecuting terror financing cases linked to UN-designated entities including Lashkar-e-Taiba and Jaish-e-Mohammed. Assessors noted that despite structural reforms, operational enforcement remains weak.',
    'Pakistan has failed to exit the Financial Action Task Force (FATF) grey list at the April 2026 plenary session. The FATF cited continued deficiencies in prosecuting terror financing cases linked to UN-designated entities including Lashkar-e-Taiba and Jaish-e-Mohammed. Assessors noted that despite structural reforms, operational enforcement remains weak.',
    'aa00000000000000000000000000000000000000000000000000000000000016',
    'en',
    NOW() - INTERVAL '9 days',
    91.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000004"}'::jsonb,
    NOW() - INTERVAL '9 days', NOW() - INTERVAL '9 days'
),
-- CI-17: Reuters on hawala crackdown
(
    'citem001-0000-0000-0000-000000000017',
    'topic001-0000-0000-0000-000000000004',
    'source01-0000-0000-0000-000000000002',
    'clust001-0000-0000-0000-000000000007',
    'https://www.reuters.com/world/asia/dubai-hawala-pakistan-terror-finance-2026',
    'Dubai authorities arrest hawala operator linked to LeT front organisations',
    'DUBAI (Reuters) — UAE authorities have arrested a Dubai-based hawala operator suspected of channelling funds to Lashkar-e-Taiba front organisations in Pakistan. The suspect allegedly transferred approximately $2.3 million over 18 months through a network of exchange houses. The arrest follows intelligence sharing between UAE and Indian agencies.',
    'UAE authorities have arrested a Dubai-based hawala operator suspected of channelling funds to Lashkar-e-Taiba front organisations in Pakistan. The suspect allegedly transferred approximately $2.3 million over 18 months through a network of exchange houses. The arrest follows intelligence sharing between UAE and Indian agencies.',
    'aa00000000000000000000000000000000000000000000000000000000000017',
    'en',
    NOW() - INTERVAL '7 days',
    88.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000004"}'::jsonb,
    NOW() - INTERVAL '7 days', NOW() - INTERVAL '7 days'
),
-- CI-18: TOI — Hindi content with translation
(
    'citem001-0000-0000-0000-000000000018',
    'topic001-0000-0000-0000-000000000004',
    'source01-0000-0000-0000-000000000005',
    'clust001-0000-0000-0000-000000000007',
    'https://timesofindia.indiatimes.com/india/nia-jem-module-kashmir',
    'NIA ने जम्मू में जैश-ए-मोहम्मद के स्लीपर सेल का भंडाफोड़ किया',
    'एनआईए ने जम्मू संभाग में जैश-ए-मोहम्मद से जुड़े एक स्लीपर सेल का भंडाफोड़ किया है। छापेमारी में हवाला के माध्यम से प्राप्त 15 लाख रुपये नकद, पाकिस्तानी सिम कार्ड और एन्क्रिप्टेड संचार उपकरण बरामद किए गए। गिरफ्तार किए गए तीन संदिग्धों को पाकिस्तान स्थित हैंडलरों से निर्देश मिल रहे थे।',
    'एनआईए ने जम्मू संभाग में जैश-ए-मोहम्मद से जुड़े एक स्लीपर सेल का भंडाफोड़ किया है। छापेमारी में हवाला के माध्यम से प्राप्त 15 लाख रुपये नकद, पाकिस्तानी सिम कार्ड और एन्क्रिप्टेड संचार उपकरण बरामद किए गए।',
    'aa00000000000000000000000000000000000000000000000000000000000018',
    'hi',
    NOW() - INTERVAL '6 days',
    65.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000004"}'::jsonb,
    NOW() - INTERVAL '6 days', NOW() - INTERVAL '6 days'
),
-- CI-19: Pak Defence Forum — low credibility
(
    'citem001-0000-0000-0000-000000000019',
    'topic001-0000-0000-0000-000000000004',
    'source01-0000-0000-0000-000000000006',
    NULL,
    'https://www.defence.pk/threads/india-false-flag-fatf.12345',
    'India using FATF as political weapon against Pakistan — analysis',
    'India is weaponising the FATF process to isolate Pakistan diplomatically. The so-called terror financing allegations are fabricated by RAW to keep Pakistan on the grey list. Pakistan''s military establishment has successfully dismantled all militant networks and the FATF should acknowledge this progress.',
    'India is weaponising the FATF process to isolate Pakistan diplomatically. The so-called terror financing allegations are fabricated by RAW to keep Pakistan on the grey list. Pakistan''s military establishment has successfully dismantled all militant networks and the FATF should acknowledge this progress.',
    'aa00000000000000000000000000000000000000000000000000000000000019',
    'en',
    NOW() - INTERVAL '5 days',
    42.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000004"}'::jsonb,
    NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days'
),
-- CI-20: OSINT Aggregator on JeM camps
(
    'citem001-0000-0000-0000-000000000020',
    'topic001-0000-0000-0000-000000000004',
    'source01-0000-0000-0000-000000000007',
    'clust001-0000-0000-0000-000000000007',
    NULL,
    'Satellite imagery suggests JeM training camp activity near Bahawalpur',
    'Open-source satellite imagery from April 8 shows renewed activity at a known Jaish-e-Mohammed training facility near Bahawalpur, Punjab, Pakistan. Vehicle movements, new temporary structures, and what appear to be obstacle courses are visible. The facility was previously identified by Indian intelligence as a JeM recruitment and training centre.',
    'Open-source satellite imagery from April 8 shows renewed activity at a known Jaish-e-Mohammed training facility near Bahawalpur, Punjab, Pakistan. Vehicle movements, new temporary structures, and what appear to be obstacle courses are visible. The facility was previously identified by Indian intelligence as a JeM recruitment and training centre.',
    'aa00000000000000000000000000000000000000000000000000000000000020',
    'en',
    NOW() - INTERVAL '4 days',
    55.0,
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000004"}'::jsonb,
    NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days'
),

-- --- T5: Indian Ocean Region (5 items) ---

-- CI-21: Jane's on Hambantota
(
    'citem001-0000-0000-0000-000000000021',
    'topic001-0000-0000-0000-000000000005',
    'source01-0000-0000-0000-000000000001',
    'clust001-0000-0000-0000-000000000008',
    'https://www.janes.com/defence-news/hambantota-port-expansion-2026',
    'Hambantota Port expansion exceeds commercial requirements — defence analysts',
    'Jane''s analysis of recent satellite imagery reveals significant expansion of pier infrastructure at Hambantota Port, Sri Lanka, beyond what commercial shipping volumes justify. The new deep-water berth could accommodate vessels up to 60,000 tonnes displacement — consistent with PLAN Type 075 amphibious assault ships. Chinese state-owned CMPORT holds a 99-year lease on the facility.',
    'Jane''s analysis of recent satellite imagery reveals significant expansion of pier infrastructure at Hambantota Port, Sri Lanka, beyond what commercial shipping volumes justify. The new deep-water berth could accommodate vessels up to 60,000 tonnes displacement — consistent with PLAN Type 075 amphibious assault ships. Chinese state-owned CMPORT holds a 99-year lease on the facility.',
    'aa00000000000000000000000000000000000000000000000000000000000021',
    'en',
    NOW() - INTERVAL '8 days',
    91.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000005"}'::jsonb,
    NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days'
),
-- CI-22: Reuters on Djibouti base
(
    'citem001-0000-0000-0000-000000000022',
    'topic001-0000-0000-0000-000000000005',
    'source01-0000-0000-0000-000000000002',
    'clust001-0000-0000-0000-000000000009',
    'https://www.reuters.com/world/africa/china-djibouti-base-expansion-2026',
    'China''s Djibouti base pier extension nears completion — satellite images',
    'NAIROBI (Reuters) — Satellite imagery reviewed by Reuters shows that construction of a major pier extension at China''s naval support base in Djibouti is approximately 80% complete. The 400-metre extension would enable berthing of China''s largest warships. Western defence officials say this confirms China''s intent to project sustained naval power in the Indian Ocean and Red Sea.',
    'Satellite imagery reviewed by Reuters shows that construction of a major pier extension at China''s naval support base in Djibouti is approximately 80% complete. The 400-metre extension would enable berthing of China''s largest warships. Western defence officials say this confirms China''s intent to project sustained naval power in the Indian Ocean and Red Sea.',
    'aa00000000000000000000000000000000000000000000000000000000000022',
    'en',
    NOW() - INTERVAL '6 days',
    88.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000005"}'::jsonb,
    NOW() - INTERVAL '6 days', NOW() - INTERVAL '6 days'
),
-- CI-23: SCMP on PLAN survey vessel
(
    'citem001-0000-0000-0000-000000000023',
    'topic001-0000-0000-0000-000000000005',
    'source01-0000-0000-0000-000000000003',
    'clust001-0000-0000-0000-000000000008',
    'https://www.scmp.com/news/china/diplomacy/article/plan-survey-vessel-sri-lanka',
    'PLAN survey vessel Hai Yang 26 conducts operations near Sri Lankan waters',
    'China''s research vessel Hai Yang 26 has been conducting hydrographic surveys in waters adjacent to Hambantota Port for 12 days. Sri Lanka granted a research permit despite Indian diplomatic protests. The vessel is equipped with multi-beam sonar and sub-bottom profiling systems used for submarine navigation chart preparation.',
    'China''s research vessel Hai Yang 26 has been conducting hydrographic surveys in waters adjacent to Hambantota Port for 12 days. Sri Lanka granted a research permit despite Indian diplomatic protests. The vessel is equipped with multi-beam sonar and sub-bottom profiling systems used for submarine navigation chart preparation.',
    'aa00000000000000000000000000000000000000000000000000000000000023',
    'en',
    NOW() - INTERVAL '5 days',
    74.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000005"}'::jsonb,
    NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days'
),
-- CI-24: Global Security on string of pearls
(
    'citem001-0000-0000-0000-000000000024',
    'topic001-0000-0000-0000-000000000005',
    'source01-0000-0000-0000-000000000014',
    'clust001-0000-0000-0000-000000000008',
    'https://www.globalsecurity.org/military/world/china/ior-facilities-2026',
    'Updated assessment: China''s Indian Ocean facility network — 2026 status',
    'An updated assessment of Chinese dual-use port facilities across the Indian Ocean identifies active military-capable infrastructure at Gwadar (Pakistan), Hambantota (Sri Lanka), Chittagong (Bangladesh), and Djibouti. Planned facilities at Marao (Maldives) and Beira (Mozambique) remain in negotiation. The network provides logistical depth for PLAN operations from the Persian Gulf to the Strait of Malacca.',
    'An updated assessment of Chinese dual-use port facilities across the Indian Ocean identifies active military-capable infrastructure at Gwadar (Pakistan), Hambantota (Sri Lanka), Chittagong (Bangladesh), and Djibouti. Planned facilities at Marao (Maldives) and Beira (Mozambique) remain in negotiation. The network provides logistical depth for PLAN operations from the Persian Gulf to the Strait of Malacca.',
    'aa00000000000000000000000000000000000000000000000000000000000024',
    'en',
    NOW() - INTERVAL '3 days',
    82.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000005"}'::jsonb,
    NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days'
),
-- CI-25: Bellingcat on PLAN deployments
(
    'citem001-0000-0000-0000-000000000025',
    'topic001-0000-0000-0000-000000000005',
    'source01-0000-0000-0000-000000000010',
    'clust001-0000-0000-0000-000000000009',
    'https://www.bellingcat.com/news/asia/2026/04/plan-indian-ocean-deployment',
    'PLAN Task Group 47 enters Indian Ocean via Malacca Strait',
    'AIS and satellite tracking confirm PLAN Task Group 47 — comprising Type 052D destroyer Hohhot, Type 054A frigate Yueyang, and Type 903A replenishment ship Dongpinghu — transited the Strait of Malacca on April 18 heading west. The task group is assessed to be heading for the Gulf of Aden anti-piracy patrol but may conduct port calls at Hambantota and Djibouti.',
    'AIS and satellite tracking confirm PLAN Task Group 47 — comprising Type 052D destroyer Hohhot, Type 054A frigate Yueyang, and Type 903A replenishment ship Dongpinghu — transited the Strait of Malacca on April 18 heading west. The task group is assessed to be heading for the Gulf of Aden anti-piracy patrol but may conduct port calls at Hambantota and Djibouti.',
    'aa00000000000000000000000000000000000000000000000000000000000025',
    'en',
    NOW() - INTERVAL '2 days',
    89.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000005"}'::jsonb,
    NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'
),

-- --- T6: Internal Security LWE (5 items) ---

-- CI-26: TOI on CRPF ambush
(
    'citem001-0000-0000-0000-000000000026',
    'topic001-0000-0000-0000-000000000006',
    'source01-0000-0000-0000-000000000005',
    'clust001-0000-0000-0000-000000000010',
    'https://timesofindia.indiatimes.com/india/crpf-ambush-sukma-ied',
    'CRPF convoy hit by IED in Sukma; 3 jawans injured',
    'Sukma: A CRPF road-opening party was targeted by an improvised explosive device (IED) in the Kistaram area of Sukma district, Chhattisgarh. Three jawans sustained injuries and have been evacuated. CPI(Maoist) is suspected. This is the fourth IED attack on security forces in the Sukma-Bijapur corridor in 10 days.',
    'A CRPF road-opening party was targeted by an improvised explosive device (IED) in the Kistaram area of Sukma district, Chhattisgarh. Three jawans sustained injuries and have been evacuated. CPI(Maoist) is suspected. This is the fourth IED attack on security forces in the Sukma-Bijapur corridor in 10 days.',
    'aa00000000000000000000000000000000000000000000000000000000000026',
    'en',
    NOW() - INTERVAL '7 days',
    65.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000006"}'::jsonb,
    NOW() - INTERVAL '7 days', NOW() - INTERVAL '7 days'
),
-- CI-27: NDTV on Maoist leaflet campaign
(
    'citem001-0000-0000-0000-000000000027',
    'topic001-0000-0000-0000-000000000006',
    'source01-0000-0000-0000-000000000011',
    'clust001-0000-0000-0000-000000000010',
    'https://www.ndtv.com/india-news/maoist-leaflet-bastar-panchayat-elections',
    'Maoist leaflets warn of election boycott and escalation in Bastar division',
    'CPI(Maoist) leaflets recovered from multiple villages in Bastar division call for a boycott of upcoming panchayat elections and warn of "intensified armed resistance" against security forces. Intelligence agencies assess this as preparation for a pre-election violence campaign to intimidate voters and candidates.',
    'CPI(Maoist) leaflets recovered from multiple villages in Bastar division call for a boycott of upcoming panchayat elections and warn of "intensified armed resistance" against security forces. Intelligence agencies assess this as preparation for a pre-election violence campaign to intimidate voters and candidates.',
    'aa00000000000000000000000000000000000000000000000000000000000027',
    'en',
    NOW() - INTERVAL '6 days',
    68.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000006"}'::jsonb,
    NOW() - INTERVAL '6 days', NOW() - INTERVAL '6 days'
),
-- CI-28: The Hindu — Hindi article on Gadchiroli ops
(
    'citem001-0000-0000-0000-000000000028',
    'topic001-0000-0000-0000-000000000006',
    'source01-0000-0000-0000-000000000012',
    'clust001-0000-0000-0000-000000000010',
    'https://www.thehindu.com/news/national/gadchiroli-anti-naxal-ops',
    'गडचिरोली में सी-60 कमांडो ने 4 नक्सलियों को किया ढेर',
    'महाराष्ट्र पुलिस की विशेष C-60 कमांडो यूनिट ने गडचिरोली जिले के एटापल्ली तालुका में मुठभेड़ के दौरान 4 CPI(Maoist) कैडर को मार गिराया। मारे गए नक्सलियों में एक दलम कमांडर शामिल है जिस पर 10 लाख का इनाम था। मौके से हथियार और विस्फोटक बरामद किए गए।',
    'महाराष्ट्र पुलिस की विशेष C-60 कमांडो यूनिट ने गडचिरोली जिले के एटापल्ली तालुका में मुठभेड़ के दौरान 4 CPI(Maoist) कैडर को मार गिराया। मारे गए नक्सलियों में एक दलम कमांडर शामिल है जिस पर 10 लाख का इनाम था।',
    'aa00000000000000000000000000000000000000000000000000000000000028',
    'hi',
    NOW() - INTERVAL '5 days',
    72.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000006"}'::jsonb,
    NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days'
),
-- CI-29: Reddit on Maoist supply routes
(
    'citem001-0000-0000-0000-000000000029',
    'topic001-0000-0000-0000-000000000006',
    'source01-0000-0000-0000-000000000009',
    'clust001-0000-0000-0000-000000000010',
    'https://www.reddit.com/r/IndianDefence/comments/ghi789',
    'Discussion: Are Maoist supply routes shifting to Gadchiroli-Bastar corridor?',
    'Analysis of recent encounter patterns suggests CPI(Maoist) is consolidating its supply routes through the Gadchiroli-Bastar-Sukma corridor. The shift from the traditional Abujhmad sanctuary may indicate pressure from ongoing operations but also suggests new logistics partnerships with local smuggling networks.',
    'Analysis of recent encounter patterns suggests CPI(Maoist) is consolidating its supply routes through the Gadchiroli-Bastar-Sukma corridor. The shift from the traditional Abujhmad sanctuary may indicate pressure from ongoing operations but also suggests new logistics partnerships with local smuggling networks.',
    'aa00000000000000000000000000000000000000000000000000000000000029',
    'en',
    NOW() - INTERVAL '3 days',
    52.0,
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000006"}'::jsonb,
    NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days'
),
-- CI-30: OSINT Aggregator on IED forensics
(
    'citem001-0000-0000-0000-000000000030',
    'topic001-0000-0000-0000-000000000006',
    'source01-0000-0000-0000-000000000007',
    'clust001-0000-0000-0000-000000000010',
    NULL,
    'IED forensics suggest common fabrication source across Sukma-Bijapur attacks',
    'Explosive forensics from the four recent IED attacks in Sukma-Bijapur corridor reveal common detonator signatures and explosive composition, suggesting a single fabrication workshop. CRPF bomb disposal units have identified the devices as pressure-plate activated with estimated 5-8kg main charge. The sophistication level indicates experienced bomb-makers.',
    'Explosive forensics from the four recent IED attacks in Sukma-Bijapur corridor reveal common detonator signatures and explosive composition, suggesting a single fabrication workshop. CRPF bomb disposal units have identified the devices as pressure-plate activated with estimated 5-8kg main charge. The sophistication level indicates experienced bomb-makers.',
    'aa00000000000000000000000000000000000000000000000000000000000030',
    'en',
    NOW() - INTERVAL '2 days',
    55.0,
    '{"classification": "OPEN", "domain": "social", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000006"}'::jsonb,
    NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'
)
ON CONFLICT (content_hash) DO NOTHING;

-- Update translated_text for non-English items
UPDATE content_items SET translated_text = 'Reports of unusual Iranian military movements near the Strait of Hormuz. Eyewitnesses confirm the presence of IRGC fast attack boats in the area.', translation_model = 'nllb-200-distilled-600M' WHERE id = 'citem001-0000-0000-0000-000000000003';
UPDATE content_items SET translated_text = 'Allegations that BSF shot Bangladeshi citizens at the Indian border. Anti-India protests underway in Dhaka. Videos going viral on social media.', translation_model = 'nllb-200-distilled-600M' WHERE id = 'citem001-0000-0000-0000-000000000008';
UPDATE content_items SET translated_text = 'NIA busts Jaish-e-Mohammed sleeper cell in Jammu division. Cash of Rs 15 lakh received via hawala, Pakistani SIM cards, and encrypted communication devices recovered in raids. Three arrested suspects were receiving instructions from Pakistan-based handlers.', translation_model = 'nllb-200-distilled-600M' WHERE id = 'citem001-0000-0000-0000-000000000018';
UPDATE content_items SET translated_text = 'Maharashtra Police C-60 commandos eliminated 4 CPI(Maoist) cadres in an encounter in Etapalli taluka of Gadchiroli district. Among those killed was a dalam commander who carried a Rs 10 lakh bounty. Arms and explosives recovered from the site.', translation_model = 'nllb-200-distilled-600M' WHERE id = 'citem001-0000-0000-0000-000000000028';

-- =============================================================================
-- 7. TOPIC_CONTENT_ITEMS (join table)
-- =============================================================================

INSERT INTO topic_content_items (topic_id, content_item_id, similarity_score) VALUES
-- T1 Hormuz
('topic001-0000-0000-0000-000000000001', 'citem001-0000-0000-0000-000000000001', 0.92),
('topic001-0000-0000-0000-000000000001', 'citem001-0000-0000-0000-000000000002', 0.88),
('topic001-0000-0000-0000-000000000001', 'citem001-0000-0000-0000-000000000003', 0.85),
('topic001-0000-0000-0000-000000000001', 'citem001-0000-0000-0000-000000000004', 0.90),
('topic001-0000-0000-0000-000000000001', 'citem001-0000-0000-0000-000000000005', 0.87),
-- T2 Bangladesh
('topic001-0000-0000-0000-000000000002', 'citem001-0000-0000-0000-000000000006', 0.91),
('topic001-0000-0000-0000-000000000002', 'citem001-0000-0000-0000-000000000007', 0.89),
('topic001-0000-0000-0000-000000000002', 'citem001-0000-0000-0000-000000000008', 0.82),
('topic001-0000-0000-0000-000000000002', 'citem001-0000-0000-0000-000000000009', 0.93),
('topic001-0000-0000-0000-000000000002', 'citem001-0000-0000-0000-000000000010', 0.86),
-- T3 China LAC
('topic001-0000-0000-0000-000000000003', 'citem001-0000-0000-0000-000000000011', 0.95),
('topic001-0000-0000-0000-000000000003', 'citem001-0000-0000-0000-000000000012', 0.91),
('topic001-0000-0000-0000-000000000003', 'citem001-0000-0000-0000-000000000013', 0.88),
('topic001-0000-0000-0000-000000000003', 'citem001-0000-0000-0000-000000000014', 0.93),
('topic001-0000-0000-0000-000000000003', 'citem001-0000-0000-0000-000000000015', 0.84),
-- T4 Pakistan
('topic001-0000-0000-0000-000000000004', 'citem001-0000-0000-0000-000000000016', 0.94),
('topic001-0000-0000-0000-000000000004', 'citem001-0000-0000-0000-000000000017', 0.92),
('topic001-0000-0000-0000-000000000004', 'citem001-0000-0000-0000-000000000018', 0.87),
('topic001-0000-0000-0000-000000000004', 'citem001-0000-0000-0000-000000000019', 0.78),
('topic001-0000-0000-0000-000000000004', 'citem001-0000-0000-0000-000000000020', 0.89),
-- T5 IOR
('topic001-0000-0000-0000-000000000005', 'citem001-0000-0000-0000-000000000021', 0.94),
('topic001-0000-0000-0000-000000000005', 'citem001-0000-0000-0000-000000000022', 0.91),
('topic001-0000-0000-0000-000000000005', 'citem001-0000-0000-0000-000000000023', 0.90),
('topic001-0000-0000-0000-000000000005', 'citem001-0000-0000-0000-000000000024', 0.88),
('topic001-0000-0000-0000-000000000005', 'citem001-0000-0000-0000-000000000025', 0.92),
-- T6 LWE
('topic001-0000-0000-0000-000000000006', 'citem001-0000-0000-0000-000000000026', 0.93),
('topic001-0000-0000-0000-000000000006', 'citem001-0000-0000-0000-000000000027', 0.90),
('topic001-0000-0000-0000-000000000006', 'citem001-0000-0000-0000-000000000028', 0.88),
('topic001-0000-0000-0000-000000000006', 'citem001-0000-0000-0000-000000000029', 0.85),
('topic001-0000-0000-0000-000000000006', 'citem001-0000-0000-0000-000000000030', 0.91)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 8. EXTRACTED ENTITIES (~45)
-- =============================================================================

INSERT INTO extracted_entities (id, content_item_id, entity_type, entity_text, confidence, language, created_at, labels) VALUES
-- CI-01 (Hormuz IRGC)
('entity01-0000-0000-0000-000000000001', 'citem001-0000-0000-0000-000000000001', 'ORG', 'IRGC Navy', 0.97, 'en', NOW() - INTERVAL '7 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000002', 'citem001-0000-0000-0000-000000000001', 'GPE', 'Strait of Hormuz', 0.99, 'en', NOW() - INTERVAL '7 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000003', 'citem001-0000-0000-0000-000000000001', 'GPE', 'Iran', 0.98, 'en', NOW() - INTERVAL '7 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-02 (Lloyd's insurance)
('entity01-0000-0000-0000-000000000004', 'citem001-0000-0000-0000-000000000002', 'ORG', 'Lloyd''s of London', 0.96, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000005', 'citem001-0000-0000-0000-000000000002', 'GPE', 'Cape of Good Hope', 0.91, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-04 (Bellingcat Great Prophet)
('entity01-0000-0000-0000-000000000006', 'citem001-0000-0000-0000-000000000004', 'FACILITY', 'Bandar Abbas Naval Base', 0.94, 'en', NOW() - INTERVAL '4 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000007', 'citem001-0000-0000-0000-000000000004', 'GPE', 'Qeshm Island', 0.93, 'en', NOW() - INTERVAL '4 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000008', 'citem001-0000-0000-0000-000000000004', 'EVENT', 'Great Prophet 19', 0.95, 'en', NOW() - INTERVAL '4 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-06 (BSF Tripura)
('entity01-0000-0000-0000-000000000009', 'citem001-0000-0000-0000-000000000006', 'ORG', 'BSF', 0.98, 'en', NOW() - INTERVAL '9 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000010', 'citem001-0000-0000-0000-000000000006', 'GPE', 'Tripura', 0.97, 'en', NOW() - INTERVAL '9 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000011', 'citem001-0000-0000-0000-000000000006', 'GPE', 'Akhaura', 0.89, 'en', NOW() - INTERVAL '9 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000012', 'citem001-0000-0000-0000-000000000006', 'WEAPON', 'AK-47', 0.95, 'en', NOW() - INTERVAL '9 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-09 (Rohingya repatriation)
('entity01-0000-0000-0000-000000000013', 'citem001-0000-0000-0000-000000000009', 'ORG', 'UNHCR', 0.97, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000014', 'citem001-0000-0000-0000-000000000009', 'GPE', 'Rakhine', 0.94, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000015', 'citem001-0000-0000-0000-000000000009', 'GPE', 'Mizoram', 0.93, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-11 (Jane's Aksai Chin road)
('entity01-0000-0000-0000-000000000016', 'citem001-0000-0000-0000-000000000011', 'ORG', 'PLA', 0.98, 'en', NOW() - INTERVAL '10 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000017', 'citem001-0000-0000-0000-000000000011', 'GPE', 'Aksai Chin', 0.97, 'en', NOW() - INTERVAL '10 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000018', 'citem001-0000-0000-0000-000000000011', 'GPE', 'Depsang Plains', 0.96, 'en', NOW() - INTERVAL '10 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000019', 'citem001-0000-0000-0000-000000000011', 'FACILITY', 'G219 Highway', 0.90, 'en', NOW() - INTERVAL '10 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-14 (Bellingcat Galwan)
('entity01-0000-0000-0000-000000000020', 'citem001-0000-0000-0000-000000000014', 'GPE', 'Galwan Valley', 0.98, 'en', NOW() - INTERVAL '5 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000021', 'citem001-0000-0000-0000-000000000014', 'ORG', 'Maxar', 0.87, 'en', NOW() - INTERVAL '5 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-13 (Hotan PLAAF)
('entity01-0000-0000-0000-000000000022', 'citem001-0000-0000-0000-000000000013', 'FACILITY', 'Hotan Airbase', 0.96, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000023', 'citem001-0000-0000-0000-000000000013', 'FACILITY', 'Kashgar Airbase', 0.94, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000024', 'citem001-0000-0000-0000-000000000013', 'WEAPON', 'Wing Loong II UAV', 0.95, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000025', 'citem001-0000-0000-0000-000000000013', 'WEAPON', 'J-16', 0.93, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-16 (FATF Pakistan)
('entity01-0000-0000-0000-000000000026', 'citem001-0000-0000-0000-000000000016', 'ORG', 'FATF', 0.99, 'en', NOW() - INTERVAL '9 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000027', 'citem001-0000-0000-0000-000000000016', 'ORG', 'Lashkar-e-Taiba', 0.97, 'en', NOW() - INTERVAL '9 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000028', 'citem001-0000-0000-0000-000000000016', 'ORG', 'Jaish-e-Mohammed', 0.97, 'en', NOW() - INTERVAL '9 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000029', 'citem001-0000-0000-0000-000000000016', 'GPE', 'Pakistan', 0.99, 'en', NOW() - INTERVAL '9 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-17 (Dubai hawala)
('entity01-0000-0000-0000-000000000030', 'citem001-0000-0000-0000-000000000017', 'GPE', 'Dubai', 0.98, 'en', NOW() - INTERVAL '7 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000031', 'citem001-0000-0000-0000-000000000017', 'GPE', 'Karachi', 0.96, 'en', NOW() - INTERVAL '7 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-21 (Hambantota)
('entity01-0000-0000-0000-000000000032', 'citem001-0000-0000-0000-000000000021', 'FACILITY', 'Hambantota Port', 0.98, 'en', NOW() - INTERVAL '8 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000033', 'citem001-0000-0000-0000-000000000021', 'ORG', 'CMPORT', 0.90, 'en', NOW() - INTERVAL '8 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000034', 'citem001-0000-0000-0000-000000000021', 'GPE', 'Sri Lanka', 0.99, 'en', NOW() - INTERVAL '8 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-22 (Djibouti)
('entity01-0000-0000-0000-000000000035', 'citem001-0000-0000-0000-000000000022', 'GPE', 'Djibouti', 0.99, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000036', 'citem001-0000-0000-0000-000000000022', 'ORG', 'PLA Navy', 0.97, 'en', NOW() - INTERVAL '6 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-25 (PLAN Task Group)
('entity01-0000-0000-0000-000000000037', 'citem001-0000-0000-0000-000000000025', 'WEAPON', 'Type 052D Destroyer Hohhot', 0.93, 'en', NOW() - INTERVAL '2 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000038', 'citem001-0000-0000-0000-000000000025', 'WEAPON', 'Type 054A Frigate Yueyang', 0.92, 'en', NOW() - INTERVAL '2 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000039', 'citem001-0000-0000-0000-000000000025', 'GPE', 'Strait of Malacca', 0.97, 'en', NOW() - INTERVAL '2 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-26 (CRPF Sukma)
('entity01-0000-0000-0000-000000000040', 'citem001-0000-0000-0000-000000000026', 'ORG', 'CRPF', 0.98, 'en', NOW() - INTERVAL '7 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000041', 'citem001-0000-0000-0000-000000000026', 'GPE', 'Sukma', 0.97, 'en', NOW() - INTERVAL '7 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000042', 'citem001-0000-0000-0000-000000000026', 'GPE', 'Chhattisgarh', 0.98, 'en', NOW() - INTERVAL '7 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000043', 'citem001-0000-0000-0000-000000000026', 'ORG', 'CPI(Maoist)', 0.96, 'en', NOW() - INTERVAL '7 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
-- CI-28 (Gadchiroli)
('entity01-0000-0000-0000-000000000044', 'citem001-0000-0000-0000-000000000028', 'GPE', 'Gadchiroli', 0.97, 'hi', NOW() - INTERVAL '5 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),
('entity01-0000-0000-0000-000000000045', 'citem001-0000-0000-0000-000000000028', 'ORG', 'C-60 Commandos', 0.94, 'hi', NOW() - INTERVAL '5 days', '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 9. CREDIBILITY AUDIT LOG (5 entries)
-- =============================================================================

INSERT INTO credibility_audit_log (id, source_id, old_score, new_score, reason, changed_by, created_at, labels) VALUES
(
    'audit001-0000-0000-0000-000000000001',
    'source01-0000-0000-0000-000000000006',
    55.0, 42.0,
    'Source shared unverified claims about Indian military operations 3 times — auto-downgrade triggered',
    'system:credibility-auto-update',
    NOW() - INTERVAL '12 days',
    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb
),
(
    'audit001-0000-0000-0000-000000000002',
    'source01-0000-0000-0000-000000000013',
    50.0, 35.0,
    'Channel shared fabricated BSF incident videos — manual downgrade by analyst',
    'user:demo0001-0000-0000-0000-000000000001',
    NOW() - INTERVAL '8 days',
    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb
),
(
    'audit001-0000-0000-0000-000000000003',
    'source01-0000-0000-0000-000000000015',
    40.0, 22.0,
    'Blog consistently publishes fabricated content with no verifiable sourcing — serial misinformation',
    'system:credibility-auto-update',
    NOW() - INTERVAL '6 days',
    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb
),
(
    'audit001-0000-0000-0000-000000000004',
    'source01-0000-0000-0000-000000000010',
    85.0, 89.0,
    'Bellingcat verified PLA positions with high-resolution imagery — credibility upgrade',
    'system:credibility-auto-update',
    NOW() - INTERVAL '5 days',
    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb
),
(
    'audit001-0000-0000-0000-000000000005',
    'source01-0000-0000-0000-000000000008',
    52.0, 48.0,
    'Gulf Watch shared 1 unverified claim about US naval movements — minor downgrade',
    'system:credibility-auto-update',
    NOW() - INTERVAL '4 days',
    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 10. SIGNALS (9)
-- =============================================================================

INSERT INTO signals (
    id, topic_id, cluster_id, signal_type,
    description, evidence, status,
    labels, created_at, updated_at
) VALUES
-- SIG-1: Hormuz IRGC harassment — HIGH (4 sources)
(
    'signal01-0000-0000-0000-000000000001',
    'topic001-0000-0000-0000-000000000001',
    'clust001-0000-0000-0000-000000000001',
    'multi_source_convergence',
    'IRGC fast-boat harassment campaign confirmed by 4 independent platforms — HIGH confidence',
    '{"cluster_id": "clust001-0000-0000-0000-000000000001", "independent_source_count": 4, "platforms": ["rss", "telegram", "web"], "source_names": ["Reuters", "Al Jazeera", "Telegram Gulf Watch", "OSINT Aggregator"]}'::jsonb,
    'new',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days'
),
-- SIG-2: Hormuz Great Prophet exercise — MEDIUM (3 sources)
(
    'signal01-0000-0000-0000-000000000002',
    'topic001-0000-0000-0000-000000000001',
    'clust001-0000-0000-0000-000000000002',
    'multi_source_convergence',
    'Iranian naval exercise staging confirmed near Bandar Abbas — 3 independent sources',
    '{"cluster_id": "clust001-0000-0000-0000-000000000002", "independent_source_count": 3, "platforms": ["web", "rss"], "source_names": ["Bellingcat", "Reuters", "Al Jazeera"]}'::jsonb,
    'acknowledged',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '2 days', NOW() - INTERVAL '1 day'
),
-- SIG-3: Bangladesh anti-India disinfo — MEDIUM (3 sources)
(
    'signal01-0000-0000-0000-000000000003',
    'topic001-0000-0000-0000-000000000002',
    'clust001-0000-0000-0000-000000000004',
    'multi_source_convergence',
    'Coordinated anti-India disinformation campaign detected from Dhaka-based accounts',
    '{"cluster_id": "clust001-0000-0000-0000-000000000004", "independent_source_count": 3, "platforms": ["telegram", "reddit", "web"], "source_names": ["Telegram Dhaka Leaks", "Reddit r/IndianDefence", "NDTV"]}'::jsonb,
    'new',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'
),
-- SIG-4: Bangladesh smuggling — MEDIUM (3 sources)
(
    'signal01-0000-0000-0000-000000000004',
    'topic001-0000-0000-0000-000000000002',
    'clust001-0000-0000-0000-000000000003',
    'multi_source_convergence',
    'Rohingya smuggling surge via Tripura border confirmed by 3 independent platforms',
    '{"cluster_id": "clust001-0000-0000-0000-000000000003", "independent_source_count": 3, "platforms": ["web", "rss", "reddit"], "source_names": ["TOI", "The Hindu", "Reddit r/IndianDefence"]}'::jsonb,
    'acknowledged',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '5 days', NOW() - INTERVAL '3 days'
),
-- SIG-5: China LAC road construction — HIGH (4 sources)
(
    'signal01-0000-0000-0000-000000000005',
    'topic001-0000-0000-0000-000000000003',
    'clust001-0000-0000-0000-000000000005',
    'multi_source_convergence',
    'PLA infrastructure build-up near Depsang Plains confirmed by 4 independent sources — HIGH confidence',
    '{"cluster_id": "clust001-0000-0000-0000-000000000005", "independent_source_count": 4, "platforms": ["web", "reddit"], "source_names": ["Jane''s", "SCMP", "Bellingcat", "Reddit r/IndianDefence"]}'::jsonb,
    'new',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days'
),
-- SIG-6: China PLAAF activity — MEDIUM (3 sources)
(
    'signal01-0000-0000-0000-000000000006',
    'topic001-0000-0000-0000-000000000003',
    'clust001-0000-0000-0000-000000000006',
    'multi_source_convergence',
    'Increased PLAAF sorties from Hotan and Kashgar airbases — 3 independent sources',
    '{"cluster_id": "clust001-0000-0000-0000-000000000006", "independent_source_count": 3, "platforms": ["web", "reddit", "telegram"], "source_names": ["Global Security", "Reddit r/IndianDefence", "OSINT Aggregator"]}'::jsonb,
    'new',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'
),
-- SIG-7: Pakistan hawala — MEDIUM (3 sources)
(
    'signal01-0000-0000-0000-000000000007',
    'topic001-0000-0000-0000-000000000004',
    'clust001-0000-0000-0000-000000000007',
    'multi_source_convergence',
    'LeT terror financing via Dubai-Karachi hawala corridor confirmed by 3 platforms',
    '{"cluster_id": "clust001-0000-0000-0000-000000000007", "independent_source_count": 3, "platforms": ["web", "rss", "telegram"], "source_names": ["Jane''s", "Reuters", "OSINT Aggregator"]}'::jsonb,
    'new',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000004"}'::jsonb,
    NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days'
),
-- SIG-8: IOR Hambantota — cross-topic convergence with China LAC
(
    'signal01-0000-0000-0000-000000000008',
    'topic001-0000-0000-0000-000000000005',
    'clust001-0000-0000-0000-000000000008',
    'cross_topic_convergence',
    'Chinese military expansion narrative converges across LAC and IOR topics — coordinated strategic posture',
    '{"cluster_id": "clust001-0000-0000-0000-000000000008", "converging_topic_ids": ["topic001-0000-0000-0000-000000000003", "topic001-0000-0000-0000-000000000005"], "cosine_similarity": 0.78, "platforms": ["web", "rss"], "source_names": ["Jane''s", "Reuters", "SCMP", "Global Security"]}'::jsonb,
    'new',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000005"}'::jsonb,
    NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day'
),
-- SIG-9: LWE IED campaign — MEDIUM (3 sources), dismissed
(
    'signal01-0000-0000-0000-000000000009',
    'topic001-0000-0000-0000-000000000006',
    'clust001-0000-0000-0000-000000000010',
    'multi_source_convergence',
    'CPI(Maoist) IED campaign in Sukma-Bijapur corridor — common fabrication source identified',
    '{"cluster_id": "clust001-0000-0000-0000-000000000010", "independent_source_count": 3, "platforms": ["web", "reddit", "telegram"], "source_names": ["TOI", "NDTV", "OSINT Aggregator"]}'::jsonb,
    'dismissed',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000006"}'::jsonb,
    NOW() - INTERVAL '2 days', NOW() - INTERVAL '1 day'
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 11. REPORTS (6 — two of each type)
-- =============================================================================

-- R1: Hormuz intelligence brief
INSERT INTO reports (
    id, topic_id, report_type,
    time_window_start, time_window_end, credibility_min_filter,
    content_md, confidence_score, generated_at,
    source_snapshot, content_item_count, geojson,
    labels, created_at, updated_at
) VALUES
(
    'report01-0000-0000-0000-000000000001',
    'topic001-0000-0000-0000-000000000001',
    'intelligence_brief',
    NOW() - INTERVAL '10 days',
    NOW() - INTERVAL '2 days',
    30.0,
    E'# Intelligence Brief: Strait of Hormuz Maritime Threat Assessment\n\n**Classification:** OPEN | **Generated:** Auto | **Confidence:** HIGH (0.85)\n\n---\n\n## Executive Summary\n\nOpen-source intelligence collected over the past 8 days confirms a significant escalation in Iranian Revolutionary Guard Corps Navy (IRGCN) activity in the Strait of Hormuz. Four independent sources across three platforms report fast-boat harassment of commercial shipping, while satellite imagery reveals preparation for the "Great Prophet 19" naval exercise.\n\n## Key Findings\n\n### 1. IRGC Fast-Boat Harassment Campaign\n- **Incidents:** At least 3 interceptions of commercial oil tankers confirmed since April 15\n- **Escalation indicator:** Warning shots fired at a Marshall Islands-flagged VLCC (Reuters, credibility: 88%)\n- **Insurance impact:** Lloyd''s of London raised war-risk premiums by 150% for Hormuz transit\n- **AIS data:** 8 VLCCs diverted from the narrowest transit zone in 72 hours\n\n### 2. Great Prophet 19 Exercise Staging\n- **Location:** Bandar Abbas Naval Base and Qeshm Island\n- **Assets identified:** 12+ missile-armed fast attack craft, 3 Ghadir-class midget submarines (Bellingcat, credibility: 89%)\n- **Coastal defence:** TEL vehicles deployed at Qeshm Island positions\n- **Assessment:** Exercise likely to commence within 7-10 days\n\n### 3. Economic Impact Indicators\n- Shipping rerouting via Cape of Good Hope adds 10-14 days transit time\n- Estimated $1.2M additional fuel cost per VLCC for Cape route\n- Brent crude futures up 3.2% on Hormuz tensions\n\n## Source Assessment Matrix\n\n| Source | Platform | Credibility | Contribution |\n|--------|----------|------------|-------------|\n| Reuters | RSS | 88% | IRGC interception reporting |\n| Al Jazeera | RSS | 70% | Insurance premium analysis |\n| Bellingcat | Web | 89% | Satellite imagery analysis |\n| Telegram Gulf Watch | Telegram | 48% | Real-time maritime reports |\n| OSINT Aggregator | Telegram | 55% | AIS tracking data |\n\n## Confidence Assessment\n\n**Overall: HIGH (0.85)**\n- Primary claims corroborated by 4 independent sources across 3 platforms\n- Satellite imagery provides objective verification\n- Insurance market response provides independent economic validation\n\n## Recommendations\n\n1. Monitor AIS data for further tanker diversions as leading indicator\n2. Track Great Prophet 19 exercise timeline for escalation triggers\n3. Cross-reference with US CENTCOM public statements for allied response indicators\n\n---\n*Generated by Anveshak OSINT Analysis Platform. Analyst review recommended before dissemination.*',
    0.85,
    NOW() - INTERVAL '2 days',
    '{"source01-0000-0000-0000-000000000002": {"name": "Reuters", "credibility_score": 88.0}, "source01-0000-0000-0000-000000000004": {"name": "Al Jazeera", "credibility_score": 70.0}, "source01-0000-0000-0000-000000000010": {"name": "Bellingcat", "credibility_score": 89.0}, "source01-0000-0000-0000-000000000008": {"name": "Telegram Gulf Watch", "credibility_score": 48.0}, "source01-0000-0000-0000-000000000007": {"name": "OSINT Aggregator", "credibility_score": 55.0}}'::jsonb,
    5,
    '{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [56.27, 26.57]}, "properties": {"name": "Strait of Hormuz — Interception Zone"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [56.28, 27.18]}, "properties": {"name": "Bandar Abbas Naval Base"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [55.98, 26.82]}, "properties": {"name": "Qeshm Island — Coastal Defence"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [56.35, 25.23]}, "properties": {"name": "Fujairah Anchorage — Tanker Diversion"}}]}'::jsonb,
    '{"classification": "OPEN", "domain": "report", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'
)
ON CONFLICT (id) DO NOTHING;

-- R2: China LAC intelligence brief
INSERT INTO reports (
    id, topic_id, report_type,
    time_window_start, time_window_end, credibility_min_filter,
    content_md, confidence_score, generated_at,
    source_snapshot, content_item_count, geojson,
    labels, created_at, updated_at
) VALUES
(
    'report01-0000-0000-0000-000000000002',
    'topic001-0000-0000-0000-000000000003',
    'intelligence_brief',
    NOW() - INTERVAL '14 days',
    NOW() - INTERVAL '3 days',
    30.0,
    E'# Intelligence Brief: PLA Military Build-up Along LAC\n\n**Classification:** OPEN | **Generated:** Auto | **Confidence:** HIGH (0.88)\n\n---\n\n## Executive Summary\n\nMulti-source intelligence confirms an accelerated PLA military infrastructure build-up along the Line of Actual Control (LAC) in the Aksai Chin-Ladakh sector. Road construction, helipad development, and increased air activity from Hotan and Kashgar airbases collectively indicate either an enhanced defensive posture or preparation for coercive positioning.\n\n## Key Findings\n\n### 1. Ground Infrastructure — Aksai Chin Road Extension\n- **New road segment:** 45km extension from G219 highway toward Depsang Plains\n- **Proximity:** Vehicular access now within 25km of Indian forward positions\n- **Helipads:** 2 new helicopter landing pads at intermediate waypoints\n- **Source:** Jane''s Intelligence Review (credibility: 91%) — highest confidence\n\n### 2. Defensive Positions — Galwan Valley Sector\n- **New positions:** Semi-permanent defensive structures 8km from LAC\n- **Infrastructure:** Reinforced bunkers, vehicle revetments, pre-positioned supply caches\n- **Assessment:** Forward movement beyond post-2020 buffer zone arrangements\n- **Source:** Bellingcat geolocation of Maxar imagery (credibility: 89%)\n\n### 3. Air Activity — Hotan & Kashgar Airbases\n- **Sortie increase:** 200% month-over-month for Wing Loong II UAVs\n- **Fighter aircraft:** J-16 multirole fighters in increased numbers at Hotan\n- **Flight patterns:** Surveillance tracks over Aksai Chin plateau\n- **Source:** Global Security ADS-B analysis (credibility: 82%)\n\n### 4. Logistics Exercise — Western Theatre Command\n- **Exercise scope:** 2,000 personnel, combined-arms brigade deployment to 4,500m+\n- **Focus:** Cold-weather equipment supply chain validation\n- **Correlation:** Exercise area corresponds to Aksai Chin-Ladakh frontier\n\n## Threat Assessment\n\nThe combination of infrastructure expansion, forward defensive positioning, and increased air activity suggests a deliberate enhancement of PLA operational capability along the LAC. While this could represent routine modernisation, the pace and forward positioning exceed peacetime norms.\n\n## Confidence Assessment\n\n**Overall: HIGH (0.88)**\n- 4 independent sources across web and social platforms\n- Satellite imagery provides objective ground truth\n- Consistent with PLA Western Theatre Command operational patterns\n\n---\n*Generated by Anveshak OSINT Analysis Platform. Analyst review recommended before dissemination.*',
    0.88,
    NOW() - INTERVAL '3 days',
    '{"source01-0000-0000-0000-000000000001": {"name": "Jane''s Defence Weekly", "credibility_score": 91.0}, "source01-0000-0000-0000-000000000003": {"name": "SCMP", "credibility_score": 74.0}, "source01-0000-0000-0000-000000000010": {"name": "Bellingcat", "credibility_score": 89.0}, "source01-0000-0000-0000-000000000014": {"name": "Global Security", "credibility_score": 82.0}}'::jsonb,
    5,
    '{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [78.18, 35.50]}, "properties": {"name": "Depsang Plains — Road Construction"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [78.17, 34.75]}, "properties": {"name": "Galwan Valley — New Defensive Positions"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [79.93, 37.13]}, "properties": {"name": "Hotan Airbase — PLAAF Activity"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [75.99, 39.47]}, "properties": {"name": "Kashgar Airbase"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [79.06, 35.18]}, "properties": {"name": "Aksai Chin — G219 Road Extension"}}]}'::jsonb,
    '{"classification": "OPEN", "domain": "report", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days'
)
ON CONFLICT (id) DO NOTHING;

-- R3: Bangladesh research summary
INSERT INTO reports (
    id, topic_id, report_type,
    time_window_start, time_window_end, credibility_min_filter,
    content_md, confidence_score, generated_at,
    source_snapshot, content_item_count,
    labels, created_at, updated_at
) VALUES
(
    'report01-0000-0000-0000-000000000003',
    'topic001-0000-0000-0000-000000000002',
    'research_summary',
    NOW() - INTERVAL '14 days',
    NOW() - INTERVAL '2 days',
    30.0,
    E'# Research Summary: Bangladesh Border Security & Instability\n\n**Classification:** OPEN | **Period:** 14 days | **Confidence:** MEDIUM-HIGH (0.76)\n\n---\n\n## Overview\n\nThis research summary analyses two converging threat vectors on the India-Bangladesh border: (1) an increase in Rohingya smuggling and arms trafficking via the Tripura-Bangladesh border, and (2) a coordinated anti-India disinformation campaign originating from Dhaka-based social media accounts.\n\n## Thread 1: Rohingya Smuggling Surge\n\n### Key Observations\n- BSF seized arms cache including 3 AK-47 rifles at Akhaura sector, Tripura (TOI, credibility: 65%)\n- Monsoon damage has created 47 gaps in India-Bangladesh border fencing in West Bengal and Tripura (NDTV, credibility: 68%)\n- UNHCR reports 60% increase in Rohingya crossings into India''s northeast (The Hindu, credibility: 72%)\n- Myanmar''s Rakhine state instability continues to drive outflows\n\n### Assessment\nOrganised smuggling networks are systematically exploiting monsoon-weakened fence sections. The co-occurrence of arms seizures with Rohingya movement suggests some networks serve dual purposes — human smuggling and arms trafficking.\n\n## Thread 2: Anti-India Disinformation Campaign\n\n### Key Observations\n- 47 coordinated accounts created within 48 hours sharing identical fabricated videos (Reddit, credibility: 52%)\n- Fabricated BSF "atrocity" videos traced to edited Myanmar footage\n- 340% spike in anti-India social media posts from Dhaka-based accounts over 72 hours\n- Telegram channel @dhaka_leaks_bd identified as primary amplification node (credibility: 35%)\n\n### Assessment\nThe campaign bears hallmarks of state-adjacent information warfare rather than organic protest. The synchronised account creation, identical content distribution, and use of recycled footage from unrelated conflicts indicate professional coordination.\n\n## Source Reliability\n\n| Source | Credibility | Notes |\n|--------|------------|-------|\n| The Hindu | 72% | Reliable on Rohingya data |\n| NDTV | 68% | Consistent border reporting |\n| TOI | 65% | Ground-level incidents |\n| Reddit r/IndianDefence | 52% | Useful aggregation, verify claims |\n| Telegram Dhaka Leaks | 35% | **CAUTION** — primary disinfo amplifier |\n\n## Confidence: MEDIUM-HIGH (0.76)\n\nSmuggling thread well-sourced; disinfo thread relies partly on low-credibility Telegram source.\n\n---\n*Generated by Anveshak OSINT Analysis Platform.*',
    0.76,
    NOW() - INTERVAL '2 days',
    '{"source01-0000-0000-0000-000000000005": {"name": "TOI", "credibility_score": 65.0}, "source01-0000-0000-0000-000000000011": {"name": "NDTV", "credibility_score": 68.0}, "source01-0000-0000-0000-000000000012": {"name": "The Hindu", "credibility_score": 72.0}, "source01-0000-0000-0000-000000000013": {"name": "Telegram Dhaka Leaks", "credibility_score": 35.0}, "source01-0000-0000-0000-000000000009": {"name": "Reddit r/IndianDefence", "credibility_score": 52.0}}'::jsonb,
    5,
    '{"classification": "OPEN", "domain": "report", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'
)
ON CONFLICT (id) DO NOTHING;

-- R4: Pakistan Proxy Networks research summary
INSERT INTO reports (
    id, topic_id, report_type,
    time_window_start, time_window_end, credibility_min_filter,
    content_md, confidence_score, generated_at,
    source_snapshot, content_item_count,
    labels, created_at, updated_at
) VALUES
(
    'report01-0000-0000-0000-000000000004',
    'topic001-0000-0000-0000-000000000004',
    'research_summary',
    NOW() - INTERVAL '14 days',
    NOW() - INTERVAL '1 day',
    30.0,
    E'# Research Summary: Pakistan Proxy Networks — Terror Financing\n\n**Classification:** OPEN | **Period:** 14 days | **Confidence:** HIGH (0.82)\n\n---\n\n## Overview\n\nThis summary analyses the current state of terror financing networks linked to Pakistan-based designated entities, drawing on FATF assessments, financial intelligence, and ground-level enforcement actions.\n\n## Key Findings\n\n### 1. FATF Grey List Status (April 2026)\n- Pakistan failed to exit FATF grey list at April plenary (Jane''s, credibility: 91%)\n- Cited deficiencies: prosecution gaps for LeT and JeM financing cases\n- Structural reforms acknowledged but operational enforcement weak\n\n### 2. Dubai-Karachi Hawala Corridor\n- UAE arrested Dubai-based hawala operator linked to LeT front organisations (Reuters, credibility: 88%)\n- Estimated $2.3M transferred over 18 months\n- At least 4 hawala operators identified in the network\n- Intelligence sharing between UAE and Indian agencies enabled the arrest\n\n### 3. JeM Operational Activity\n- NIA busted JeM sleeper cell in Jammu division (TOI, credibility: 65%)\n- Seized: Rs 15 lakh hawala cash, Pakistani SIM cards, encrypted devices\n- Three suspects receiving instructions from Pakistan-based handlers\n\n### 4. JeM Training Infrastructure\n- Satellite imagery shows renewed activity at known JeM facility near Bahawalpur (OSINT Aggregator, credibility: 55%)\n- Vehicle movements, new temporary structures, obstacle courses visible\n\n### 5. Counter-Narrative (Low Credibility)\n- Pakistani Defence Forum claims FATF process is "weaponised" by India (credibility: 42%)\n- Assessed as deflection narrative — no factual basis provided\n\n## Financial Flow Mapping\n\n```\nDubai Exchange Houses → Hawala Network → Karachi Front Orgs → LeT/JeM Operatives\n     ($2.3M/18mo)         (4+ operators)     (identified)        (active cells)\n```\n\n## Confidence: HIGH (0.82)\n\nPrimary claims from high-credibility sources (Jane''s 91%, Reuters 88%). Ground truth from NIA enforcement action.\n\n---\n*Generated by Anveshak OSINT Analysis Platform.*',
    0.82,
    NOW() - INTERVAL '1 day',
    '{"source01-0000-0000-0000-000000000001": {"name": "Jane''s Defence Weekly", "credibility_score": 91.0}, "source01-0000-0000-0000-000000000002": {"name": "Reuters", "credibility_score": 88.0}, "source01-0000-0000-0000-000000000005": {"name": "TOI", "credibility_score": 65.0}, "source01-0000-0000-0000-000000000006": {"name": "Pak Defence Forum", "credibility_score": 42.0}, "source01-0000-0000-0000-000000000007": {"name": "OSINT Aggregator", "credibility_score": 55.0}}'::jsonb,
    5,
    '{"classification": "OPEN", "domain": "report", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000004"}'::jsonb,
    NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day'
)
ON CONFLICT (id) DO NOTHING;

-- R5: IOR Naval weekly digest
INSERT INTO reports (
    id, topic_id, report_type,
    time_window_start, time_window_end, credibility_min_filter,
    content_md, confidence_score, generated_at,
    source_snapshot, content_item_count, geojson,
    labels, created_at, updated_at
) VALUES
(
    'report01-0000-0000-0000-000000000005',
    'topic001-0000-0000-0000-000000000005',
    'weekly_digest',
    NOW() - INTERVAL '7 days',
    NOW(),
    30.0,
    E'# Weekly Digest: Indian Ocean Region — PLAN Naval Expansion\n\n**Classification:** OPEN | **Week:** April 18-25, 2026 | **Confidence:** HIGH (0.84)\n\n---\n\n## This Week''s Highlights\n\n### Hambantota Port Expansion\n- Pier infrastructure expansion confirmed beyond commercial requirements (Jane''s, 91%)\n- New deep-water berth accommodates vessels up to 60,000 tonnes — consistent with PLAN Type 075 LHD\n- CMPORT (Chinese state-owned) holds 99-year lease\n\n### PLAN Survey Vessel Activity\n- Hai Yang 26 conducting hydrographic surveys near Hambantota for 12 days (SCMP, 74%)\n- Equipment: multi-beam sonar, sub-bottom profiling (submarine navigation chart preparation)\n- Sri Lanka granted research permit despite Indian protests\n\n### Djibouti Base Pier Extension\n- 400-metre pier extension ~80% complete (Reuters, 88%)\n- Would enable berthing of China''s largest warships\n- First overseas PLAN facility with large-vessel capability if completed\n\n### PLAN Task Group 47 Deployment\n- Type 052D destroyer Hohhot, Type 054A frigate Yueyang, Type 903A replenishment ship Dongpinghu\n- Transited Strait of Malacca on April 18 heading west (Bellingcat, 89%)\n- Expected port calls: Hambantota, Djibouti\n\n### String of Pearls — Updated Network\n- Active military-capable facilities: Gwadar, Hambantota, Chittagong, Djibouti\n- Planned: Marao (Maldives), Beira (Mozambique) — still in negotiation\n- Network provides logistical depth from Persian Gulf to Malacca Strait\n\n## Cross-Topic Signal\n\n**ALERT:** Chinese military expansion narrative converges across LAC (Topic: China LAC) and IOR topics. This suggests a coordinated strategic posture rather than isolated regional activities.\n\n## Source Summary\n\n| Source | Items | Avg Credibility |\n|--------|-------|-----------------|\n| Jane''s | 1 | 91% |\n| Reuters | 1 | 88% |\n| Bellingcat | 1 | 89% |\n| SCMP | 1 | 74% |\n| Global Security | 1 | 82% |\n\n---\n*Weekly digest generated automatically by Anveshak.*',
    0.84,
    NOW(),
    '{"source01-0000-0000-0000-000000000001": {"name": "Jane''s Defence Weekly", "credibility_score": 91.0}, "source01-0000-0000-0000-000000000002": {"name": "Reuters", "credibility_score": 88.0}, "source01-0000-0000-0000-000000000003": {"name": "SCMP", "credibility_score": 74.0}, "source01-0000-0000-0000-000000000010": {"name": "Bellingcat", "credibility_score": 89.0}, "source01-0000-0000-0000-000000000014": {"name": "Global Security", "credibility_score": 82.0}}'::jsonb,
    5,
    '{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [81.12, 6.12]}, "properties": {"name": "Hambantota Port, Sri Lanka"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [43.15, 11.59]}, "properties": {"name": "Djibouti Support Base"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [62.33, 25.12]}, "properties": {"name": "Gwadar Port, Pakistan"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [91.83, 22.33]}, "properties": {"name": "Chittagong Port, Bangladesh"}}, {"type": "Feature", "geometry": {"type": "Point", "coordinates": [100.47, 2.50]}, "properties": {"name": "Strait of Malacca — TG47 Transit"}}]}'::jsonb,
    '{"classification": "OPEN", "domain": "report", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000005"}'::jsonb,
    NOW(), NOW()
)
ON CONFLICT (id) DO NOTHING;

-- R6: LWE weekly digest
INSERT INTO reports (
    id, topic_id, report_type,
    time_window_start, time_window_end, credibility_min_filter,
    content_md, confidence_score, generated_at,
    source_snapshot, content_item_count,
    labels, created_at, updated_at
) VALUES
(
    'report01-0000-0000-0000-000000000006',
    'topic001-0000-0000-0000-000000000006',
    'weekly_digest',
    NOW() - INTERVAL '7 days',
    NOW(),
    30.0,
    E'# Weekly Digest: Internal Security — Left Wing Extremism\n\n**Classification:** OPEN | **Week:** April 18-25, 2026 | **Confidence:** MEDIUM-HIGH (0.78)\n\n---\n\n## This Week''s Highlights\n\n### IED Campaign — Sukma-Bijapur Corridor\n- 4 IED attacks targeting CRPF road-opening parties in 10 days\n- 3 jawans injured in latest Kistaram attack (TOI, 65%)\n- Explosive forensics indicate **common fabrication source** across all 4 incidents (OSINT Aggregator, 55%)\n- Devices: pressure-plate activated, 5-8kg main charge\n\n### Maoist Leaflet Campaign\n- CPI(Maoist) leaflets recovered from Bastar division villages (NDTV, 68%)\n- Content: panchayat election boycott call + warning of "intensified armed resistance"\n- Assessment: pre-election intimidation campaign\n\n### Gadchiroli Encounter\n- Maharashtra C-60 commandos neutralised 4 CPI(Maoist) cadres in Etapalli taluka (The Hindu, 72%)\n- Included dalam commander with Rs 10 lakh bounty\n- Arms and explosives recovered\n\n### Supply Route Analysis\n- CPI(Maoist) consolidating logistics through Gadchiroli-Bastar-Sukma corridor (Reddit, 52%)\n- Shift from traditional Abujhmad sanctuary may indicate operational pressure\n- New partnerships with local smuggling networks suspected\n\n## Threat Trend\n\nThe combination of an IED campaign, election boycott leaflets, and cadre losses suggests CPI(Maoist) is simultaneously under pressure from security operations and escalating asymmetric attacks ahead of panchayat elections. The common IED fabrication source indicates a centralised bomb-making capability that remains intact.\n\n## Source Summary\n\n| Source | Items | Avg Credibility |\n|--------|-------|-----------------|\n| TOI | 1 | 65% |\n| NDTV | 1 | 68% |\n| The Hindu | 1 | 72% |\n| Reddit | 1 | 52% |\n| OSINT Aggregator | 1 | 55% |\n\n---\n*Weekly digest generated automatically by Anveshak.*',
    0.78,
    NOW(),
    '{"source01-0000-0000-0000-000000000005": {"name": "TOI", "credibility_score": 65.0}, "source01-0000-0000-0000-000000000011": {"name": "NDTV", "credibility_score": 68.0}, "source01-0000-0000-0000-000000000012": {"name": "The Hindu", "credibility_score": 72.0}, "source01-0000-0000-0000-000000000009": {"name": "Reddit r/IndianDefence", "credibility_score": 52.0}, "source01-0000-0000-0000-000000000007": {"name": "OSINT Aggregator", "credibility_score": 55.0}}'::jsonb,
    5,
    '{"classification": "OPEN", "domain": "report", "owner_org": "anveshak", "topic_id": "topic001-0000-0000-0000-000000000006"}'::jsonb,
    NOW(), NOW()
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 12. REPORT SOURCE WARNINGS (2)
-- =============================================================================

INSERT INTO report_source_warnings (
    id, report_id, source_id, source_name,
    warning_type, old_score, new_score,
    labels, created_at, updated_at
) VALUES
(
    'rswarn01-0000-0000-0000-000000000001',
    'report01-0000-0000-0000-000000000003',
    'source01-0000-0000-0000-000000000013',
    'Telegram Dhaka Leaks',
    'credibility_downgraded',
    50.0, 35.0,
    '{"classification": "OPEN", "domain": "report", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day'
),
(
    'rswarn01-0000-0000-0000-000000000002',
    'report01-0000-0000-0000-000000000004',
    'source01-0000-0000-0000-000000000015',
    'Kashmir Truth Blog (Suspicious)',
    'credibility_downgraded',
    40.0, 22.0,
    '{"classification": "OPEN", "domain": "report", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '12 hours', NOW() - INTERVAL '12 hours'
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 13. ANALYSIS JOBS (4 completed)
-- =============================================================================

INSERT INTO analysis_jobs (
    id, job_type, topic_id, status,
    payload, result, error,
    labels, created_at, updated_at
) VALUES
(
    'ajob0001-0000-0000-0000-000000000001',
    'scrape', 'topic001-0000-0000-0000-000000000001', 'done',
    '{"sources": 5, "topic_name": "Strait of Hormuz"}'::jsonb,
    '{"items_scraped": 5, "items_new": 5, "items_duplicate": 0, "duration_seconds": 42}'::jsonb,
    NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '7 days', NOW() - INTERVAL '7 days'
),
(
    'ajob0001-0000-0000-0000-000000000002',
    'cluster', 'topic001-0000-0000-0000-000000000003', 'done',
    '{"topic_name": "China LAC", "algorithm": "hdbscan"}'::jsonb,
    '{"clusters_formed": 2, "items_clustered": 5, "noise_items": 0}'::jsonb,
    NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days'
),
(
    'ajob0001-0000-0000-0000-000000000003',
    'signal_check', NULL, 'done',
    '{"check_type": "scheduled", "topics_checked": 6}'::jsonb,
    '{"signals_fired": 3, "signals_suppressed": 1}'::jsonb,
    NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'
),
(
    'ajob0001-0000-0000-0000-000000000004',
    'report', 'topic001-0000-0000-0000-000000000005', 'done',
    '{"report_type": "weekly_digest", "topic_name": "IOR Naval"}'::jsonb,
    '{"report_id": "report01-0000-0000-0000-000000000005", "content_items_used": 5, "generation_time_seconds": 87}'::jsonb,
    NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW(), NOW()
)
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- =============================================================================
-- Summary
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE '=============================================================';
    RAISE NOTICE 'Anveshak Full Demo Seed — Complete';
    RAISE NOTICE '=============================================================';
    RAISE NOTICE '  Users:              1 (demo@anveshak.local / AnveshakDemo2024!)';
    RAISE NOTICE '  Topics:             6';
    RAISE NOTICE '  Sources:           15 (mixed platforms & credibility)';
    RAISE NOTICE '  Topic-Sources:     31 associations';
    RAISE NOTICE '  Content Items:     30';
    RAISE NOTICE '  Extracted Entities: 45';
    RAISE NOTICE '  Narrative Clusters: 10';
    RAISE NOTICE '  Signals:            9 (5 new, 2 acknowledged, 1 dismissed, 1 cross-topic)';
    RAISE NOTICE '  Reports:            6 (2 intelligence_brief, 2 research_summary, 2 weekly_digest)';
    RAISE NOTICE '  Report Warnings:    2';
    RAISE NOTICE '  Audit Log:          5 entries';
    RAISE NOTICE '  Analysis Jobs:      4 completed';
    RAISE NOTICE '=============================================================';
    RAISE NOTICE '';
    RAISE NOTICE '  Login:    http://localhost:3000';
    RAISE NOTICE '  Username: demo@anveshak.local';
    RAISE NOTICE '  Password: AnveshakDemo2024!';
    RAISE NOTICE '';
    RAISE NOTICE '  Topics:';
    RAISE NOTICE '    1. Strait of Hormuz — Maritime Threat Monitoring';
    RAISE NOTICE '    2. Bangladesh Border Security & Instability';
    RAISE NOTICE '    3. China LAC Military Build-up';
    RAISE NOTICE '    4. Pakistan Proxy Networks — Terror Financing';
    RAISE NOTICE '    5. Indian Ocean Region — PLAN Naval Expansion';
    RAISE NOTICE '    6. Internal Security — Left Wing Extremism';
    RAISE NOTICE '=============================================================';
END $$;
