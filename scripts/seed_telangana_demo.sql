-- ==========================================================================
-- Telangana Cyber Cell Demo — Investment Fraud & Mule Account Monitoring
-- ==========================================================================
-- Scenario: TGCSB monitoring investment fraud, pig butchering scams,
-- mule account recruitment, and UPI fraud networks across Telegram,
-- news sources, and dark web.
--
-- Context: Telangana saw 11,657 investment scam cases (Jan-Sep 2025),
-- ₹547 crore single fraud case (Khammam), 56% of India's cybercrime
-- losses from pig butchering. TGCSB nabbed 48 criminals, 38 mule holders.
--
-- Org: org_cyber (reusing existing org for demo user)
-- User: demo_cyber@anveshak.local (existing)
--
-- Idempotent: all INSERTs use ON CONFLICT DO NOTHING.
-- Run: docker exec -i anveshak-postgres-1 psql -U anveshak -d anveshak < scripts/seed_telangana_demo.sql
-- ==========================================================================

-- ==========================================================================
-- 1. Topic
-- ==========================================================================
INSERT INTO topics (
    id, name, keywords, signal_threshold, identifier_signal_threshold,
    status, languages, credibility_min,
    labels, created_at, updated_at, org_id
) VALUES (
    'tg-cyber-001',
    'Telangana Cyber Fraud Intelligence',
    ARRAY['investment fraud', 'pig butchering', 'mule account', 'UPI fraud',
          'stock trading scam', 'Telegram fraud', 'digital arrest',
          'TGCSB', 'crypto scam', 'Hyderabad cyber crime',
          'fake trading app', 'money laundering'],
    2, 2, 'active', ARRAY['en', 'hi', 'te'], 20.0,
    '{"classification":"RESTRICTED","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb,
    NOW() - INTERVAL '30 days', NOW(), 'org_cyber'
) ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 2. Sources (15)
-- ==========================================================================

-- ── RSS / Web News Sources (Telangana + National Cyber Crime) ──
INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, health_status, labels, created_at, updated_at, org_id) VALUES
    -- Telangana local news
    ('tg-src-01', 'Telangana Today - Cyber Crime',    'https://telanganatoday.com/tag/cybercrime/feed',  'rss', 80.0, true, 'healthy', '{"classification":"OPEN","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('tg-src-02', 'Deccan Chronicle - Telangana',     'https://www.deccanchronicle.com/southern-states/telangana/rss', 'rss', 78.0, true, 'healthy', '{"classification":"OPEN","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('tg-src-03', 'The Siasat Daily',                 'https://www.siasat.com/feed',                     'rss', 72.0, true, 'healthy', '{"classification":"OPEN","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('tg-src-04', 'The Hans India - Hyderabad',       'https://www.thehansindia.com/feed/telangana',     'rss', 70.0, true, 'healthy', '{"classification":"OPEN","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),

    -- National cyber crime news
    ('tg-src-05', 'The420.in - Cyber Crime News',     'https://the420.in/feed',                          'rss', 75.0, true, 'healthy', '{"classification":"OPEN","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('tg-src-06', 'TGCSB Official News',              'https://tgcsb.tspolice.gov.in',                   'web', 95.0, true, 'healthy', '{"classification":"OPEN","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),

    -- ── Telegram Sources (REAL channels — mule accounts, UPI fraud, crypto) ──
    -- These are real public Telegram channels known for mule/fraud activity
    ('tg-src-07', 'India Bank Accounts Channel',      'indiabankaccs',      'telegram', 15.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('tg-src-08', 'AlphaPay Telegram',                'ALPHAPAY3333',       'telegram', 15.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('tg-src-09', 'GamingPay191',                     'gamingpay191',       'telegram', 10.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('tg-src-10', 'USDT Exchange India',              'usdt_exchange_ind',  'telegram', 10.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('tg-src-11', 'Money Transfer Agents',            'money_transfer_in',  'telegram', 12.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),

    -- ── YouTube (Cyber awareness / TGCSB press conferences) ──
    ('tg-src-12', 'TGCSB Press Conferences',          'tgcsb_official',     'youtube',  85.0, true, 'healthy', '{"classification":"OPEN","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),

    -- ── Dark Web ──
    ('tg-src-13', 'DuckDuckGo Onion',                 'http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/', 'darkweb', 5.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),

    -- ── Instagram (Scam lure accounts) ──
    ('tg-src-14', 'Hyderabad Earn Online',            'hyd_earn_online',    'instagram', 8.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('tg-src-15', 'Invest Pro Hyderabad',             'investpro_hyd',      'instagram', 8.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"cyber_fraud","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber')
ON CONFLICT (id) DO NOTHING;

-- org_sources visibility
INSERT INTO org_sources (org_id, source_id) VALUES
    ('org_cyber','tg-src-01'),('org_cyber','tg-src-02'),('org_cyber','tg-src-03'),
    ('org_cyber','tg-src-04'),('org_cyber','tg-src-05'),('org_cyber','tg-src-06'),
    ('org_cyber','tg-src-07'),('org_cyber','tg-src-08'),('org_cyber','tg-src-09'),
    ('org_cyber','tg-src-10'),('org_cyber','tg-src-11'),('org_cyber','tg-src-12'),
    ('org_cyber','tg-src-13'),('org_cyber','tg-src-14'),('org_cyber','tg-src-15')
ON CONFLICT DO NOTHING;

-- topic_sources
INSERT INTO topic_sources (topic_id, source_id) VALUES
    ('tg-cyber-001','tg-src-01'),('tg-cyber-001','tg-src-02'),('tg-cyber-001','tg-src-03'),
    ('tg-cyber-001','tg-src-04'),('tg-cyber-001','tg-src-05'),('tg-cyber-001','tg-src-06'),
    ('tg-cyber-001','tg-src-07'),('tg-cyber-001','tg-src-08'),('tg-cyber-001','tg-src-09'),
    ('tg-cyber-001','tg-src-10'),('tg-cyber-001','tg-src-11'),('tg-cyber-001','tg-src-12'),
    ('tg-cyber-001','tg-src-13'),('tg-cyber-001','tg-src-14'),('tg-cyber-001','tg-src-15')
ON CONFLICT DO NOTHING;

-- Also link the EXISTING real Telegram channels that already have cyber fraud data
INSERT INTO topic_sources (topic_id, source_id) VALUES
    ('tg-cyber-001', '7edc0f46-e5b0-448e-a0ac-298ebc88f441'),  -- India Bank Accounts (already scraping)
    ('tg-cyber-001', 'b2a4c275-ed10-4c5a-93d0-a2013bcbacf2')   -- AlphaPay (already scraping)
ON CONFLICT DO NOTHING;

-- ==========================================================================
-- 3. Keyword Alert Rules
-- ==========================================================================
INSERT INTO keyword_alert_rules (id, topic_id, keywords, match_mode, is_active, notify_websocket, created_by, org_id, created_at, updated_at, labels) VALUES
    ('tg-alert-01', 'tg-cyber-001', ARRAY['mule account', 'bank account', 'UPI', 'IMPS'], 'any', true, true, 'ec-user-cyber', 'org_cyber', NOW()-INTERVAL '25 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"cyber"}'::jsonb),
    ('tg-alert-02', 'tg-cyber-001', ARRAY['USDT', 'crypto', 'bitcoin', 'tether', 'USDC'], 'any', true, true, 'ec-user-cyber', 'org_cyber', NOW()-INTERVAL '25 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"cyber"}'::jsonb),
    ('tg-alert-03', 'tg-cyber-001', ARRAY['pig butchering', 'investment scam', 'trading scam', 'digital arrest'], 'any', true, true, 'ec-user-cyber', 'org_cyber', NOW()-INTERVAL '25 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"cyber"}'::jsonb),
    ('tg-alert-04', 'tg-cyber-001', ARRAY['+852', '+86', 'Hong Kong', 'Chinese number'], 'any', true, true, 'ec-user-cyber', 'org_cyber', NOW()-INTERVAL '25 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"cyber"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- Done. Verify:
-- ==========================================================================
SELECT 'Topic' AS entity, COUNT(*) FROM topics WHERE id = 'tg-cyber-001'
UNION ALL SELECT 'Sources', COUNT(*) FROM sources WHERE id LIKE 'tg-src-%'
UNION ALL SELECT 'Topic-Sources', COUNT(*) FROM topic_sources WHERE topic_id = 'tg-cyber-001'
UNION ALL SELECT 'Alert Rules', COUNT(*) FROM keyword_alert_rules WHERE topic_id = 'tg-cyber-001';
