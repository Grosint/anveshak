-- =============================================================================
-- ANVESHAK — Engine C Demo Seed Data
-- 4 Agency Scenarios: MEA, Police Cyber, SEBI, NCB
-- =============================================================================
-- Usage:
--   make seed-demo-ec
--   # or: psql -U anveshak -d anveshak < scripts/seed_demo_engine_c.sql
--
-- Each agency gets its own org + user + topic.  Data is fully org-isolated.
-- All INSERTs are idempotent (ON CONFLICT DO NOTHING).
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. ORGANIZATIONS
-- =============================================================================

INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
VALUES
    ('org_mea',   'MEA — XP Division',       'mea',   NOW(), NOW(),
     '{"classification":"OPEN","domain":"platform"}'::jsonb),
    ('org_cyber', 'Police Cyber Cell',        'cyber', NOW(), NOW(),
     '{"classification":"OPEN","domain":"platform"}'::jsonb),
    ('org_sebi',  'SEBI Surveillance',        'sebi',  NOW(), NOW(),
     '{"classification":"OPEN","domain":"platform"}'::jsonb),
    ('org_ncb',   'NCB Intelligence Bureau',  'ncb',   NOW(), NOW(),
     '{"classification":"OPEN","domain":"platform"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 2. USERS (password: AnveshakDemo2024! — same bcrypt hash as existing demo)
-- =============================================================================

INSERT INTO users (id, username, password_hash, role, org_id, created_at, updated_at, labels)
VALUES
    ('ec-user-mea',   'demo_mea@anveshak.local',
     '$2b$12$exK0vBQZHOMCPjg37GTJZ.AtYqz1NI5SXwMLrWjnPvP2IqZMZKaei',
     'analyst', 'org_mea',   NOW(), NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb),

    ('ec-user-cyber', 'demo_cyber@anveshak.local',
     '$2b$12$exK0vBQZHOMCPjg37GTJZ.AtYqz1NI5SXwMLrWjnPvP2IqZMZKaei',
     'analyst', 'org_cyber', NOW(), NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),

    ('ec-user-sebi',  'demo_sebi@anveshak.local',
     '$2b$12$exK0vBQZHOMCPjg37GTJZ.AtYqz1NI5SXwMLrWjnPvP2IqZMZKaei',
     'analyst', 'org_sebi',  NOW(), NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb),

    ('ec-user-ncb',   'demo_ncb@anveshak.local',
     '$2b$12$exK0vBQZHOMCPjg37GTJZ.AtYqz1NI5SXwMLrWjnPvP2IqZMZKaei',
     'analyst', 'org_ncb',   NOW(), NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb"}'::jsonb)
ON CONFLICT (username) DO NOTHING;

-- =============================================================================
-- 3. TOPICS (one per agency, with Engine C identifier_signal_threshold)
-- =============================================================================

INSERT INTO topics (id, name, keywords, signal_threshold, identifier_signal_threshold, status, labels, created_at, updated_at, org_id)
VALUES
    ('ec-topic-mea',
     'Anti-India Narratives in Chinese Media',
     ARRAY['India', 'LAC', 'Arunachal', 'South Tibet', 'Modi', 'border'],
     3, 3, 'active',
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb,
     NOW() - INTERVAL '14 days', NOW(), 'org_mea'),

    ('ec-topic-cyber',
     'Mule Account & Investment Fraud Networks',
     ARRAY['bank account', 'commission', 'guaranteed returns', 'easy money', 'mule'],
     2, 2, 'active',
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb,
     NOW() - INTERVAL '10 days', NOW(), 'org_cyber'),

    ('ec-topic-sebi',
     'Pump-and-Dump Detection — Small Cap',
     ARRAY['multibagger', 'guaranteed returns', 'buy before', 'insider tip', 'XYZLTD'],
     2, 2, 'active',
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb,
     NOW() - INTERVAL '7 days', NOW(), 'org_sebi'),

    ('ec-topic-ncb',
     'Drug Network Monitoring — South India',
     ARRAY['stuff available', 'delivery', '420', 'green', 'maal'],
     2, 2, 'active',
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb"}'::jsonb,
     NOW() - INTERVAL '7 days', NOW(), 'org_ncb')
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 4. SOURCES
-- =============================================================================

-- MEA sources (5)
INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, labels, created_at, updated_at, org_id)
VALUES
    ('ec-src-mea-1', 'Global Times',        'https://www.globaltimes.cn',      'web', 35.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb, NOW()-INTERVAL '14 days', NOW(), 'org_mea'),
    ('ec-src-mea-2', 'CGTN',                'https://www.cgtn.com',            'web', 40.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb, NOW()-INTERVAL '14 days', NOW(), 'org_mea'),
    ('ec-src-mea-3', 'Xinhua News',          'https://www.xinhuanet.com',       'web', 38.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb, NOW()-INTERVAL '14 days', NOW(), 'org_mea'),
    ('ec-src-mea-4', 'People''s Daily',      'https://en.people.cn',            'web', 36.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb, NOW()-INTERVAL '14 days', NOW(), 'org_mea'),
    ('ec-src-mea-5', 'China Military Online', 'https://eng.chinamil.com.cn',    'web', 30.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb, NOW()-INTERVAL '14 days', NOW(), 'org_mea')
ON CONFLICT (id) DO NOTHING;

-- Cyber Police sources (6)
INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, labels, created_at, updated_at, org_id)
VALUES
    ('ec-src-cy-1', 'Telegram: Easy Money India',  '@easy_money_india',        'telegram', 15.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '10 days', NOW(), 'org_cyber'),
    ('ec-src-cy-2', 'Telegram: Account Service',   '@account_service_247',     'telegram', 12.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '10 days', NOW(), 'org_cyber'),
    ('ec-src-cy-3', 'Telegram: VIP Earning Group', '@vip_earning_group',       'telegram', 18.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '10 days', NOW(), 'org_cyber'),
    ('ec-src-cy-4', 'Telegram: Investment Tips',   '@investment_tips_pro',     'telegram', 20.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '10 days', NOW(), 'org_cyber'),
    ('ec-src-cy-5', 'Telegram: Trading VIP',       '@trading_vip_club',       'telegram', 16.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '10 days', NOW(), 'org_cyber'),
    ('ec-src-cy-6', 'Fake Investment Portal',       'https://fakeinvestment.example.com', 'web', 10.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '10 days', NOW(), 'org_cyber')
ON CONFLICT (id) DO NOTHING;

-- SEBI sources (5)
INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, labels, created_at, updated_at, org_id)
VALUES
    ('ec-src-sebi-1', 'Telegram: Stock Tips Free',      '@stock_tips_free',     'telegram', 14.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb, NOW()-INTERVAL '7 days', NOW(), 'org_sebi'),
    ('ec-src-sebi-2', 'Telegram: Penny Stock VIP',      '@penny_stock_vip',     'telegram', 11.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb, NOW()-INTERVAL '7 days', NOW(), 'org_sebi'),
    ('ec-src-sebi-3', 'Telegram: Trading Guru India',   '@trading_guru_india',  'telegram', 16.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb, NOW()-INTERVAL '7 days', NOW(), 'org_sebi'),
    ('ec-src-sebi-4', 'Telegram: Research Reports',     '@research_reports_daily', 'telegram', 13.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb, NOW()-INTERVAL '7 days', NOW(), 'org_sebi'),
    ('ec-src-sebi-5', 'Fake Research Portal',           'https://fakeresearch.example.com', 'web', 8.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb, NOW()-INTERVAL '7 days', NOW(), 'org_sebi')
ON CONFLICT (id) DO NOTHING;

-- NCB sources (4)
INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, labels, created_at, updated_at, org_id)
VALUES
    ('ec-src-ncb-1', 'Telegram: Stuff BLR',          '@stuff_blr',           'telegram', 10.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '7 days', NOW(), 'org_ncb'),
    ('ec-src-ncb-2', 'Telegram: 420 Club India',     '@420_club_india',      'telegram', 8.0,  true,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '7 days', NOW(), 'org_ncb'),
    ('ec-src-ncb-3', 'Telegram: Green Life BLR',     '@green_life_blr',      'telegram', 12.0, true,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '7 days', NOW(), 'org_ncb'),
    ('ec-src-ncb-4', 'Dark Web: India Market',       'http://indiamarket.onion', 'web', 5.0,  true,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '7 days', NOW(), 'org_ncb')
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 5. ORG_SOURCES + TOPIC_SOURCES linkage
-- =============================================================================

-- org_sources
INSERT INTO org_sources (org_id, source_id) VALUES
    ('org_mea', 'ec-src-mea-1'), ('org_mea', 'ec-src-mea-2'), ('org_mea', 'ec-src-mea-3'),
    ('org_mea', 'ec-src-mea-4'), ('org_mea', 'ec-src-mea-5'),
    ('org_cyber', 'ec-src-cy-1'), ('org_cyber', 'ec-src-cy-2'), ('org_cyber', 'ec-src-cy-3'),
    ('org_cyber', 'ec-src-cy-4'), ('org_cyber', 'ec-src-cy-5'), ('org_cyber', 'ec-src-cy-6'),
    ('org_sebi', 'ec-src-sebi-1'), ('org_sebi', 'ec-src-sebi-2'), ('org_sebi', 'ec-src-sebi-3'),
    ('org_sebi', 'ec-src-sebi-4'), ('org_sebi', 'ec-src-sebi-5'),
    ('org_ncb', 'ec-src-ncb-1'), ('org_ncb', 'ec-src-ncb-2'),
    ('org_ncb', 'ec-src-ncb-3'), ('org_ncb', 'ec-src-ncb-4')
ON CONFLICT DO NOTHING;

-- topic_sources
INSERT INTO topic_sources (topic_id, source_id, added_at) VALUES
    ('ec-topic-mea', 'ec-src-mea-1', NOW()), ('ec-topic-mea', 'ec-src-mea-2', NOW()),
    ('ec-topic-mea', 'ec-src-mea-3', NOW()), ('ec-topic-mea', 'ec-src-mea-4', NOW()),
    ('ec-topic-mea', 'ec-src-mea-5', NOW()),
    ('ec-topic-cyber', 'ec-src-cy-1', NOW()), ('ec-topic-cyber', 'ec-src-cy-2', NOW()),
    ('ec-topic-cyber', 'ec-src-cy-3', NOW()), ('ec-topic-cyber', 'ec-src-cy-4', NOW()),
    ('ec-topic-cyber', 'ec-src-cy-5', NOW()), ('ec-topic-cyber', 'ec-src-cy-6', NOW()),
    ('ec-topic-sebi', 'ec-src-sebi-1', NOW()), ('ec-topic-sebi', 'ec-src-sebi-2', NOW()),
    ('ec-topic-sebi', 'ec-src-sebi-3', NOW()), ('ec-topic-sebi', 'ec-src-sebi-4', NOW()),
    ('ec-topic-sebi', 'ec-src-sebi-5', NOW()),
    ('ec-topic-ncb', 'ec-src-ncb-1', NOW()), ('ec-topic-ncb', 'ec-src-ncb-2', NOW()),
    ('ec-topic-ncb', 'ec-src-ncb-3', NOW()), ('ec-topic-ncb', 'ec-src-ncb-4', NOW())
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 6. TOPIC_TEMPLATES (link built-in templates to topics)
-- =============================================================================

INSERT INTO topic_templates (topic_id, template_id) VALUES
    -- Cyber: mule, maas, investment fraud, digital arrest
    ('ec-topic-cyber', 'tpl-mule-recruitment'),
    ('ec-topic-cyber', 'tpl-maas'),
    ('ec-topic-cyber', 'tpl-investment-fraud'),
    ('ec-topic-cyber', 'tpl-digital-arrest'),
    -- SEBI: pump-and-dump, fake research
    ('ec-topic-sebi', 'tpl-pump-and-dump'),
    ('ec-topic-sebi', 'tpl-fake-research-report'),
    -- NCB: drug sale, delivery recruitment, mule (shared infra), crypto cashout
    ('ec-topic-ncb', 'tpl-drug-sale'),
    ('ec-topic-ncb', 'tpl-drug-delivery-recruitment'),
    ('ec-topic-ncb', 'tpl-mule-recruitment'),
    ('ec-topic-ncb', 'tpl-crypto-cashout')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 7. NARRATIVE CLUSTERS (insert before content_items for FK)
-- =============================================================================

INSERT INTO narrative_clusters (id, topic_id, label, item_count, independent_source_count, embedding_centroid, labels, created_at, updated_at)
VALUES
    -- MEA: 2 narrative clusters
    ('ec-nc-mea-1', 'ec-topic-mea',
     'Arunachal = South Tibet territorial narrative', 4, 3, NULL,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea","topic_id":"ec-topic-mea"}'::jsonb,
     NOW()-INTERVAL '10 days', NOW()),
    ('ec-nc-mea-2', 'ec-topic-mea',
     'India road building near LAC provocation narrative', 3, 3, NULL,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea","topic_id":"ec-topic-mea"}'::jsonb,
     NOW()-INTERVAL '8 days', NOW()),
    -- Cyber: mule recruitment cluster
    ('ec-nc-cyber-1', 'ec-topic-cyber',
     'Mule account recruitment network via Telegram', 8, 4, NULL,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","topic_id":"ec-topic-cyber"}'::jsonb,
     NOW()-INTERVAL '7 days', NOW()),
    -- SEBI: pump-and-dump cluster
    ('ec-nc-sebi-1', 'ec-topic-sebi',
     'Coordinated XYZLTD stock promotion across channels', 10, 4, NULL,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi","topic_id":"ec-topic-sebi"}'::jsonb,
     NOW()-INTERVAL '5 days', NOW()),
    -- NCB: drug network cluster
    ('ec-nc-ncb-1', 'ec-topic-ncb',
     'Bangalore drug delivery network via Telegram', 6, 3, NULL,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","topic_id":"ec-topic-ncb"}'::jsonb,
     NOW()-INTERVAL '5 days', NOW())
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 8. CONTENT ITEMS
-- =============================================================================

-- -------------------------------------------------------------------------
-- MEA content (8 items)
-- -------------------------------------------------------------------------

INSERT INTO content_items (
    id, topic_id, source_id, url, raw_text, clean_text, content_hash,
    language, captured_at, credibility_score_at_capture, labels,
    created_at, updated_at, narrative_cluster_id, org_id
) VALUES
    -- Cluster 1: "Arunachal = South Tibet" narrative (4 items, 3 sources)
    ('ec-ci-mea-01', 'ec-topic-mea', 'ec-src-mea-1',
     'https://www.globaltimes.cn/page/202606/1330001.shtml',
     'Zangnan (South Tibet) has been part of China since ancient times. India''s so-called Arunachal Pradesh is illegal occupation of Chinese territory. Beijing urges New Delhi to respect historical facts.',
     'Zangnan (South Tibet) has been part of China since ancient times. India so-called Arunachal Pradesh is illegal occupation of Chinese territory. Beijing urges New Delhi to respect historical facts.',
     'ec01mea01hash0000000000000000000000000000000000000000000000000001',
     'en', NOW()-INTERVAL '12 days', 35.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb,
     NOW()-INTERVAL '12 days', NOW()-INTERVAL '12 days', 'ec-nc-mea-1', 'org_mea'),

    ('ec-ci-mea-02', 'ec-topic-mea', 'ec-src-mea-2',
     'https://www.cgtn.com/news/2026-06-01/india-arunachal-south-tibet.html',
     'CGTN report: India deploys additional troops to so-called Arunachal Pradesh, which China considers part of South Tibet. The move violates the spirit of border agreements.',
     'India deploys additional troops to so-called Arunachal Pradesh, which China considers part of South Tibet. The move violates the spirit of border agreements.',
     'ec01mea02hash0000000000000000000000000000000000000000000000000002',
     'en', NOW()-INTERVAL '11 days', 40.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb,
     NOW()-INTERVAL '11 days', NOW()-INTERVAL '11 days', 'ec-nc-mea-1', 'org_mea'),

    ('ec-ci-mea-03', 'ec-topic-mea', 'ec-src-mea-3',
     'https://www.xinhuanet.com/english/202606/zangnan-historical-claim.htm',
     'Xinhua commentary: Historical records confirm Zangnan is integral part of Tibet Autonomous Region. Recent Indian construction activities near the LAC are provocative.',
     'Historical records confirm Zangnan is integral part of Tibet Autonomous Region. Recent Indian construction activities near the LAC are provocative.',
     'ec01mea03hash0000000000000000000000000000000000000000000000000003',
     'en', NOW()-INTERVAL '10 days', 38.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb,
     NOW()-INTERVAL '10 days', NOW()-INTERVAL '10 days', 'ec-nc-mea-1', 'org_mea'),

    ('ec-ci-mea-04', 'ec-topic-mea', 'ec-src-mea-1',
     'https://www.globaltimes.cn/page/202606/1330015.shtml',
     'Expert commentary: India must accept that Zangnan (South Tibet) is Chinese sovereign territory. Any infrastructure construction in the disputed area undermines bilateral relations.',
     'India must accept that Zangnan (South Tibet) is Chinese sovereign territory. Any infrastructure construction in the disputed area undermines bilateral relations.',
     'ec01mea04hash0000000000000000000000000000000000000000000000000004',
     'en', NOW()-INTERVAL '9 days', 35.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb,
     NOW()-INTERVAL '9 days', NOW()-INTERVAL '9 days', 'ec-nc-mea-1', 'org_mea'),

    -- Cluster 2: "India road building provocation" narrative (3 items, 3 sources)
    ('ec-ci-mea-05', 'ec-topic-mea', 'ec-src-mea-4',
     'https://en.people.cn/202606/lac-road-construction-provocation.html',
     'India road construction near LAC is provocative action destabilizing border situation. Beijing has lodged formal protests through diplomatic channels.',
     'India road construction near LAC is provocative action destabilizing border situation. Beijing has lodged formal protests through diplomatic channels.',
     'ec01mea05hash0000000000000000000000000000000000000000000000000005',
     'en', NOW()-INTERVAL '8 days', 36.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb,
     NOW()-INTERVAL '8 days', NOW()-INTERVAL '8 days', 'ec-nc-mea-2', 'org_mea'),

    ('ec-ci-mea-06', 'ec-topic-mea', 'ec-src-mea-5',
     'https://eng.chinamil.com.cn/OPINIONS/202606/lac-strategic-road.htm',
     'PLA analysis: India strategic road near LAC designed to support forward military deployment. Modi government escalating border tensions for domestic political gain.',
     'India strategic road near LAC designed to support forward military deployment. Modi government escalating border tensions for domestic political gain.',
     'ec01mea06hash0000000000000000000000000000000000000000000000000006',
     'en', NOW()-INTERVAL '7 days', 30.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb,
     NOW()-INTERVAL '7 days', NOW()-INTERVAL '7 days', 'ec-nc-mea-2', 'org_mea'),

    ('ec-ci-mea-07', 'ec-topic-mea', 'ec-src-mea-2',
     'https://www.cgtn.com/news/2026-06-04/lac-road-military-purpose.html',
     'CGTN exclusive: Satellite imagery shows India constructing military-grade road within 5km of LAC in Ladakh sector. Road connects to forward staging areas.',
     'Satellite imagery shows India constructing military-grade road within 5km of LAC in Ladakh sector. Road connects to forward staging areas.',
     'ec01mea07hash0000000000000000000000000000000000000000000000000007',
     'en', NOW()-INTERVAL '6 days', 40.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb,
     NOW()-INTERVAL '6 days', NOW()-INTERVAL '6 days', 'ec-nc-mea-2', 'org_mea'),

    -- Chinese-language article (for multilingual demo)
    ('ec-ci-mea-08', 'ec-topic-mea', 'ec-src-mea-3',
     'https://www.xinhuanet.com/2026-06/05/c_1130001.htm',
     '新华社评论：印度在藏南地区的非法建设活动严重侵犯中国主权。中方将采取必要措施维护领土完整。',
     '新华社评论：印度在藏南地区的非法建设活动严重侵犯中国主权。中方将采取必要措施维护领土完整。',
     'ec01mea08hash0000000000000000000000000000000000000000000000000008',
     'zh', NOW()-INTERVAL '5 days', 38.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea"}'::jsonb,
     NOW()-INTERVAL '5 days', NOW()-INTERVAL '5 days', NULL, 'org_mea')
ON CONFLICT (content_hash) DO NOTHING;

-- -------------------------------------------------------------------------
-- Cyber Fraud content (10 items, with identifiers + scam_template labels)
-- -------------------------------------------------------------------------

INSERT INTO content_items (
    id, topic_id, source_id, url, raw_text, clean_text, content_hash,
    language, captured_at, credibility_score_at_capture, labels,
    created_at, updated_at, narrative_cluster_id, org_id
) VALUES
    -- Mule recruitment (4 items, phone +91-9876543210 appears in 3 sources)
    ('ec-ci-cy-01', 'ec-topic-cyber', 'ec-src-cy-1', NULL,
     'EARN ₹5000 PER TRANSACTION! Rent your bank account for easy money. No risk, daily income. Contact: +91-9876543210 or DM @account_service. UPI: service123@paytm',
     'Earn 5000 per transaction. Rent your bank account for easy money. No risk daily income. Contact +91-9876543210 or DM @account_service. UPI service123@paytm',
     'ec01cy01hash00000000000000000000000000000000000000000000000000c001',
     'en', NOW()-INTERVAL '8 days', 15.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","scam_template":"mule_recruitment","template_confidence":0.92}'::jsonb,
     NOW()-INTERVAL '8 days', NOW()-INTERVAL '8 days', 'ec-nc-cyber-1', 'org_cyber'),

    ('ec-ci-cy-02', 'ec-topic-cyber', 'ec-src-cy-2', NULL,
     'Bank account for sale! Commission ₹3000-5000 per transaction. WhatsApp: +91-9876543210. Account service 24/7. UPI: service123@paytm. No questions asked.',
     'Bank account for sale. Commission 3000-5000 per transaction. WhatsApp +91-9876543210. Account service 24/7. UPI service123@paytm. No questions asked.',
     'ec01cy02hash00000000000000000000000000000000000000000000000000c002',
     'en', NOW()-INTERVAL '7 days', 12.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","scam_template":"mule_recruitment","template_confidence":0.88}'::jsonb,
     NOW()-INTERVAL '7 days', NOW()-INTERVAL '7 days', 'ec-nc-cyber-1', 'org_cyber'),

    ('ec-ci-cy-03', 'ec-topic-cyber', 'ec-src-cy-3', NULL,
     'Passive income opportunity! Lend your bank account, earn daily. Call +91-9876543210 for details. Telegram: @account_service. Easy money guaranteed.',
     'Passive income opportunity. Lend your bank account earn daily. Call +91-9876543210 for details. Telegram @account_service. Easy money guaranteed.',
     'ec01cy03hash00000000000000000000000000000000000000000000000000c003',
     'en', NOW()-INTERVAL '6 days', 18.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","scam_template":"mule_recruitment","template_confidence":0.85}'::jsonb,
     NOW()-INTERVAL '6 days', NOW()-INTERVAL '6 days', 'ec-nc-cyber-1', 'org_cyber'),

    ('ec-ci-cy-04', 'ec-topic-cyber', 'ec-src-cy-1', NULL,
     'Urgent: Need 10 bank accounts immediately. ₹8000 per account per month. DM @account_service or call +91-9876543210. GSTIN: 29AABCU9603R1ZM (verified company).',
     'Need 10 bank accounts immediately. 8000 per account per month. DM @account_service or call +91-9876543210. GSTIN 29AABCU9603R1ZM verified company.',
     'ec01cy04hash00000000000000000000000000000000000000000000000000c004',
     'en', NOW()-INTERVAL '5 days', 15.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","scam_template":"mule_recruitment","template_confidence":0.90}'::jsonb,
     NOW()-INTERVAL '5 days', NOW()-INTERVAL '5 days', 'ec-nc-cyber-1', 'org_cyber'),

    -- Investment fraud (4 items, phone +91-8765432109 in 2 sources)
    ('ec-ci-cy-05', 'ec-topic-cyber', 'ec-src-cy-4', NULL,
     'GUARANTEED 5% DAILY RETURNS! Invest now in our AI trading platform. Zero risk. Call +91-8765432109. Visit https://fakeinvestment.example.com. Minimum ₹10,000.',
     'Guaranteed 5 percent daily returns. Invest now in AI trading platform. Zero risk. Call +91-8765432109. Visit https://fakeinvestment.example.com. Minimum 10000.',
     'ec01cy05hash00000000000000000000000000000000000000000000000000c005',
     'en', NOW()-INTERVAL '7 days', 20.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","scam_template":"investment_fraud","template_confidence":0.87}'::jsonb,
     NOW()-INTERVAL '7 days', NOW()-INTERVAL '7 days', NULL, 'org_cyber'),

    ('ec-ci-cy-06', 'ec-topic-cyber', 'ec-src-cy-5', NULL,
     'Double your investment in 30 days! Our platform has 99% accuracy. Call +91-8765432109. WhatsApp for VIP access. No risk, guaranteed returns.',
     'Double your investment in 30 days. Platform has 99 percent accuracy. Call +91-8765432109. WhatsApp for VIP access. No risk guaranteed returns.',
     'ec01cy06hash00000000000000000000000000000000000000000000000000c006',
     'en', NOW()-INTERVAL '6 days', 16.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","scam_template":"investment_fraud","template_confidence":0.82}'::jsonb,
     NOW()-INTERVAL '6 days', NOW()-INTERVAL '6 days', NULL, 'org_cyber'),

    ('ec-ci-cy-07', 'ec-topic-cyber', 'ec-src-cy-4', NULL,
     'High returns investment opportunity. Monthly 15% guaranteed. Risk free. Visit https://fakeinvestment.example.com for details. Limited slots.',
     'High returns investment opportunity. Monthly 15 percent guaranteed. Risk free. Visit https://fakeinvestment.example.com for details. Limited slots.',
     'ec01cy07hash00000000000000000000000000000000000000000000000000c007',
     'en', NOW()-INTERVAL '5 days', 20.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","scam_template":"investment_fraud","template_confidence":0.78}'::jsonb,
     NOW()-INTERVAL '5 days', NOW()-INTERVAL '5 days', NULL, 'org_cyber'),

    ('ec-ci-cy-08', 'ec-topic-cyber', 'ec-src-cy-6',
     'https://fakeinvestment.example.com/testimonials',
     'Join 10,000+ investors earning daily income. Our AI-powered trading bot delivers 5% daily. Deposit via UPI: invest@ybl. 100% safe.',
     'Join 10000 investors earning daily income. AI-powered trading bot delivers 5 percent daily. Deposit via UPI invest@ybl. 100 percent safe.',
     'ec01cy08hash00000000000000000000000000000000000000000000000000c008',
     'en', NOW()-INTERVAL '4 days', 10.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","scam_template":"investment_fraud","template_confidence":0.91}'::jsonb,
     NOW()-INTERVAL '4 days', NOW()-INTERVAL '4 days', NULL, 'org_cyber'),

    -- MaaS (2 items)
    ('ec-ci-cy-09', 'ec-topic-cyber', 'ec-src-cy-2', NULL,
     'BULK ACCOUNTS AVAILABLE! Fresh verified accounts with KYC done. Ready to use. ₹15000 per account. Contact +91-7654321098. Wholesale discount for 10+.',
     'Bulk accounts available. Fresh verified accounts with KYC done. Ready to use. 15000 per account. Contact +91-7654321098. Wholesale discount for 10 plus.',
     'ec01cy09hash00000000000000000000000000000000000000000000000000c009',
     'en', NOW()-INTERVAL '4 days', 12.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","scam_template":"maas","template_confidence":0.80}'::jsonb,
     NOW()-INTERVAL '4 days', NOW()-INTERVAL '4 days', 'ec-nc-cyber-1', 'org_cyber'),

    ('ec-ci-cy-10', 'ec-topic-cyber', 'ec-src-cy-3', NULL,
     'Account supply service. Clean accounts ready for cash out. Bulk orders accepted. Call +91-7654321098 or DM @account_service.',
     'Account supply service. Clean accounts ready for cash out. Bulk orders accepted. Call +91-7654321098 or DM @account_service.',
     'ec01cy10hash00000000000000000000000000000000000000000000000000c010',
     'en', NOW()-INTERVAL '3 days', 18.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","scam_template":"maas","template_confidence":0.75}'::jsonb,
     NOW()-INTERVAL '3 days', NOW()-INTERVAL '3 days', 'ec-nc-cyber-1', 'org_cyber')
ON CONFLICT (content_hash) DO NOTHING;

-- -------------------------------------------------------------------------
-- SEBI content (8 items)
-- -------------------------------------------------------------------------

INSERT INTO content_items (
    id, topic_id, source_id, url, raw_text, clean_text, content_hash,
    language, captured_at, credibility_score_at_capture, labels,
    created_at, updated_at, narrative_cluster_id, org_id
) VALUES
    -- Pump-and-dump: XYZLTD stock (6 items, @stockguru_india in 3 sources)
    ('ec-ci-sebi-01', 'ec-topic-sebi', 'ec-src-sebi-1', NULL,
     'XYZLTD next multibagger! Buy before ₹500. Target price ₹2000. Insider tip from @stockguru_india. Call +91-9998877665 for premium tips. UPI: premiumtips@paytm for VIP access ₹999.',
     'XYZLTD next multibagger. Buy before 500. Target price 2000. Insider tip from @stockguru_india. Call +91-9998877665 for premium tips. UPI premiumtips@paytm for VIP access 999.',
     'ec01sebi01hash000000000000000000000000000000000000000000000000s001',
     'en', NOW()-INTERVAL '6 days', 14.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi","scam_template":"pump_and_dump","template_confidence":0.93}'::jsonb,
     NOW()-INTERVAL '6 days', NOW()-INTERVAL '6 days', 'ec-nc-sebi-1', 'org_sebi'),

    ('ec-ci-sebi-02', 'ec-topic-sebi', 'ec-src-sebi-2', NULL,
     'XYZLTD breaking out! Small cap gem confirmed by @stockguru_india. 100% guaranteed profit. Buy now or regret later. Operator stock.',
     'XYZLTD breaking out. Small cap gem confirmed by @stockguru_india. 100 percent guaranteed profit. Buy now or regret later. Operator stock.',
     'ec01sebi02hash000000000000000000000000000000000000000000000000s002',
     'en', NOW()-INTERVAL '5 days', 11.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi","scam_template":"pump_and_dump","template_confidence":0.89}'::jsonb,
     NOW()-INTERVAL '5 days', NOW()-INTERVAL '5 days', 'ec-nc-sebi-1', 'org_sebi'),

    ('ec-ci-sebi-03', 'ec-topic-sebi', 'ec-src-sebi-3', NULL,
     'Urgent: XYZLTD will hit circuit tomorrow. @stockguru_india premium pick. Free tips available. Call +91-9998877665.',
     'XYZLTD will hit circuit tomorrow. @stockguru_india premium pick. Free tips available. Call +91-9998877665.',
     'ec01sebi03hash000000000000000000000000000000000000000000000000s003',
     'en', NOW()-INTERVAL '4 days', 16.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi","scam_template":"pump_and_dump","template_confidence":0.86}'::jsonb,
     NOW()-INTERVAL '4 days', NOW()-INTERVAL '4 days', 'ec-nc-sebi-1', 'org_sebi'),

    ('ec-ci-sebi-04', 'ec-topic-sebi', 'ec-src-sebi-1', NULL,
     'XYZLTD crossed ₹300! Next target ₹500 as predicted by @stockguru_india. Buy more on dips. SEBI registered analyst INZ000123456789.',
     'XYZLTD crossed 300. Next target 500 as predicted by @stockguru_india. Buy more on dips. SEBI registered analyst INZ000123456789.',
     'ec01sebi04hash000000000000000000000000000000000000000000000000s004',
     'en', NOW()-INTERVAL '3 days', 14.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi","scam_template":"pump_and_dump","template_confidence":0.91}'::jsonb,
     NOW()-INTERVAL '3 days', NOW()-INTERVAL '3 days', 'ec-nc-sebi-1', 'org_sebi'),

    -- Fake research reports (2 items)
    ('ec-ci-sebi-05', 'ec-topic-sebi', 'ec-src-sebi-4', NULL,
     'LEAKED: Confidential research report on XYZLTD. Strong buy rating. Price target ₹500. Download: https://fakeresearch.example.com/reports/xyz.pdf. Institutional pick.',
     'Confidential research report on XYZLTD. Strong buy rating. Price target 500. Download https://fakeresearch.example.com/reports/xyz.pdf. Institutional pick.',
     'ec01sebi05hash000000000000000000000000000000000000000000000000s005',
     'en', NOW()-INTERVAL '4 days', 13.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi","scam_template":"fake_research_report","template_confidence":0.84}'::jsonb,
     NOW()-INTERVAL '4 days', NOW()-INTERVAL '4 days', NULL, 'org_sebi'),

    ('ec-ci-sebi-06', 'ec-topic-sebi', 'ec-src-sebi-5',
     'https://fakeresearch.example.com/reports/xyz.pdf',
     'XYZLTD Equity Research — BUY. CMP ₹280, Target ₹500. Analyst recommendation by SEBI registered research analyst INZ000123456789. Fundamental analysis shows 80% upside.',
     'XYZLTD Equity Research BUY. CMP 280 Target 500. Analyst recommendation by SEBI registered research analyst INZ000123456789. Fundamental analysis shows 80 percent upside.',
     'ec01sebi06hash000000000000000000000000000000000000000000000000s006',
     'en', NOW()-INTERVAL '3 days', 8.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi","scam_template":"fake_research_report","template_confidence":0.88}'::jsonb,
     NOW()-INTERVAL '3 days', NOW()-INTERVAL '3 days', NULL, 'org_sebi'),

    -- Control: generic stock tip (no template match)
    ('ec-ci-sebi-07', 'ec-topic-sebi', 'ec-src-sebi-3', NULL,
     'Market update: Nifty closed at 25,430. Banking sector strong. IT sector weak on US recession fears. HDFC, ICICI performing well.',
     'Market update Nifty closed at 25430. Banking sector strong. IT sector weak on US recession fears. HDFC ICICI performing well.',
     'ec01sebi07hash000000000000000000000000000000000000000000000000s007',
     'en', NOW()-INTERVAL '2 days', 16.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb,
     NOW()-INTERVAL '2 days', NOW()-INTERVAL '2 days', NULL, 'org_sebi'),

    ('ec-ci-sebi-08', 'ec-topic-sebi', 'ec-src-sebi-2', NULL,
     'Quarterly results: Top 5 small caps to watch. Diversify your portfolio across sectors. Standard investment advice from trading community.',
     'Quarterly results top 5 small caps to watch. Diversify your portfolio across sectors. Standard investment advice from trading community.',
     'ec01sebi08hash000000000000000000000000000000000000000000000000s008',
     'en', NOW()-INTERVAL '1 day', 11.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb,
     NOW()-INTERVAL '1 day', NOW()-INTERVAL '1 day', NULL, 'org_sebi')
ON CONFLICT (content_hash) DO NOTHING;

-- -------------------------------------------------------------------------
-- NCB content (8 items)
-- -------------------------------------------------------------------------

INSERT INTO content_items (
    id, topic_id, source_id, url, raw_text, clean_text, content_hash,
    language, captured_at, credibility_score_at_capture, labels,
    created_at, updated_at, narrative_cluster_id, org_id
) VALUES
    -- Drug sale (4 items, phone +91-9753186420 in 3 channels, BTC wallet in 2)
    ('ec-ci-ncb-01', 'ec-topic-ncb', 'ec-src-ncb-1', NULL,
     'Stuff available Bangalore 🍃. Best quality product. Delivery within 2 hours. DM @stuff_blr or call +91-9753186420. UPI: dealer420@paytm. Discreet packaging.',
     'Stuff available Bangalore. Best quality product. Delivery within 2 hours. DM @stuff_blr or call +91-9753186420. UPI dealer420@paytm. Discreet packaging.',
     'ec01ncb01hash000000000000000000000000000000000000000000000000n001',
     'en', NOW()-INTERVAL '6 days', 10.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","scam_template":"drug_sale","template_confidence":0.90}'::jsonb,
     NOW()-INTERVAL '6 days', NOW()-INTERVAL '6 days', 'ec-nc-ncb-1', 'org_ncb'),

    ('ec-ci-ncb-02', 'ec-topic-ncb', 'ec-src-ncb-2', NULL,
     '420 stuff ready for delivery Bangalore 🔥. Premium and regular available. Call +91-9753186420. BTC accepted: bc1qr8fakew4ll3taddr3ssm4n0000000000000000. Sample available.',
     '420 stuff ready for delivery Bangalore. Premium and regular available. Call +91-9753186420. BTC accepted bc1qr8fakew4ll3taddr3ssm4n0000000000000000. Sample available.',
     'ec01ncb02hash000000000000000000000000000000000000000000000000n002',
     'en', NOW()-INTERVAL '5 days', 8.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","scam_template":"drug_sale","template_confidence":0.87}'::jsonb,
     NOW()-INTERVAL '5 days', NOW()-INTERVAL '5 days', 'ec-nc-ncb-1', 'org_ncb'),

    ('ec-ci-ncb-03', 'ec-topic-ncb', 'ec-src-ncb-3', NULL,
     'Green life Bangalore delivery service. Bulk order discount. Contact +91-9753186420 or DM @stuff_blr admin. Delivery Koramangala, HSR, Whitefield.',
     'Green life Bangalore delivery service. Bulk order discount. Contact +91-9753186420 or DM @stuff_blr admin. Delivery Koramangala HSR Whitefield.',
     'ec01ncb03hash000000000000000000000000000000000000000000000000n003',
     'en', NOW()-INTERVAL '4 days', 12.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","scam_template":"drug_sale","template_confidence":0.85}'::jsonb,
     NOW()-INTERVAL '4 days', NOW()-INTERVAL '4 days', 'ec-nc-ncb-1', 'org_ncb'),

    ('ec-ci-ncb-04', 'ec-topic-ncb', 'ec-src-ncb-1', NULL,
     'Menu update: New stock arrived. Quality guaranteed. DM for price list. UPI: dealer420@paytm. Escrow for new customers. @stuff_blr verified.',
     'Menu update new stock arrived. Quality guaranteed. DM for price list. UPI dealer420@paytm. Escrow for new customers. @stuff_blr verified.',
     'ec01ncb04hash000000000000000000000000000000000000000000000000n004',
     'en', NOW()-INTERVAL '3 days', 10.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","scam_template":"drug_sale","template_confidence":0.82}'::jsonb,
     NOW()-INTERVAL '3 days', NOW()-INTERVAL '3 days', 'ec-nc-ncb-1', 'org_ncb'),

    -- Dark web listings (2 items, same BTC wallet links to Telegram)
    ('ec-ci-ncb-05', 'ec-topic-ncb', 'ec-src-ncb-4',
     'http://indiamarket.onion/listings/blr-420',
     'India shipping. Quality guaranteed. Escrow accepted. BTC: bc1qr8fakew4ll3taddr3ssm4n0000000000000000. Bangalore local delivery 2h. All India shipping 3-5 days.',
     'India shipping. Quality guaranteed. Escrow accepted. BTC bc1qr8fakew4ll3taddr3ssm4n0000000000000000. Bangalore local delivery 2h. All India shipping 3-5 days.',
     'ec01ncb05hash000000000000000000000000000000000000000000000000n005',
     'en', NOW()-INTERVAL '5 days', 5.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","scam_template":"drug_sale","template_confidence":0.78}'::jsonb,
     NOW()-INTERVAL '5 days', NOW()-INTERVAL '5 days', NULL, 'org_ncb'),

    ('ec-ci-ncb-06', 'ec-topic-ncb', 'ec-src-ncb-4',
     'http://indiamarket.onion/listings/blr-premium',
     'Premium product available. Verified vendor. 100+ successful orders. BTC only: bc1qr8fakew4ll3taddr3ssm4n0000000000000000. India domestic shipping.',
     'Premium product available. Verified vendor. 100 plus successful orders. BTC only bc1qr8fakew4ll3taddr3ssm4n0000000000000000. India domestic shipping.',
     'ec01ncb06hash000000000000000000000000000000000000000000000000n006',
     'en', NOW()-INTERVAL '4 days', 5.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","scam_template":"drug_sale","template_confidence":0.75}'::jsonb,
     NOW()-INTERVAL '4 days', NOW()-INTERVAL '4 days', NULL, 'org_ncb'),

    -- Mule recruitment (shared infra with cyber fraud, 2 items)
    ('ec-ci-ncb-07', 'ec-topic-ncb', 'ec-src-ncb-2', NULL,
     'Bank account needed for commission work. Easy money ₹5000 daily. No risk. Call +91-8642097531. Account for sale welcome.',
     'Bank account needed for commission work. Easy money 5000 daily. No risk. Call +91-8642097531. Account for sale welcome.',
     'ec01ncb07hash000000000000000000000000000000000000000000000000n007',
     'en', NOW()-INTERVAL '3 days', 8.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","scam_template":"mule_recruitment","template_confidence":0.72}'::jsonb,
     NOW()-INTERVAL '3 days', NOW()-INTERVAL '3 days', NULL, 'org_ncb'),

    ('ec-ci-ncb-08', 'ec-topic-ncb', 'ec-src-ncb-3', NULL,
     'Earn daily income. Lend your bank account for commission. Call +91-8642097531 for details. Passive income guaranteed.',
     'Earn daily income. Lend your bank account for commission. Call +91-8642097531 for details. Passive income guaranteed.',
     'ec01ncb08hash000000000000000000000000000000000000000000000000n008',
     'en', NOW()-INTERVAL '2 days', 12.0,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","scam_template":"mule_recruitment","template_confidence":0.68}'::jsonb,
     NOW()-INTERVAL '2 days', NOW()-INTERVAL '2 days', NULL, 'org_ncb')
ON CONFLICT (content_hash) DO NOTHING;

-- =============================================================================
-- 9. IDENTIFIER CLUSTERS (pre-seeded for demo reliability)
-- =============================================================================

INSERT INTO identifier_clusters (
    id, topic_id, identifier_type, identifier_value,
    source_count, content_item_count, first_seen_at, last_seen_at,
    created_at, updated_at, labels
) VALUES
    -- Cyber: mule phone cluster (3 sources)
    ('ec-ic-cy-phone', 'ec-topic-cyber', 'PHONE_IN', '9876543210',
     3, 4, NOW()-INTERVAL '8 days', NOW()-INTERVAL '5 days',
     NOW()-INTERVAL '8 days', NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),

    -- Cyber: UPI cluster (2 sources)
    ('ec-ic-cy-upi', 'ec-topic-cyber', 'UPI', 'service123@paytm',
     2, 2, NOW()-INTERVAL '8 days', NOW()-INTERVAL '7 days',
     NOW()-INTERVAL '8 days', NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),

    -- Cyber: Telegram handle cluster (3 sources)
    ('ec-ic-cy-tg', 'ec-topic-cyber', 'TELEGRAM_HANDLE', 'account_service',
     3, 4, NOW()-INTERVAL '8 days', NOW()-INTERVAL '3 days',
     NOW()-INTERVAL '8 days', NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),

    -- SEBI: finfluencer handle cluster (3 sources)
    ('ec-ic-sebi-tg', 'ec-topic-sebi', 'TELEGRAM_HANDLE', 'stockguru_india',
     3, 4, NOW()-INTERVAL '6 days', NOW()-INTERVAL '3 days',
     NOW()-INTERVAL '6 days', NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb),

    -- SEBI: phone cluster (2 sources)
    ('ec-ic-sebi-phone', 'ec-topic-sebi', 'PHONE_IN', '9998877665',
     2, 2, NOW()-INTERVAL '6 days', NOW()-INTERVAL '4 days',
     NOW()-INTERVAL '6 days', NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi"}'::jsonb),

    -- NCB: dealer phone cluster (3 sources)
    ('ec-ic-ncb-phone', 'ec-topic-ncb', 'PHONE_IN', '9753186420',
     3, 4, NOW()-INTERVAL '6 days', NOW()-INTERVAL '4 days',
     NOW()-INTERVAL '6 days', NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb"}'::jsonb),

    -- NCB: BTC wallet cluster (2 sources — links Telegram to dark web)
    ('ec-ic-ncb-btc', 'ec-topic-ncb', 'CRYPTO_BTC', 'bc1qr8fakew4ll3taddr3ssm4n0000000000000000',
     2, 3, NOW()-INTERVAL '5 days', NOW()-INTERVAL '4 days',
     NOW()-INTERVAL '5 days', NOW(),
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- Cluster items (link content to clusters)
INSERT INTO identifier_cluster_items (identifier_cluster_id, content_item_id, source_id) VALUES
    -- Cyber phone cluster
    ('ec-ic-cy-phone', 'ec-ci-cy-01', 'ec-src-cy-1'),
    ('ec-ic-cy-phone', 'ec-ci-cy-02', 'ec-src-cy-2'),
    ('ec-ic-cy-phone', 'ec-ci-cy-03', 'ec-src-cy-3'),
    ('ec-ic-cy-phone', 'ec-ci-cy-04', 'ec-src-cy-1'),
    -- Cyber UPI cluster
    ('ec-ic-cy-upi', 'ec-ci-cy-01', 'ec-src-cy-1'),
    ('ec-ic-cy-upi', 'ec-ci-cy-02', 'ec-src-cy-2'),
    -- Cyber TG handle cluster
    ('ec-ic-cy-tg', 'ec-ci-cy-01', 'ec-src-cy-1'),
    ('ec-ic-cy-tg', 'ec-ci-cy-02', 'ec-src-cy-2'),
    ('ec-ic-cy-tg', 'ec-ci-cy-03', 'ec-src-cy-3'),
    ('ec-ic-cy-tg', 'ec-ci-cy-04', 'ec-src-cy-1'),
    -- SEBI TG handle cluster
    ('ec-ic-sebi-tg', 'ec-ci-sebi-01', 'ec-src-sebi-1'),
    ('ec-ic-sebi-tg', 'ec-ci-sebi-02', 'ec-src-sebi-2'),
    ('ec-ic-sebi-tg', 'ec-ci-sebi-03', 'ec-src-sebi-3'),
    ('ec-ic-sebi-tg', 'ec-ci-sebi-04', 'ec-src-sebi-1'),
    -- NCB phone cluster
    ('ec-ic-ncb-phone', 'ec-ci-ncb-01', 'ec-src-ncb-1'),
    ('ec-ic-ncb-phone', 'ec-ci-ncb-02', 'ec-src-ncb-2'),
    ('ec-ic-ncb-phone', 'ec-ci-ncb-03', 'ec-src-ncb-3'),
    ('ec-ic-ncb-phone', 'ec-ci-ncb-04', 'ec-src-ncb-1'),
    -- NCB BTC cluster (links TG to dark web)
    ('ec-ic-ncb-btc', 'ec-ci-ncb-02', 'ec-src-ncb-2'),
    ('ec-ic-ncb-btc', 'ec-ci-ncb-05', 'ec-src-ncb-4'),
    ('ec-ic-ncb-btc', 'ec-ci-ncb-06', 'ec-src-ncb-4')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 10. SIGNALS (pre-seeded for demo reliability)
-- =============================================================================

INSERT INTO signals (
    id, topic_id, cluster_id, signal_type,
    description, evidence, status, labels, created_at, updated_at
) VALUES
    -- MEA: multi_source_convergence on "South Tibet" narrative
    ('ec-sig-mea-1', 'ec-topic-mea', 'ec-nc-mea-1', 'multi_source_convergence',
     'Coordinated "Arunachal = South Tibet" narrative detected across 3 Chinese state media outlets',
     '{"cluster_id":"ec-nc-mea-1","independent_source_count":3,"platforms":["web"],"label":"Arunachal = South Tibet territorial narrative"}'::jsonb,
     'new',
     '{"classification":"OPEN","domain":"osint","owner_org":"mea","topic_id":"ec-topic-mea"}'::jsonb,
     NOW()-INTERVAL '9 days', NOW()-INTERVAL '9 days'),

    -- Cyber: identifier_convergence on mule phone
    ('ec-sig-cy-1', 'ec-topic-cyber', 'ec-nc-cyber-1', 'identifier_convergence',
     'Phone +91-9876543210 detected across 3 Telegram channels recruiting mule accounts',
     '{"identifier_cluster_id":"ec-ic-cy-phone","identifier_type":"PHONE_IN","identifier_value":"9876543210","source_count":3,"content_item_count":4}'::jsonb,
     'new',
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","topic_id":"ec-topic-cyber"}'::jsonb,
     NOW()-INTERVAL '6 days', NOW()-INTERVAL '6 days'),

    -- Cyber: scam_template_match on mule recruitment
    ('ec-sig-cy-2', 'ec-topic-cyber', 'ec-nc-cyber-1', 'scam_template_match',
     'CRITICAL: Mule Account Recruitment template matched with 92% confidence across 4 content items',
     '{"template_name":"mule_recruitment","template_display":"Mule Account Recruitment","confidence":0.92,"severity":"CRITICAL","match_count":4,"legal_sections":["PMLA Section 3","PMLA Section 4"]}'::jsonb,
     'new',
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","topic_id":"ec-topic-cyber"}'::jsonb,
     NOW()-INTERVAL '5 days', NOW()-INTERVAL '5 days'),

    -- SEBI: scam_template_match on pump-and-dump
    ('ec-sig-sebi-1', 'ec-topic-sebi', 'ec-nc-sebi-1', 'scam_template_match',
     'CRITICAL: Pump and Dump template matched on XYZLTD stock — coordinated across 4 Telegram channels',
     '{"template_name":"pump_and_dump","template_display":"Pump and Dump","confidence":0.93,"severity":"CRITICAL","match_count":4,"legal_sections":["SEBI (PFUTP) Regulations 2003","SEBI Act Section 12A"]}'::jsonb,
     'new',
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi","topic_id":"ec-topic-sebi"}'::jsonb,
     NOW()-INTERVAL '4 days', NOW()-INTERVAL '4 days'),

    -- SEBI: identifier_convergence on finfluencer handle
    ('ec-sig-sebi-2', 'ec-topic-sebi', 'ec-nc-sebi-1', 'identifier_convergence',
     '@stockguru_india handle detected across 3 channels promoting XYZLTD',
     '{"identifier_cluster_id":"ec-ic-sebi-tg","identifier_type":"TELEGRAM_HANDLE","identifier_value":"stockguru_india","source_count":3,"content_item_count":4}'::jsonb,
     'new',
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi","topic_id":"ec-topic-sebi"}'::jsonb,
     NOW()-INTERVAL '3 days', NOW()-INTERVAL '3 days'),

    -- NCB: identifier_convergence on dealer phone
    ('ec-sig-ncb-1', 'ec-topic-ncb', 'ec-nc-ncb-1', 'identifier_convergence',
     'Phone +91-9753186420 detected across 3 drug delivery channels in Bangalore',
     '{"identifier_cluster_id":"ec-ic-ncb-phone","identifier_type":"PHONE_IN","identifier_value":"9753186420","source_count":3,"content_item_count":4}'::jsonb,
     'new',
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","topic_id":"ec-topic-ncb"}'::jsonb,
     NOW()-INTERVAL '4 days', NOW()-INTERVAL '4 days'),

    -- NCB: scam_template_match on drug sale
    ('ec-sig-ncb-2', 'ec-topic-ncb', 'ec-nc-ncb-1', 'scam_template_match',
     'HIGH: Drug Sale template matched across Telegram channels and dark web listing',
     '{"template_name":"drug_sale","template_display":"Drug Sale","confidence":0.90,"severity":"HIGH","match_count":6,"legal_sections":["NDPS Act Section 20","NDPS Act Section 22","NDPS Act Section 25"]}'::jsonb,
     'new',
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","topic_id":"ec-topic-ncb"}'::jsonb,
     NOW()-INTERVAL '3 days', NOW()-INTERVAL '3 days')
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 11. REPORTS (one per agency, with identifier sections)
-- =============================================================================

INSERT INTO reports (
    id, topic_id, report_type,
    time_window_start, time_window_end, credibility_min_filter,
    content_md, generated_at, source_snapshot, content_item_count,
    labels, created_at, updated_at
) VALUES
    -- MEA report
    ('ec-rpt-mea', 'ec-topic-mea', 'intelligence_brief',
     NOW()-INTERVAL '14 days', NOW(), 20.0,
     E'## Executive Summary\n\nCoordinated anti-India territorial narrative detected across 3 Chinese state media outlets (Global Times, CGTN, Xinhua) over a 12-day period. Two distinct narrative threads identified: (1) "Arunachal = South Tibet" sovereignty claims, and (2) "India road building near LAC" provocation framing.\n\n## Key Findings\n\n- 4 articles across 3 sources push identical "Zangnan/South Tibet" sovereignty claim [Source: globaltimes.cn, cgtn.com, xinhuanet.com]\n- 3 articles frame India LAC road construction as military provocation [Source: people.cn, chinamil.com.cn, cgtn.com]\n- Narrative coordination: consistent terminology ("Zangnan", "so-called Arunachal Pradesh") across outlets\n- Chinese-language article from Xinhua confirms domestic audience messaging alignment\n\n## Recommendations\n\n- Monitor for escalation in frequency of "South Tibet" references\n- Track PLA-affiliated media for military dimension\n- Flag for XP Division strategic communications response\n\n## Identified Indicators\n\n| Type | Value | Sources | Items |\n|------|-------|---------|-------|\n| URL_DOMAIN | globaltimes.cn | 1 | 3 |\n| URL_DOMAIN | cgtn.com | 1 | 2 |\n| URL_DOMAIN | xinhuanet.com | 1 | 2 |\n\n## Source Citations\n\n- https://www.globaltimes.cn\n- https://www.cgtn.com\n- https://www.xinhuanet.com',
     NOW()-INTERVAL '1 day',
     '{"ec-src-mea-1":{"name":"Global Times","credibility_score":35.0},"ec-src-mea-2":{"name":"CGTN","credibility_score":40.0},"ec-src-mea-3":{"name":"Xinhua News","credibility_score":38.0}}'::jsonb,
     8,
     '{"classification":"OPEN","domain":"osint","owner_org":"mea","topic_id":"ec-topic-mea"}'::jsonb,
     NOW()-INTERVAL '1 day', NOW()-INTERVAL '1 day'),

    -- Cyber Fraud report
    ('ec-rpt-cyber', 'ec-topic-cyber', 'intelligence_brief',
     NOW()-INTERVAL '10 days', NOW(), 10.0,
     E'## Executive Summary\n\nActive mule account recruitment network detected operating across 5 Telegram channels. Primary actor uses phone +91-9876543210 and handle @account_service across 3 channels. Parallel investment fraud operation promotes fake platform at fakeinvestment.example.com.\n\n## Key Findings\n\n- Mule recruitment network: 4 messages across 3 channels offering ₹5000-8000/transaction for bank accounts [Source: @easy_money_india, @account_service_247, @vip_earning_group]\n- Same phone +91-9876543210 appears in 3 independent channels — high confidence single actor\n- GSTIN 29AABCU9603R1ZM used as legitimacy facade (likely shell company)\n- Investment fraud: fake platform fakeinvestment.example.com promising 5% daily returns\n- MaaS operation: bulk verified accounts offered at ₹15000 each\n\n## Recommendations\n\n- Freeze identified UPI IDs (service123@paytm) under PMLA Section 17\n- Request CDR for +91-9876543210 and +91-8765432109\n- Block fakeinvestment.example.com via DoT\n\n## Identified Indicators\n\n| Type | Value | Sources | Items |\n|------|-------|---------|-------|\n| PHONE_IN | 9876543210 | 3 | 4 |\n| PHONE_IN | 8765432109 | 2 | 2 |\n| PHONE_IN | 7654321098 | 2 | 2 |\n| UPI | service123@paytm | 2 | 2 |\n| TELEGRAM_HANDLE | account_service | 3 | 4 |\n| GSTIN | 29AABCU9603R1ZM | 1 | 1 |\n| URL_DOMAIN | fakeinvestment.example.com | 2 | 3 |\n\n## Scam Template Matches\n\n**Mule Account Recruitment** — Severity: CRITICAL, Confidence: 92%, Matches: 4\n  Legal provisions: PMLA Section 3, PMLA Section 4\n\n**Investment Fraud** — Severity: CRITICAL, Confidence: 87%, Matches: 4\n  Legal provisions: IPC 420, SEBI (PFUTP) Regulations\n\n**Mule-as-a-Service** — Severity: CRITICAL, Confidence: 80%, Matches: 2\n  Legal provisions: PMLA Section 3, IT Act 66D\n\n## Recommended Actions\n\n- Freeze identified bank accounts and UPI IDs under PMLA Section 17\n- Request CDR for associated phone numbers\n- File STR with FIU-IND\n\n## Source Citations\n\n- @easy_money_india\n- @account_service_247\n- @vip_earning_group\n- @investment_tips_pro\n- https://fakeinvestment.example.com',
     NOW()-INTERVAL '1 day',
     '{"ec-src-cy-1":{"name":"Easy Money India","credibility_score":15.0},"ec-src-cy-2":{"name":"Account Service","credibility_score":12.0},"ec-src-cy-3":{"name":"VIP Earning Group","credibility_score":18.0}}'::jsonb,
     10,
     '{"classification":"OPEN","domain":"osint","owner_org":"cyber","topic_id":"ec-topic-cyber"}'::jsonb,
     NOW()-INTERVAL '1 day', NOW()-INTERVAL '1 day'),

    -- SEBI report
    ('ec-rpt-sebi', 'ec-topic-sebi', 'intelligence_brief',
     NOW()-INTERVAL '7 days', NOW(), 5.0,
     E'## Executive Summary\n\nCoordinated pump-and-dump scheme detected targeting small-cap stock XYZLTD. Single actor @stockguru_india orchestrating promotion across 3 Telegram channels. Fake research report hosted at fakeresearch.example.com uses fraudulent SEBI registration number.\n\n## Key Findings\n\n- XYZLTD promoted as "multibagger" across 4 channels with identical narrative [Source: @stock_tips_free, @penny_stock_vip, @trading_guru_india]\n- @stockguru_india handle appears in 3 channels — coordinated single-actor promotion\n- Fraudulent SEBI registration INZ000123456789 used to claim legitimacy\n- Fake research report at fakeresearch.example.com mimics institutional format\n- Monetization via UPI premiumtips@paytm (₹999 "VIP access")\n\n## Recommendations\n\n- Report XYZLTD manipulation to SEBI surveillance division\n- Block @stockguru_india across platforms\n- Takedown fakeresearch.example.com\n\n## Identified Indicators\n\n| Type | Value | Sources | Items |\n|------|-------|---------|-------|\n| TELEGRAM_HANDLE | stockguru_india | 3 | 4 |\n| PHONE_IN | 9998877665 | 2 | 2 |\n| UPI | premiumtips@paytm | 1 | 1 |\n| SEBI_REG | INZ000123456789 | 2 | 2 |\n| URL_DOMAIN | fakeresearch.example.com | 2 | 2 |\n\n## Scam Template Matches\n\n**Pump and Dump** — Severity: CRITICAL, Confidence: 93%, Matches: 4\n  Legal provisions: SEBI (PFUTP) Regulations 2003, SEBI Act Section 12A\n\n**Fake Research Report** — Severity: HIGH, Confidence: 86%, Matches: 2\n  Legal provisions: SEBI (Research Analysts) Regulations 2014\n\n## Recommended Actions\n\n- Report manipulated securities to SEBI surveillance division\n- Flag identified social media accounts for coordinated promotion\n- Request trading data for identified accounts from exchanges\n\n## Source Citations\n\n- @stock_tips_free\n- @penny_stock_vip\n- @trading_guru_india\n- https://fakeresearch.example.com',
     NOW()-INTERVAL '1 day',
     '{"ec-src-sebi-1":{"name":"Stock Tips Free","credibility_score":14.0},"ec-src-sebi-2":{"name":"Penny Stock VIP","credibility_score":11.0},"ec-src-sebi-3":{"name":"Trading Guru India","credibility_score":16.0}}'::jsonb,
     8,
     '{"classification":"OPEN","domain":"osint","owner_org":"sebi","topic_id":"ec-topic-sebi"}'::jsonb,
     NOW()-INTERVAL '1 day', NOW()-INTERVAL '1 day'),

    -- NCB report
    ('ec-rpt-ncb', 'ec-topic-ncb', 'intelligence_brief',
     NOW()-INTERVAL '7 days', NOW(), 5.0,
     E'## Executive Summary\n\nDrug delivery network operating across 3 Telegram channels and 1 dark web marketplace identified in Bangalore. Primary actor uses phone +91-9753186420 and handle @stuff_blr. BTC wallet bc1qr8fake... links Telegram operations to dark web listings, confirming single network.\n\n## Key Findings\n\n- Dealer phone +91-9753186420 active across 3 Telegram channels [Source: @stuff_blr, @420_club_india, @green_life_blr]\n- BTC wallet bc1qr8fakew4ll3t... appears in both Telegram channels and dark web listings — confirms network linkage\n- Delivery coverage: Koramangala, HSR Layout, Whitefield (Bangalore)\n- UPI dealer420@paytm used for local transactions\n- Mule recruitment messages (2) suggest financial infrastructure overlap\n\n## Recommendations\n\n- Request CDR for +91-9753186420 and +91-8642097531\n- Coordinate with NCB for controlled delivery in Bangalore\n- Trace BTC wallet transactions on blockchain\n\n## Identified Indicators\n\n| Type | Value | Sources | Items |\n|------|-------|---------|-------|\n| PHONE_IN | 9753186420 | 3 | 4 |\n| PHONE_IN | 8642097531 | 2 | 2 |\n| CRYPTO_BTC | bc1qr8fakew4ll3taddr3ssm4n0000000000000000 | 2 | 3 |\n| UPI | dealer420@paytm | 2 | 2 |\n| TELEGRAM_HANDLE | stuff_blr | 3 | 4 |\n\n## Scam Template Matches\n\n**Drug Sale** — Severity: HIGH, Confidence: 90%, Matches: 6\n  Legal provisions: NDPS Act Section 20, NDPS Act Section 22, NDPS Act Section 25\n\n**Mule Account Recruitment** — Severity: CRITICAL, Confidence: 72%, Matches: 2\n  Legal provisions: PMLA Section 3, PMLA Section 4\n\n## Recommended Actions\n\n- Request CDR and IP logs for identified phone numbers and handles\n- Coordinate with NCB for controlled delivery operations\n- File case under NDPS Act Sections 20, 22, 25\n\n## Source Citations\n\n- @stuff_blr\n- @420_club_india\n- @green_life_blr\n- http://indiamarket.onion',
     NOW()-INTERVAL '1 day',
     '{"ec-src-ncb-1":{"name":"Stuff BLR","credibility_score":10.0},"ec-src-ncb-2":{"name":"420 Club India","credibility_score":8.0},"ec-src-ncb-3":{"name":"Green Life BLR","credibility_score":12.0}}'::jsonb,
     8,
     '{"classification":"OPEN","domain":"osint","owner_org":"ncb","topic_id":"ec-topic-ncb"}'::jsonb,
     NOW()-INTERVAL '1 day', NOW()-INTERVAL '1 day')
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- =============================================================================
-- Summary
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Engine C demo seed complete:';
    RAISE NOTICE '  Organizations: 4 (org_mea, org_cyber, org_sebi, org_ncb)';
    RAISE NOTICE '  Users:         4 (demo_mea/cyber/sebi/ncb@anveshak.local)';
    RAISE NOTICE '  Topics:        4 (MEA, Cyber Fraud, SEBI, NCB)';
    RAISE NOTICE '  Sources:       20 (5 MEA + 6 Cyber + 5 SEBI + 4 NCB)';
    RAISE NOTICE '  Content:       34 items (8 MEA + 10 Cyber + 8 SEBI + 8 NCB)';
    RAISE NOTICE '  Clusters:      5 narrative + 7 identifier';
    RAISE NOTICE '  Signals:       7 (1 MEA + 2 Cyber + 2 SEBI + 2 NCB)';
    RAISE NOTICE '  Reports:       4 (1 per agency, with identifier sections)';
    RAISE NOTICE '  Templates:     10 topic-template links';
    RAISE NOTICE '';
    RAISE NOTICE 'Password for all demo users: AnveshakDemo2024!';
    RAISE NOTICE '';
    RAISE NOTICE 'Login URLs:';
    RAISE NOTICE '  MEA:   demo_mea@anveshak.local';
    RAISE NOTICE '  Cyber: demo_cyber@anveshak.local';
    RAISE NOTICE '  SEBI:  demo_sebi@anveshak.local';
    RAISE NOTICE '  NCB:   demo_ncb@anveshak.local';
END $$;
