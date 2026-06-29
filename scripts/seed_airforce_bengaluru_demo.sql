-- ==========================================================================
-- IAF Bengaluru Demo — Air Force Intelligence Seed Data
-- ==========================================================================
-- Scenario: IAF intelligence wing monitoring Chinese air power near LAC,
-- anti-IAF disinformation campaigns, and PAF modernization.
-- Audience: IAF officers at Bengaluru (HAL HQ, DRDO ADA, Training Command).
--
-- Org: org_iaf (Air Force Intelligence Wing)
-- User: demo_iaf@anveshak.local
--
-- Idempotent: all INSERTs use ON CONFLICT DO NOTHING.
-- Run: make seed-demo-iaf
--   or: docker exec -i anveshak-postgres-1 psql -U anveshak -d anveshak < scripts/seed_airforce_bengaluru_demo.sql
-- ==========================================================================

BEGIN;

-- ==========================================================================
-- 0. Organization + User
-- ==========================================================================
INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
VALUES (
    'org_iaf',
    'Air Force Intelligence Wing',
    'iaf',
    NOW(), NOW(),
    '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb
) ON CONFLICT (id) DO NOTHING;

-- Password: AnveshakDemo2024! (same bcrypt hash as other demo accounts)
INSERT INTO users (id, username, password_hash, role, org_id, created_at, updated_at, labels)
VALUES (
    'iaf-user-analyst',
    'demo_iaf@anveshak.local',
    '$2b$12$exK0vBQZHOMCPjg37GTJZ.AtYqz1NI5SXwMLrWjnPvP2IqZMZKaei',
    'analyst',
    'org_iaf',
    NOW(), NOW(),
    '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb
) ON CONFLICT (username) DO NOTHING;

-- ==========================================================================
-- 1. Topics (3)
-- ==========================================================================
INSERT INTO topics (
    id, name, keywords, signal_threshold, identifier_signal_threshold,
    status, languages, credibility_min,
    labels, created_at, updated_at, org_id
) VALUES
(
    'iaf-topic-01',
    'Chinese Air Power — LAC Threat Assessment',
    ARRAY['J-20', 'PLAAF', 'Hotan', 'Kashgar', 'Wing Loong', 'WZ-7', 'stealth',
          'LAC', 'Aksai Chin', 'Tibet airbase', 'Ngari', 'WS-15', 'fifth-gen'],
    3, 2, 'active', ARRAY['en'], 30.0,
    '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb,
    NOW() - INTERVAL '30 days', NOW(), 'org_iaf'
),
(
    'iaf-topic-02',
    'Anti-IAF Disinformation & Deepfakes',
    ARRAY['deepfake', 'Rafale', 'propaganda', 'fabricated', 'disinformation',
          'IAF', 'fake video', 'AI-generated', 'Tejas', 'AMCA', 'HAL'],
    2, 2, 'active', ARRAY['en', 'hi'], 20.0,
    '{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb,
    NOW() - INTERVAL '30 days', NOW(), 'org_iaf'
),
(
    'iaf-topic-03',
    'PAF Modernization & Force Posture',
    ARRAY['JF-17', 'Block 3', 'PL-15', 'PAF', 'Shaheen', 'J-10CP',
          'Skardu', 'KLJ-7A', 'AESA', 'F-16', 'Chinese arms'],
    3, 2, 'active', ARRAY['en'], 30.0,
    '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb,
    NOW() - INTERVAL '30 days', NOW(), 'org_iaf'
)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 2. Sources (16)
-- ==========================================================================
INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, health_status, labels, created_at, updated_at, org_id) VALUES
    -- RSS / Web defence publications
    ('iaf-src-01', 'Jane''s Defence Weekly',    'https://www.janes.com/feeds/defence',       'rss',  91.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-02', 'The War Zone',              'https://www.twz.com/feed',                  'rss',  80.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-03', 'Indian Defence Review',     'https://www.indiandefencereview.com/feed',   'rss',  76.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-04', 'LiveFist Defence',          'https://www.livefistdefence.com/feed',       'rss',  74.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-05', 'SCMP Defence',              'https://www.scmp.com/topics/china-military', 'rss',  72.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-06', 'Global Times Military',     'https://www.globaltimes.cn/military',        'web',  35.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-07', 'Defence.pk Forum',          'https://defence.pk',                         'web',  40.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-08', 'SIPRI Arms Transfers',      'https://www.sipri.org/databases/armstransfers','web', 88.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    -- Telegram channels
    ('iaf-src-09', 'Defence OSINT',             '@defence_osint',                             'telegram', 55.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-10', 'China Mil Watch',           '@china_mil_watch',                           'telegram', 48.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-11', 'PAF Tracker',               '@paf_tracker',                               'telegram', 42.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-12', 'IAF Disinfo Alert',         '@iaf_disinfo_alert',                         'telegram', 50.0, true, 'healthy', '{"classification":"OPEN","domain":"info_warfare","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    ('iaf-src-13', 'Air Power India',           '@airpower_india',                            'telegram', 45.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    -- Instagram
    ('iaf-src-14', 'Military Aviation IG',      '@mil_aviation_ig',                           'instagram', 52.0, true, 'healthy', '{"classification":"OPEN","domain":"info_warfare","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    -- Reddit
    ('iaf-src-15', 'Defence Forum India',       'r/IndianDefence',                            'reddit', 35.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf'),
    -- OSINT investigator
    ('iaf-src-16', 'Bellingcat OSINT',          'https://www.bellingcat.com',                 'web',  85.0, true, 'healthy', '{"classification":"OPEN","domain":"air_intelligence","owner_org":"iaf"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_iaf')
ON CONFLICT (id) DO NOTHING;

-- org_sources visibility
INSERT INTO org_sources (org_id, source_id) VALUES
    ('org_iaf','iaf-src-01'),('org_iaf','iaf-src-02'),('org_iaf','iaf-src-03'),('org_iaf','iaf-src-04'),
    ('org_iaf','iaf-src-05'),('org_iaf','iaf-src-06'),('org_iaf','iaf-src-07'),('org_iaf','iaf-src-08'),
    ('org_iaf','iaf-src-09'),('org_iaf','iaf-src-10'),('org_iaf','iaf-src-11'),('org_iaf','iaf-src-12'),
    ('org_iaf','iaf-src-13'),('org_iaf','iaf-src-14'),('org_iaf','iaf-src-15'),('org_iaf','iaf-src-16')
ON CONFLICT DO NOTHING;

-- topic_sources (each source linked to relevant topics)
INSERT INTO topic_sources (topic_id, source_id) VALUES
    -- Topic 1: Chinese Air Power (11 sources)
    ('iaf-topic-01','iaf-src-01'),('iaf-topic-01','iaf-src-02'),('iaf-topic-01','iaf-src-03'),
    ('iaf-topic-01','iaf-src-04'),('iaf-topic-01','iaf-src-05'),('iaf-topic-01','iaf-src-06'),
    ('iaf-topic-01','iaf-src-09'),('iaf-topic-01','iaf-src-10'),('iaf-topic-01','iaf-src-13'),
    ('iaf-topic-01','iaf-src-16'),
    -- Topic 2: Disinformation (8 sources)
    ('iaf-topic-02','iaf-src-02'),('iaf-topic-02','iaf-src-04'),('iaf-topic-02','iaf-src-09'),
    ('iaf-topic-02','iaf-src-12'),('iaf-topic-02','iaf-src-13'),('iaf-topic-02','iaf-src-14'),
    ('iaf-topic-02','iaf-src-15'),('iaf-topic-02','iaf-src-16'),
    -- Topic 3: PAF Modernization (7 sources)
    ('iaf-topic-03','iaf-src-01'),('iaf-topic-03','iaf-src-03'),('iaf-topic-03','iaf-src-04'),
    ('iaf-topic-03','iaf-src-07'),('iaf-topic-03','iaf-src-08'),('iaf-topic-03','iaf-src-11'),
    ('iaf-topic-03','iaf-src-13')
ON CONFLICT DO NOTHING;

-- ==========================================================================
-- 3. Narrative Clusters (6)
-- ==========================================================================
INSERT INTO narrative_clusters (id, topic_id, label, item_count, independent_source_count, executive_summary, created_at, updated_at, labels) VALUES
    ('iaf-cl-01', 'iaf-topic-01', 'J-20 Stealth Fighter Deployments near LAC', 12, 5,
     'Multiple independent sources confirm J-20 fifth-generation stealth fighter deployment at Hotan and Kashgar airbases in Xinjiang. Satellite imagery shows at least 8 aircraft with hardened shelters. WS-15 engine upgrade extends combat radius to cover northern Ladakh.',
     NOW()-INTERVAL '28 days', NOW(), '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
    ('iaf-cl-02', 'iaf-topic-01', 'PLAAF UAV/Drone Activity — Northern Borders', 8, 4,
     'Rising PLAAF drone activity along LAC. WZ-7 Soaring Dragon high-altitude ISR UAV conducting regular sorties near Ladakh airspace. Wing Loong III armed UCAVs deployed at Kashgar. Sortie patterns correlate with Indian exercise schedules.',
     NOW()-INTERVAL '22 days', NOW(), '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
    ('iaf-cl-03', 'iaf-topic-02', 'Coordinated Deepfake Campaign Against IAF', 10, 4,
     'Coordinated disinformation operation detected across Telegram, Reddit, Instagram, and adversary web. Fake Rafale shootdown video (deepfake score 0.94) and fabricated Tejas crash footage amplified across 15+ channels within 4 hours. EXIF analysis shows AI generation markers.',
     NOW()-INTERVAL '15 days', NOW(), '{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
    ('iaf-cl-04', 'iaf-topic-03', 'JF-17 Block 3 Induction & PAF-PLAAF Exercises', 10, 3,
     'PAF inducts JF-17 Block 3 with KLJ-7A AESA radar and PL-15 BVR missile integration. Shaheen-X joint exercise with PLAAF near Skardu included BVR combat scenarios. Chinese J-10CP transfer to PAF under evaluation.',
     NOW()-INTERVAL '18 days', NOW(), '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
    ('iaf-cl-05', 'iaf-topic-01', 'Tibet Airbase Infrastructure Expansion', 8, 4,
     'Rapid infrastructure expansion across Tibetan plateau airbases. New 3,500m runway at Ngari Gunsa, hardened aircraft shelters at Lhasa Gonggar, fuel/ammunition depots at Shigatse. Construction timeline suggests operational readiness by Q4 2026.',
     NOW()-INTERVAL '20 days', NOW(), '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
    ('iaf-cl-06', 'iaf-topic-02', 'HAL/DRDO Misinformation Narratives', 7, 3,
     'Adversary media weaponizing Tejas production delay narratives and spreading false AMCA cancellation reports. Coordinated social media campaign questioning indigenous LCA capability. Sources include Global Times, Defence.pk, and amplification via Telegram.',
     NOW()-INTERVAL '12 days', NOW(), '{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 4. Content Items (55 items across 6 clusters)
-- ==========================================================================

-- ── Cluster 1: J-20 Stealth Deployments (12 items) ──
INSERT INTO content_items (id, topic_id, source_id, url, raw_text, clean_text, content_hash, language, captured_at, credibility_score_at_capture, narrative_cluster_id, labels, created_at, updated_at, org_id) VALUES
('iaf-ci-01','iaf-topic-01','iaf-src-01','https://www.janes.com/defence-news/j20-hotan-deployment','J-20 deployment confirmed at Hotan Airbase','Jane''s Defence confirms deployment of at least eight J-20 fifth-generation stealth fighters at Hotan Airbase, Xinjiang Province. Satellite imagery from commercial providers shows new hardened aircraft shelters constructed specifically for the platform. Deployment represents significant force projection capability towards the LAC.',md5('iaf-ci-01'),'en',NOW()-INTERVAL '28 days',91.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Janes Defence","author_id":"iaf-src-01","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.3,"label":"negative"},"keywords":["J-20","Hotan","stealth","deployment","LAC"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_iaf'),

('iaf-ci-02','iaf-topic-01','iaf-src-05','https://www.scmp.com/news/china/military/j20-operational','PLAAF J-20 operational readiness at western bases','South China Morning Post reports PLAAF Western Theatre Command has achieved initial operational capability with J-20 stealth fighters at two forward bases near India border. Sources indicate integration of new PL-15 beyond-visual-range missiles enhancing engagement envelope.',md5('iaf-ci-02'),'en',NOW()-INTERVAL '27 days',72.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"SCMP","author_id":"iaf-src-05","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.25,"label":"negative"},"keywords":["J-20","PLAAF","Western Theatre","PL-15","stealth"]}'::jsonb,NOW()-INTERVAL '27 days',NOW(),'org_iaf'),

('iaf-ci-03','iaf-topic-01','iaf-src-10','https://t.me/china_mil_watch/892','Satellite imagery J-20 at Kashgar','BREAKING: New satellite pass shows 4x J-20 at Kashgar forward operating base. Previously only seen at Hotan. Two aircraft appear to have external fuel tanks fitted — suggests extended range ops towards Ladakh sector. Serial 78271 visible on tail.',md5('iaf-ci-03'),'en',NOW()-INTERVAL '26 days',48.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@china_mil_watch","author_id":"china_mil_watch","engagement":{"likes":45,"comments":23,"shares":0,"views":1200,"forwards":18},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["J-20","Kashgar","satellite","Ladakh","serial 78271"]}'::jsonb,NOW()-INTERVAL '26 days',NOW(),'org_iaf'),

('iaf-ci-04','iaf-topic-01','iaf-src-09','https://t.me/defence_osint/445','J-20 exercise near Aksai Chin','Defence OSINT: Multiple J-20 sorties detected in Aksai Chin corridor over 48 hours. Flight patterns suggest air superiority training with simulated BVR engagements. PLAAF using new datalink for coordinated stealth ops. Serial 78271 confirmed again.',md5('iaf-ci-04'),'en',NOW()-INTERVAL '25 days',55.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@defence_osint","author_id":"defence_osint","engagement":{"likes":67,"comments":34,"shares":0,"views":1800,"forwards":25},"sentiment":{"compound":-0.35,"label":"negative"},"keywords":["J-20","Aksai Chin","BVR","stealth","datalink"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_iaf'),

('iaf-ci-05','iaf-topic-01','iaf-src-02','https://www.twz.com/j20-ws15-engine-upgrade','WS-15 engine upgrade extends J-20 combat radius','The War Zone analysis: WS-15 turbofan engine now confirmed on production J-20B variants. Engine delivers 18 tonnes thrust with supercruise capability. Combat radius extends to 2,200 km from Hotan — covering all of northern Ladakh and Kashmir valley without aerial refuelling.',md5('iaf-ci-05'),'en',NOW()-INTERVAL '24 days',80.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"The War Zone","author_id":"iaf-src-02","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.45,"label":"negative"},"keywords":["WS-15","J-20B","combat radius","supercruise","Ladakh"]}'::jsonb,NOW()-INTERVAL '24 days',NOW(),'org_iaf'),

('iaf-ci-06','iaf-topic-01','iaf-src-06','https://www.globaltimes.cn/page/j20-western-deployment','Global Times: J-20 deployment legitimate defence measure','Global Times editorial: J-20 deployment near western border is legitimate self-defence measure in response to Indian provocations at LAC. PLAAF modernization is peaceful and defensive in nature. Western media exaggerating threat.',md5('iaf-ci-06'),'en',NOW()-INTERVAL '23 days',35.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Global Times","author_id":"iaf-src-06","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.2,"label":"positive"},"keywords":["J-20","western border","defence","PLAAF","LAC"]}'::jsonb,NOW()-INTERVAL '23 days',NOW(),'org_iaf'),

('iaf-ci-07','iaf-topic-01','iaf-src-16','https://www.bellingcat.com/j20-hotan-analysis','Bellingcat: J-20 shelter construction timeline at Hotan','Bellingcat geospatial analysis traces J-20 shelter construction at Hotan from March 2025. Planet Labs imagery shows 12 hardened shelters, taxiway extensions, and new fuel storage. Facility designed for sustained operations with 16+ aircraft capacity.',md5('iaf-ci-07'),'en',NOW()-INTERVAL '22 days',85.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Bellingcat","author_id":"iaf-src-16","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.3,"label":"negative"},"keywords":["J-20","Hotan","Bellingcat","hardened shelters","geospatial"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_iaf'),

('iaf-ci-08','iaf-topic-01','iaf-src-13','https://t.me/airpower_india/234','J-20 vs Rafale comparison assessment','Air Power India analysis: J-20 with WS-15 closes the supercruise gap with Rafale. Key advantages: larger weapons bay, higher service ceiling. Rafale maintains edge in EW suite and proven combat record. LAC theatre favors stealth at altitude.',md5('iaf-ci-08'),'en',NOW()-INTERVAL '21 days',45.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@airpower_india","author_id":"airpower_india","engagement":{"likes":89,"comments":56,"shares":0,"views":2300,"forwards":30},"sentiment":{"compound":-0.15,"label":"neutral"},"keywords":["J-20","Rafale","WS-15","supercruise","comparison"]}'::jsonb,NOW()-INTERVAL '21 days',NOW(),'org_iaf'),

('iaf-ci-09','iaf-topic-01','iaf-src-03','https://www.indiandefencereview.com/j20-lac-implications','Strategic implications of J-20 near LAC','Indian Defence Review assessment: J-20 deployment at Hotan and Kashgar fundamentally alters air balance along LAC. India must accelerate AMCA timeline and consider additional Rafale squadrons. Current Su-30MKI radar cross-section disadvantage significant.',md5('iaf-ci-09'),'en',NOW()-INTERVAL '20 days',76.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Indian Defence Review","author_id":"iaf-src-03","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["J-20","LAC","AMCA","Rafale","Su-30MKI"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_iaf'),

('iaf-ci-10','iaf-topic-01','iaf-src-04','https://www.livefistdefence.com/j20-night-ops','J-20 night operations detected at Hotan','LiveFist Defence: Thermal imagery from commercial satellites shows J-20 night operations at Hotan. At least 4 sorties between 2200-0400 local time. Night operations capability indicates advanced pilot training and platform maturity.',md5('iaf-ci-10'),'en',NOW()-INTERVAL '18 days',74.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"LiveFist Defence","author_id":"iaf-src-04","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.35,"label":"negative"},"keywords":["J-20","night operations","Hotan","thermal","sorties"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_iaf'),

('iaf-ci-11','iaf-topic-01','iaf-src-10','https://t.me/china_mil_watch/910','J-20 two-ship formation spotted','Two-ship J-20 formation photographed by civilian pilot near Aksai Chin. Aircraft at estimated FL450. Clean configuration — no external stores. Serial 78271 and 78273 identified from enhanced imagery.',md5('iaf-ci-11'),'en',NOW()-INTERVAL '16 days',48.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@china_mil_watch","author_id":"china_mil_watch","engagement":{"likes":56,"comments":38,"shares":0,"views":1600,"forwards":22},"sentiment":{"compound":-0.2,"label":"negative"},"keywords":["J-20","formation","Aksai Chin","FL450","serial 78271"]}'::jsonb,NOW()-INTERVAL '16 days',NOW(),'org_iaf'),

('iaf-ci-12','iaf-topic-01','iaf-src-09','https://t.me/defence_osint/460','PLAAF J-20 alert readiness confirmed','Defence OSINT assesses J-20 unit at Hotan has achieved 24/7 alert readiness based on hangar door open/close patterns over 14 days. Minimum 2 aircraft on hot standby at all times. Unprecedented for PLAAF fifth-gen operations near India.',md5('iaf-ci-12'),'en',NOW()-INTERVAL '14 days',55.0,'iaf-cl-01','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@defence_osint","author_id":"defence_osint","engagement":{"likes":78,"comments":45,"shares":0,"views":2100,"forwards":28},"sentiment":{"compound":-0.55,"label":"negative"},"keywords":["J-20","alert readiness","Hotan","PLAAF","hot standby"]}'::jsonb,NOW()-INTERVAL '14 days',NOW(),'org_iaf'),

-- ── Cluster 2: PLAAF UAV/Drone Activity (8 items) ──
('iaf-ci-13','iaf-topic-01','iaf-src-02','https://www.twz.com/wz7-soaring-dragon-ladakh','WZ-7 Soaring Dragon ISR near Ladakh airspace','The War Zone exclusive: WZ-7 Soaring Dragon high-altitude ISR UAV conducting regular sorties at 65,000 feet near Ladakh airspace boundary. Platform capable of 10-hour loiter providing persistent surveillance of Indian military positions along LAC.',md5('iaf-ci-13'),'en',NOW()-INTERVAL '25 days',80.0,'iaf-cl-02','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"The War Zone","author_id":"iaf-src-02","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["WZ-7","Soaring Dragon","Ladakh","ISR","surveillance"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_iaf'),

('iaf-ci-14','iaf-topic-01','iaf-src-10','https://t.me/china_mil_watch/895','Wing Loong III at Kashgar spotted','ALERT: Wing Loong III armed UCAVs spotted at Kashgar. At least 3 platforms with visible weapons pylons. These are strike-capable with 480 km combat radius. Can reach targets deep in Ladakh sector.',md5('iaf-ci-14'),'en',NOW()-INTERVAL '23 days',48.0,'iaf-cl-02','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@china_mil_watch","author_id":"china_mil_watch","engagement":{"likes":34,"comments":18,"shares":0,"views":980,"forwards":15},"sentiment":{"compound":-0.6,"label":"negative"},"keywords":["Wing Loong III","Kashgar","UCAV","strike","Ladakh"]}'::jsonb,NOW()-INTERVAL '23 days',NOW(),'org_iaf'),

('iaf-ci-15','iaf-topic-01','iaf-src-16','https://www.bellingcat.com/plaaf-drone-patterns','Bellingcat: PLAAF drone sortie patterns correlate with Indian exercises','Bellingcat investigation reveals PLAAF drone sorties from Kashgar increase 3x during announced Indian military exercises. WZ-7 and Wing Loong flights peak within 24 hours of Indian exercise commencement. Pattern suggests real-time intelligence collection.',md5('iaf-ci-15'),'en',NOW()-INTERVAL '21 days',85.0,'iaf-cl-02','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Bellingcat","author_id":"iaf-src-16","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["PLAAF","drone","Bellingcat","exercises","intelligence"]}'::jsonb,NOW()-INTERVAL '21 days',NOW(),'org_iaf'),

('iaf-ci-16','iaf-topic-01','iaf-src-09','https://t.me/defence_osint/448','GJ-11 stealth drone test over Tibet','Defence OSINT: Unconfirmed reports of GJ-11 Sharp Sword stealth UCAV test flights from Shigatse airbase. If confirmed, represents first stealth drone deployment near Indian border. GJ-11 designed for ISR and precision strike.',md5('iaf-ci-16'),'en',NOW()-INTERVAL '19 days',55.0,'iaf-cl-02','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@defence_osint","author_id":"defence_osint","engagement":{"likes":45,"comments":28,"shares":0,"views":1400,"forwards":18},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["GJ-11","stealth","UCAV","Shigatse","Tibet"]}'::jsonb,NOW()-INTERVAL '19 days',NOW(),'org_iaf'),

('iaf-ci-17','iaf-topic-01','iaf-src-04','https://www.livefistdefence.com/plaaf-drone-fleet','PLAAF drone fleet expansion near India border','LiveFist: PLAAF Western Theatre now operates estimated 40+ UAVs from 3 bases near India border. Mix includes WZ-7 (ISR), Wing Loong III (armed ISR/strike), and CH-6 (medium altitude). India''s counter-drone gap widening.',md5('iaf-ci-17'),'en',NOW()-INTERVAL '17 days',74.0,'iaf-cl-02','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"LiveFist Defence","author_id":"iaf-src-04","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.45,"label":"negative"},"keywords":["PLAAF","drone","UAV","counter-drone","Western Theatre"]}'::jsonb,NOW()-INTERVAL '17 days',NOW(),'org_iaf'),

('iaf-ci-18','iaf-topic-01','iaf-src-13','https://t.me/airpower_india/240','Counter-drone response needed','Air Power India: India urgently needs integrated counter-UAS network along LAC. Current air defence optimized for manned aircraft threats. PLAAF drone swarm doctrine developing rapidly. Recommend evaluation of Israeli Iron Dome style C-UAS.',md5('iaf-ci-18'),'en',NOW()-INTERVAL '15 days',45.0,'iaf-cl-02','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@airpower_india","author_id":"airpower_india","engagement":{"likes":56,"comments":34,"shares":0,"views":1600,"forwards":20},"sentiment":{"compound":-0.35,"label":"negative"},"keywords":["counter-UAS","drone","LAC","C-UAS","air defence"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_iaf'),

('iaf-ci-19','iaf-topic-01','iaf-src-01','https://www.janes.com/defence-news/plaaf-uav-order','PLAAF orders 120 additional Wing Loong III','Jane''s reports PLAAF procurement of 120 additional Wing Loong III UCAVs from AVIC/Chengdu. Order indicates planned expansion of drone operations across all theatre commands. Western Theatre allocation estimated at 30-40 platforms.',md5('iaf-ci-19'),'en',NOW()-INTERVAL '13 days',91.0,'iaf-cl-02','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Janes Defence","author_id":"iaf-src-01","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.3,"label":"negative"},"keywords":["Wing Loong III","PLAAF","procurement","AVIC","expansion"]}'::jsonb,NOW()-INTERVAL '13 days',NOW(),'org_iaf'),

('iaf-ci-20','iaf-topic-01','iaf-src-03','https://www.indiandefencereview.com/drone-threat-lac','IDR: Growing drone threat demands IAF response','Indian Defence Review strategic assessment: PLAAF drone buildup represents most significant asymmetric threat shift at LAC since 2020. Recommends fast-tracking Tapas and Archer programs, and Heron TP acquisition for armed ISR.',md5('iaf-ci-20'),'en',NOW()-INTERVAL '10 days',76.0,'iaf-cl-02','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Indian Defence Review","author_id":"iaf-src-03","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["drone","LAC","Tapas","Heron","asymmetric threat"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_iaf'),

-- ── Cluster 3: Coordinated Deepfake Campaign (10 items) ──
('iaf-ci-21','iaf-topic-02','iaf-src-12','https://t.me/iaf_disinfo_alert/78','ALERT: Fake Rafale shootdown video circulating','URGENT ALERT: Fabricated video showing IAF Rafale being shot down circulating on Telegram. Video uses AI-generated imagery spliced with real French Air Force 2019 training footage. Already shared across 15+ channels. Origin: @fake_iaf_leaks channel.',md5('iaf-ci-21'),'en',NOW()-INTERVAL '15 days',50.0,'iaf-cl-03','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"@iaf_disinfo_alert","author_id":"iaf_disinfo_alert","engagement":{"likes":34,"comments":89,"shares":0,"views":3200,"forwards":45},"sentiment":{"compound":-0.8,"label":"negative"},"keywords":["deepfake","Rafale","shootdown","fabricated","@fake_iaf_leaks"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_iaf'),

('iaf-ci-22','iaf-topic-02','iaf-src-09','https://t.me/defence_osint/455','Deepfake analysis confirms AI generation','Defence OSINT forensic analysis: Rafale shootdown video confirmed AI-generated. Frame-by-frame analysis shows temporal artifacts at 0:14 and 0:23. Aircraft livery inconsistent with IAF tail numbers. Audio track recycled from 2022 Ukrainian combat footage.',md5('iaf-ci-22'),'en',NOW()-INTERVAL '14 days',55.0,'iaf-cl-03','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"@defence_osint","author_id":"defence_osint","engagement":{"likes":89,"comments":56,"shares":0,"views":4500,"forwards":60},"sentiment":{"compound":-0.6,"label":"negative"},"keywords":["deepfake","analysis","AI-generated","forensic","artifacts"]}'::jsonb,NOW()-INTERVAL '14 days',NOW(),'org_iaf'),

('iaf-ci-23','iaf-topic-02','iaf-src-15','https://reddit.com/r/IndianDefence/fake_rafale','Reddit thread amplifying fake Rafale video','Defence Forum India thread with 200+ comments sharing the fake Rafale shootdown video. Top comment from @fake_iaf_leaks alt account claims insider source. Multiple users calling out deepfake but post gaining traction.',md5('iaf-ci-23'),'en',NOW()-INTERVAL '14 days',35.0,'iaf-cl-03','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"r/IndianDefence","author_id":"iaf-src-15","engagement":{"likes":340,"comments":215,"shares":89,"views":12000},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Rafale","deepfake","Reddit","@fake_iaf_leaks","amplification"]}'::jsonb,NOW()-INTERVAL '14 days',NOW(),'org_iaf'),

('iaf-ci-24','iaf-topic-02','iaf-src-14','https://instagram.com/p/fake_rafale_ig','Instagram reel of fake Rafale footage','Military Aviation IG reposts Rafale shootdown footage with caption "IAF worst day?" garnering 45K views. Account previously shared verified content — credibility leveraged for disinfo amplification.',md5('iaf-ci-24'),'en',NOW()-INTERVAL '13 days',52.0,'iaf-cl-03','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"@mil_aviation_ig","author_id":"mil_aviation_ig","engagement":{"likes":890,"comments":234,"shares":345,"views":45000},"sentiment":{"compound":-0.7,"label":"negative"},"keywords":["Rafale","Instagram","deepfake","amplification","views"]}'::jsonb,NOW()-INTERVAL '13 days',NOW(),'org_iaf'),

('iaf-ci-25','iaf-topic-02','iaf-src-16','https://www.bellingcat.com/iaf-disinfo-network','Bellingcat: Coordinated amplification network identified','Bellingcat investigation identifies coordinated amplification network behind IAF deepfake campaign. 18 Telegram channels, 5 Reddit accounts, 3 Instagram pages share content within 4-hour window. Origin traced to @fake_iaf_leaks created 72 hours before campaign launch.',md5('iaf-ci-25'),'en',NOW()-INTERVAL '12 days',85.0,'iaf-cl-03','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"Bellingcat","author_id":"iaf-src-16","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.55,"label":"negative"},"keywords":["Bellingcat","amplification","network","@fake_iaf_leaks","coordinated"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_iaf'),

('iaf-ci-26','iaf-topic-02','iaf-src-13','https://t.me/airpower_india/245','Fake Tejas crash video surfaces','New deepfake: fabricated HAL Tejas crash video using footage from Ukraine Su-25 incident. @fake_iaf_leaks channel posts within hours of Rafale video. Same temporal artifacts — likely same AI tool used for generation.',md5('iaf-ci-26'),'en',NOW()-INTERVAL '11 days',45.0,'iaf-cl-03','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"@airpower_india","author_id":"airpower_india","engagement":{"likes":67,"comments":45,"shares":0,"views":2100,"forwards":28},"sentiment":{"compound":-0.65,"label":"negative"},"keywords":["Tejas","deepfake","crash","@fake_iaf_leaks","Ukraine"]}'::jsonb,NOW()-INTERVAL '11 days',NOW(),'org_iaf'),

('iaf-ci-27','iaf-topic-02','iaf-src-02','https://www.twz.com/iaf-deepfake-campaign','War Zone: IAF targeted by sophisticated deepfake campaign','The War Zone reports on the coordinated deepfake campaign targeting Indian Air Force. Analysis shows professional-grade AI generation tools used. Campaign timing coincides with Aero India 2026 preparations. Likely state-sponsored information operation.',md5('iaf-ci-27'),'en',NOW()-INTERVAL '10 days',80.0,'iaf-cl-03','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"The War Zone","author_id":"iaf-src-02","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.6,"label":"negative"},"keywords":["deepfake","IAF","campaign","state-sponsored","Aero India"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_iaf'),

('iaf-ci-28','iaf-topic-02','iaf-src-04','https://www.livefistdefence.com/iaf-counters-deepfake','IAF official statement on fake videos','LiveFist: IAF Public Relations Directorate issues official statement debunking Rafale and Tejas deepfake videos. Provides original source footage comparison. Urges media to verify before sharing. CERT-In notified for takedown.',md5('iaf-ci-28'),'en',NOW()-INTERVAL '9 days',74.0,'iaf-cl-03','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"LiveFist Defence","author_id":"iaf-src-04","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.3,"label":"positive"},"keywords":["IAF","official","debunk","CERT-In","takedown"]}'::jsonb,NOW()-INTERVAL '9 days',NOW(),'org_iaf'),

('iaf-ci-29','iaf-topic-02','iaf-src-12','https://t.me/iaf_disinfo_alert/85','Amplification network still active','@fake_iaf_leaks channel still active despite reports. New content appearing — now targeting HAL production delays. Same amplification network pushing narratives across platforms. Channel admin uses VPN, registration via +852 Hong Kong number.',md5('iaf-ci-29'),'en',NOW()-INTERVAL '8 days',50.0,'iaf-cl-03','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"@iaf_disinfo_alert","author_id":"iaf_disinfo_alert","engagement":{"likes":23,"comments":34,"shares":0,"views":890,"forwards":12},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["@fake_iaf_leaks","amplification","HAL","+852","Hong Kong"]}'::jsonb,NOW()-INTERVAL '8 days',NOW(),'org_iaf'),

('iaf-ci-30','iaf-topic-02','iaf-src-15','https://reddit.com/r/IndianDefence/disinfo_analysis','Reddit OSINT community traces disinfo origin','Defence Forum India OSINT thread traces @fake_iaf_leaks Telegram channel creation to IP range associated with known state-sponsored influence operations. Channel registered 72h before first deepfake dropped. Pattern matches previous campaigns.',md5('iaf-ci-30'),'en',NOW()-INTERVAL '7 days',35.0,'iaf-cl-03','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"r/IndianDefence","author_id":"iaf-src-15","engagement":{"likes":210,"comments":145,"shares":67,"views":8900},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["@fake_iaf_leaks","OSINT","state-sponsored","IP range","disinfo"]}'::jsonb,NOW()-INTERVAL '7 days',NOW(),'org_iaf'),

-- ── Cluster 4: JF-17 Block 3 & PAF-PLAAF Exercises (10 items) ──
('iaf-ci-31','iaf-topic-03','iaf-src-01','https://www.janes.com/defence-news/jf17-block3-induction','JF-17 Block 3 enters PAF service','Jane''s confirms Pakistan Air Force has inducted first squadron of JF-17 Block 3 at Kamra. Aircraft features KLJ-7A AESA radar, improved EW suite, and capacity for PL-15 BVR missile. 12 aircraft in initial batch with 50 more ordered.',md5('iaf-ci-31'),'en',NOW()-INTERVAL '20 days',91.0,'iaf-cl-04','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Janes Defence","author_id":"iaf-src-01","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.3,"label":"negative"},"keywords":["JF-17","Block 3","PAF","AESA","PL-15"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_iaf'),

('iaf-ci-32','iaf-topic-03','iaf-src-07','https://defence.pk/threads/jf17-block3-first-flight','Defence.pk celebrates JF-17 Block 3 milestone','Defence.pk forum: JF-17 Block 3 "a game changer for PAF". Thread discusses KLJ-7A radar performance claims — 170 km detection range against 3 sqm target. Users comparing favorably against Indian Tejas Mk1A radar.',md5('iaf-ci-32'),'en',NOW()-INTERVAL '19 days',40.0,'iaf-cl-04','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Defence.pk","author_id":"iaf-src-07","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.6,"label":"positive"},"keywords":["JF-17","Block 3","KLJ-7A","radar","PAF"]}'::jsonb,NOW()-INTERVAL '19 days',NOW(),'org_iaf'),

('iaf-ci-33','iaf-topic-03','iaf-src-08','https://www.sipri.org/databases/armstransfers/china-pakistan-2026','SIPRI: China-Pakistan arms transfers surge in 2025-26','SIPRI database update shows 340% increase in Chinese arms transfers to Pakistan in FY2025-26. Major items include JF-17 Block 3 kits, PL-15 missiles, KLJ-7A radars, and CM-400AKG anti-ship missiles. Total value estimated at USD 2.1 billion.',md5('iaf-ci-33'),'en',NOW()-INTERVAL '18 days',88.0,'iaf-cl-04','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"SIPRI","author_id":"iaf-src-08","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["SIPRI","China","Pakistan","arms transfer","JF-17","PL-15"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_iaf'),

('iaf-ci-34','iaf-topic-03','iaf-src-11','https://t.me/paf_tracker/156','PAF-PLAAF Shaheen-X exercise begins','PAF Tracker: Joint PAF-PLAAF exercise Shaheen-X commenced at Skardu. Chinese J-10C and PAF JF-17 Block 3 participating in BVR combat scenarios. First time PL-15 missiles used in joint exercise. 45 aircraft involved.',md5('iaf-ci-34'),'en',NOW()-INTERVAL '16 days',42.0,'iaf-cl-04','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@paf_tracker","author_id":"paf_tracker","engagement":{"likes":56,"comments":34,"shares":0,"views":1500,"forwards":22},"sentiment":{"compound":-0.2,"label":"negative"},"keywords":["Shaheen-X","PAF","PLAAF","Skardu","PL-15","BVR"]}'::jsonb,NOW()-INTERVAL '16 days',NOW(),'org_iaf'),

('iaf-ci-35','iaf-topic-03','iaf-src-03','https://www.indiandefencereview.com/shaheen-x-analysis','IDR: Shaheen-X exercise — implications for India','Indian Defence Review analysis: Shaheen-X exercise demonstrates deepening PAF-PLAAF interoperability. BVR scenarios at Skardu simulate engagement against Su-30MKI type targets. PL-15 integration on JF-17 significantly extends PAF engagement envelope.',md5('iaf-ci-35'),'en',NOW()-INTERVAL '14 days',76.0,'iaf-cl-04','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Indian Defence Review","author_id":"iaf-src-03","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Shaheen-X","interoperability","BVR","PL-15","Su-30MKI"]}'::jsonb,NOW()-INTERVAL '14 days',NOW(),'org_iaf'),

('iaf-ci-36','iaf-topic-03','iaf-src-09','https://t.me/defence_osint/453','J-10CP transfer to PAF under evaluation','Defence OSINT: China reportedly offering J-10CP (Pakistan-specific variant) to PAF as interim fifth-gen bridge. Package includes active electronically scanned array radar and helmet-mounted display. Price quoted at USD 40M per unit.',md5('iaf-ci-36'),'en',NOW()-INTERVAL '12 days',55.0,'iaf-cl-04','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@defence_osint","author_id":"defence_osint","engagement":{"likes":67,"comments":45,"shares":0,"views":1800,"forwards":25},"sentiment":{"compound":-0.35,"label":"negative"},"keywords":["J-10CP","PAF","China","fifth-gen","AESA"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_iaf'),

('iaf-ci-37','iaf-topic-03','iaf-src-04','https://www.livefistdefence.com/paf-force-structure','PAF force structure evolution 2026-2030','LiveFist assessment: PAF targeting 200 JF-17 (all variants), 36 J-10CP, and retaining 75 F-16s by 2030. Combined with PL-15 and SD-10A missiles, PAF air combat capability qualitatively jumps. India''s 4.5-gen numbers advantage narrows.',md5('iaf-ci-37'),'en',NOW()-INTERVAL '10 days',74.0,'iaf-cl-04','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"LiveFist Defence","author_id":"iaf-src-04","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.45,"label":"negative"},"keywords":["PAF","JF-17","J-10CP","F-16","force structure"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_iaf'),

('iaf-ci-38','iaf-topic-03','iaf-src-13','https://t.me/airpower_india/250','PAF Block 3 vs Tejas Mk1A comparison','Air Power India: Technical comparison — JF-17 Block 3 vs Tejas Mk1A. Block 3 advantages: AESA radar maturity, PL-15 integration. Tejas Mk1A advantages: higher thrust-to-weight, superior EW suite (Uttam radar under development).',md5('iaf-ci-38'),'en',NOW()-INTERVAL '8 days',45.0,'iaf-cl-04','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@airpower_india","author_id":"airpower_india","engagement":{"likes":123,"comments":89,"shares":0,"views":3200,"forwards":35},"sentiment":{"compound":-0.15,"label":"neutral"},"keywords":["JF-17","Tejas","Block 3","Mk1A","comparison"]}'::jsonb,NOW()-INTERVAL '8 days',NOW(),'org_iaf'),

('iaf-ci-39','iaf-topic-03','iaf-src-11','https://t.me/paf_tracker/162','PAF Shaheen-X debrief leaked','PAF Tracker: Alleged Shaheen-X exercise debrief indicates PAF achieved 3:1 kill ratio in BVR scenarios using JF-17 Block 3 + PL-15 against aggressor aircraft. Claims unverified. Exercise conducted under favorable conditions for PAF.',md5('iaf-ci-39'),'en',NOW()-INTERVAL '6 days',42.0,'iaf-cl-04','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@paf_tracker","author_id":"paf_tracker","engagement":{"likes":78,"comments":56,"shares":0,"views":2100,"forwards":30},"sentiment":{"compound":-0.3,"label":"negative"},"keywords":["Shaheen-X","debrief","BVR","kill ratio","PL-15"]}'::jsonb,NOW()-INTERVAL '6 days',NOW(),'org_iaf'),

('iaf-ci-40','iaf-topic-03','iaf-src-07','https://defence.pk/threads/paf-j10cp-order','Defence.pk: PAF J-10CP order imminent','Defence.pk forum buzz: PAF expected to sign J-10CP contract within 60 days. Initial order of 25 aircraft. Chinese financing at concessional rates. Aircraft to be based at Minhas (Kamra) alongside JF-17 Block 3 squadron.',md5('iaf-ci-40'),'en',NOW()-INTERVAL '4 days',40.0,'iaf-cl-04','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Defence.pk","author_id":"iaf-src-07","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.4,"label":"positive"},"keywords":["J-10CP","PAF","order","Kamra","Chinese financing"]}'::jsonb,NOW()-INTERVAL '4 days',NOW(),'org_iaf'),

-- ── Cluster 5: Tibet Airbase Infrastructure (8 items) ──
('iaf-ci-41','iaf-topic-01','iaf-src-16','https://www.bellingcat.com/ngari-gunsa-expansion','Bellingcat: New 3,500m runway at Ngari Gunsa airbase','Bellingcat geospatial investigation documents new 3,500m runway at Ngari Gunsa airbase, Tibet. Construction started February 2025, runway appears operational. Length sufficient for fully loaded J-20 and H-6K bomber operations at altitude.',md5('iaf-ci-41'),'en',NOW()-INTERVAL '22 days',85.0,'iaf-cl-05','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Bellingcat","author_id":"iaf-src-16","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["Ngari Gunsa","runway","Tibet","Bellingcat","J-20"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_iaf'),

('iaf-ci-42','iaf-topic-01','iaf-src-01','https://www.janes.com/defence-news/lhasa-gonggar-shelters','Jane''s: Hardened shelters at Lhasa Gonggar airbase','Jane''s satellite analysis identifies 16 new hardened aircraft shelters at Lhasa Gonggar military section. Shelters sized for fighter aircraft. Taxiway connects to expanded apron area. Facility doubles previous aircraft parking capacity.',md5('iaf-ci-42'),'en',NOW()-INTERVAL '20 days',91.0,'iaf-cl-05','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Janes Defence","author_id":"iaf-src-01","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.35,"label":"negative"},"keywords":["Lhasa Gonggar","hardened shelters","Tibet","satellite","fighter"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_iaf'),

('iaf-ci-43','iaf-topic-01','iaf-src-09','https://t.me/defence_osint/450','Shigatse fuel depot construction','Defence OSINT: Large-scale fuel and ammunition storage construction at Shigatse Peace Airport military zone. Underground fuel tanks visible in construction phase. Facility designed to support sustained combat operations.',md5('iaf-ci-43'),'en',NOW()-INTERVAL '18 days',55.0,'iaf-cl-05','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@defence_osint","author_id":"defence_osint","engagement":{"likes":34,"comments":23,"shares":0,"views":1100,"forwards":15},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["Shigatse","fuel depot","ammunition","Tibet","construction"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_iaf'),

('iaf-ci-44','iaf-topic-01','iaf-src-02','https://www.twz.com/tibet-airbase-network','War Zone: Tibet airbase network approaching operational depth','The War Zone analysis: PLAAF has transformed Tibet airbase network from limited staging areas to fully operational combat bases. Five bases now have hardened infrastructure, extended runways, and logistic support for sustained operations within 400km of Indian border.',md5('iaf-ci-44'),'en',NOW()-INTERVAL '16 days',80.0,'iaf-cl-05','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"The War Zone","author_id":"iaf-src-02","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Tibet","airbase","PLAAF","operational","infrastructure"]}'::jsonb,NOW()-INTERVAL '16 days',NOW(),'org_iaf'),

('iaf-ci-45','iaf-topic-01','iaf-src-05','https://www.scmp.com/china/military/tibet-defence','SCMP: PLA strengthens Tibet air defence network','SCMP reports PLA has deployed HQ-9B long-range SAM systems and YLC-8E counter-stealth radars across Tibet Autonomous Region. Air defence umbrella now extends to within 100km of LAC at multiple points.',md5('iaf-ci-45'),'en',NOW()-INTERVAL '14 days',72.0,'iaf-cl-05','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"SCMP","author_id":"iaf-src-05","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.35,"label":"negative"},"keywords":["Tibet","HQ-9B","SAM","air defence","LAC"]}'::jsonb,NOW()-INTERVAL '14 days',NOW(),'org_iaf'),

('iaf-ci-46','iaf-topic-01','iaf-src-10','https://t.me/china_mil_watch/920','Satellite confirms Ngari Gunsa operational','China Mil Watch: Latest satellite pass confirms aircraft activity at Ngari Gunsa new runway. Two fighter-sized aircraft on apron. Facility now operational — reduces PLAAF response time to Ladakh sector by estimated 40 minutes.',md5('iaf-ci-46'),'en',NOW()-INTERVAL '12 days',48.0,'iaf-cl-05','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"@china_mil_watch","author_id":"china_mil_watch","engagement":{"likes":45,"comments":28,"shares":0,"views":1300,"forwards":18},"sentiment":{"compound":-0.45,"label":"negative"},"keywords":["Ngari Gunsa","operational","satellite","Ladakh","response time"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_iaf'),

('iaf-ci-47','iaf-topic-01','iaf-src-04','https://www.livefistdefence.com/tibet-base-timeline','Construction timeline: 5 Tibet airbases 2024-2026','LiveFist: Comprehensive timeline of 5 Tibet airbase upgrades from 2024-2026. Ngari Gunsa (runway), Lhasa Gonggar (shelters), Shigatse (fuel/ammo), Bangda (apron expansion), Kashgar (drone hangars). Combined capacity: 150+ combat aircraft.',md5('iaf-ci-47'),'en',NOW()-INTERVAL '8 days',74.0,'iaf-cl-05','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"LiveFist Defence","author_id":"iaf-src-04","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["Tibet","airbase","timeline","construction","capacity"]}'::jsonb,NOW()-INTERVAL '8 days',NOW(),'org_iaf'),

('iaf-ci-48','iaf-topic-01','iaf-src-03','https://www.indiandefencereview.com/tibet-infrastructure','IDR: Tibet infrastructure changes India''s strategic calculus','Indian Defence Review: Tibet airbase buildup fundamentally changes India strategic calculus on LAC. Forward basing reduces PLAAF transit time, increases sortie generation rate, and enables sustained operations previously impossible at altitude.',md5('iaf-ci-48'),'en',NOW()-INTERVAL '5 days',76.0,'iaf-cl-05','{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","author_handle":"Indian Defence Review","author_id":"iaf-src-03","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Tibet","strategic","LAC","sortie rate","forward basing"]}'::jsonb,NOW()-INTERVAL '5 days',NOW(),'org_iaf'),

-- ── Cluster 6: HAL/DRDO Misinformation (7 items) ──
('iaf-ci-49','iaf-topic-02','iaf-src-06','https://www.globaltimes.cn/page/tejas-failure','Global Times: India''s Tejas program a costly failure','Global Times commentary: India''s Tejas LCA program represents decades of delays and billions wasted. Aircraft still cannot match JF-17 Block 3 in key parameters. India''s indigenous defence production capability remains questionable.',md5('iaf-ci-49'),'en',NOW()-INTERVAL '12 days',35.0,'iaf-cl-06','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"Global Times","author_id":"iaf-src-06","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.7,"label":"negative"},"keywords":["Tejas","failure","delays","JF-17","Global Times"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_iaf'),

('iaf-ci-50','iaf-topic-02','iaf-src-07','https://defence.pk/threads/amca-cancelled','Defence.pk: AMCA program reportedly cancelled','Defence.pk thread claiming AMCA (Advanced Medium Combat Aircraft) program cancelled due to cost overruns. Thread cites unnamed sources. No official confirmation from DRDO or IAF. Post gaining traction despite being unverified.',md5('iaf-ci-50'),'en',NOW()-INTERVAL '10 days',40.0,'iaf-cl-06','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"Defence.pk","author_id":"iaf-src-07","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.6,"label":"negative"},"keywords":["AMCA","cancelled","DRDO","unverified","cost overruns"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_iaf'),

('iaf-ci-51','iaf-topic-02','iaf-src-13','https://t.me/airpower_india/248','AMCA cancellation claim debunked','Air Power India debunks AMCA cancellation rumor. DRDO ADA confirmed AMCA on track — first prototype rollout scheduled 2028. Defence.pk post traces to same network as @fake_iaf_leaks. Pattern of coordinated anti-India defence narratives.',md5('iaf-ci-51'),'en',NOW()-INTERVAL '9 days',45.0,'iaf-cl-06','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"@airpower_india","author_id":"airpower_india","engagement":{"likes":89,"comments":56,"shares":0,"views":2400,"forwards":30},"sentiment":{"compound":0.3,"label":"positive"},"keywords":["AMCA","debunk","DRDO","@fake_iaf_leaks","prototype"]}'::jsonb,NOW()-INTERVAL '9 days',NOW(),'org_iaf'),

('iaf-ci-52','iaf-topic-02','iaf-src-12','https://t.me/iaf_disinfo_alert/90','Pattern: Tejas/AMCA narratives from same network','IAF Disinfo Alert analysis: Tejas failure narratives and AMCA cancellation rumors originate from same amplification network as Rafale deepfakes. Timing coordinated — new narrative drops every 48-72 hours to maintain momentum. @fake_iaf_leaks links confirmed.',md5('iaf-ci-52'),'en',NOW()-INTERVAL '7 days',50.0,'iaf-cl-06','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"@iaf_disinfo_alert","author_id":"iaf_disinfo_alert","engagement":{"likes":34,"comments":23,"shares":0,"views":980,"forwards":14},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Tejas","AMCA","@fake_iaf_leaks","network","coordinated"]}'::jsonb,NOW()-INTERVAL '7 days',NOW(),'org_iaf'),

('iaf-ci-53','iaf-topic-02','iaf-src-14','https://instagram.com/p/hal_tejas_memes','Instagram meme campaign mocking HAL','Military Aviation IG shares series of memes mocking HAL Tejas production delays. Format matches templates from @fake_iaf_leaks network. Professional quality graphics suggest organized production, not organic user content.',md5('iaf-ci-53'),'en',NOW()-INTERVAL '5 days',52.0,'iaf-cl-06','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"@mil_aviation_ig","author_id":"mil_aviation_ig","engagement":{"likes":1200,"comments":345,"shares":456,"views":25000},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["HAL","Tejas","memes","@fake_iaf_leaks","organized"]}'::jsonb,NOW()-INTERVAL '5 days',NOW(),'org_iaf'),

('iaf-ci-54','iaf-topic-02','iaf-src-15','https://reddit.com/r/IndianDefence/hal_delays','Reddit thread questioning IAF indigenous programs','Defence Forum India thread with 300+ comments debating HAL production capability. Mix of genuine criticism and seeded disinformation. Accounts created within last 30 days pushing most negative narratives. Moderators flagging coordinated activity.',md5('iaf-ci-54'),'en',NOW()-INTERVAL '3 days',35.0,'iaf-cl-06','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"r/IndianDefence","author_id":"iaf-src-15","engagement":{"likes":250,"comments":310,"shares":78,"views":15000},"sentiment":{"compound":-0.35,"label":"negative"},"keywords":["HAL","production","coordinated","disinformation","accounts"]}'::jsonb,NOW()-INTERVAL '3 days',NOW(),'org_iaf'),

('iaf-ci-55','iaf-topic-02','iaf-src-04','https://www.livefistdefence.com/hal-tejas-production','LiveFist: HAL Tejas production on track — 8 aircraft in Q1 2026','LiveFist exclusive: HAL delivered 8 Tejas Mk1A in Q1 2026, ahead of schedule. New production line at Nashik operational. Counters disinformation narratives about delays. IAF expects full squadron strength by December 2026.',md5('iaf-ci-55'),'en',NOW()-INTERVAL '2 days',74.0,'iaf-cl-06','{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf","author_handle":"LiveFist Defence","author_id":"iaf-src-04","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.55,"label":"positive"},"keywords":["HAL","Tejas","production","Mk1A","on track"]}'::jsonb,NOW()-INTERVAL '2 days',NOW(),'org_iaf')

ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 5. Extracted Entities (NER results)
-- ==========================================================================
INSERT INTO extracted_entities (id, content_item_id, entity_type, entity_text, created_at, labels) VALUES
-- J-20 cluster entities
('iaf-ent-001','iaf-ci-01','GPE','Hotan',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-002','iaf-ci-01','GPE','Xinjiang',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-003','iaf-ci-01','ORG','PLAAF',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-004','iaf-ci-02','ORG','PLAAF Western Theatre Command',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-005','iaf-ci-03','GPE','Kashgar',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-006','iaf-ci-03','GPE','Ladakh',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-007','iaf-ci-04','GPE','Aksai Chin',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-008','iaf-ci-05','PRODUCT','WS-15',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-009','iaf-ci-07','ORG','Bellingcat',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-010','iaf-ci-09','PRODUCT','AMCA',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-011','iaf-ci-09','PRODUCT','Su-30MKI',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
-- UAV cluster entities
('iaf-ent-012','iaf-ci-13','PRODUCT','WZ-7 Soaring Dragon',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-013','iaf-ci-14','PRODUCT','Wing Loong III',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-014','iaf-ci-16','PRODUCT','GJ-11 Sharp Sword',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-015','iaf-ci-16','GPE','Shigatse',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-016','iaf-ci-19','ORG','AVIC',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
-- Deepfake cluster entities
('iaf-ent-017','iaf-ci-21','TELEGRAM_HANDLE','fake_iaf_leaks',NOW(),'{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
('iaf-ent-018','iaf-ci-22','PRODUCT','Rafale',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-019','iaf-ci-25','ORG','Bellingcat',NOW(),'{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
('iaf-ent-020','iaf-ci-26','PRODUCT','Tejas',NOW(),'{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
('iaf-ent-021','iaf-ci-28','ORG','IAF PRD',NOW(),'{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
('iaf-ent-022','iaf-ci-28','ORG','CERT-In',NOW(),'{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
('iaf-ent-023','iaf-ci-29','PHONE_INTL','+852',NOW(),'{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
-- PAF cluster entities
('iaf-ent-024','iaf-ci-31','GPE','Kamra',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-025','iaf-ci-31','PRODUCT','KLJ-7A',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-026','iaf-ci-31','PRODUCT','PL-15',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-027','iaf-ci-33','ORG','SIPRI',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-028','iaf-ci-34','GPE','Skardu',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-029','iaf-ci-34','EVENT','Shaheen-X',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-030','iaf-ci-36','PRODUCT','J-10CP',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
-- Tibet airbase entities
('iaf-ent-031','iaf-ci-41','GPE','Ngari Gunsa',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-032','iaf-ci-42','GPE','Lhasa Gonggar',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-033','iaf-ci-43','GPE','Shigatse',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-034','iaf-ci-45','PRODUCT','HQ-9B',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
('iaf-ent-035','iaf-ci-45','PRODUCT','YLC-8E',NOW(),'{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
-- HAL/DRDO misinfo entities
('iaf-ent-036','iaf-ci-50','ORG','DRDO ADA',NOW(),'{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
('iaf-ent-037','iaf-ci-51','ORG','DRDO ADA',NOW(),'{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
('iaf-ent-038','iaf-ci-55','ORG','HAL',NOW(),'{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
('iaf-ent-039','iaf-ci-55','GPE','Nashik',NOW(),'{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 6. Identifier Clusters (Engine C)
-- ==========================================================================
INSERT INTO identifier_clusters (id, topic_id, identifier_type, identifier_value, source_count, content_item_count, first_seen_at, last_seen_at, created_at, updated_at, labels) VALUES
    ('iaf-ic-01', 'iaf-topic-02', 'TELEGRAM_HANDLE', 'fake_iaf_leaks', 4, 6,
     NOW()-INTERVAL '15 days', NOW()-INTERVAL '5 days', NOW()-INTERVAL '15 days', NOW(),
     '{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb),
    ('iaf-ic-02', 'iaf-topic-01', 'TELEGRAM_HANDLE', 'china_mil_watch', 1, 5,
     NOW()-INTERVAL '26 days', NOW()-INTERVAL '12 days', NOW()-INTERVAL '26 days', NOW(),
     '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb),
    ('iaf-ic-03', 'iaf-topic-01', 'AIRCRAFT_ID', 'J-20 serial 78271', 3, 3,
     NOW()-INTERVAL '26 days', NOW()-INTERVAL '16 days', NOW()-INTERVAL '26 days', NOW(),
     '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO identifier_cluster_items (identifier_cluster_id, content_item_id, source_id) VALUES
    -- @fake_iaf_leaks across disinfo items
    ('iaf-ic-01', 'iaf-ci-21', 'iaf-src-12'),
    ('iaf-ic-01', 'iaf-ci-23', 'iaf-src-15'),
    ('iaf-ic-01', 'iaf-ci-25', 'iaf-src-16'),
    ('iaf-ic-01', 'iaf-ci-26', 'iaf-src-13'),
    ('iaf-ic-01', 'iaf-ci-29', 'iaf-src-12'),
    ('iaf-ic-01', 'iaf-ci-52', 'iaf-src-12'),
    -- @china_mil_watch forwarding pattern
    ('iaf-ic-02', 'iaf-ci-03', 'iaf-src-10'),
    ('iaf-ic-02', 'iaf-ci-11', 'iaf-src-10'),
    ('iaf-ic-02', 'iaf-ci-14', 'iaf-src-10'),
    ('iaf-ic-02', 'iaf-ci-46', 'iaf-src-10'),
    ('iaf-ic-02', 'iaf-ci-04', 'iaf-src-09'),
    -- J-20 serial 78271 tracked across sources
    ('iaf-ic-03', 'iaf-ci-03', 'iaf-src-10'),
    ('iaf-ic-03', 'iaf-ci-04', 'iaf-src-09'),
    ('iaf-ic-03', 'iaf-ci-11', 'iaf-src-10')
ON CONFLICT DO NOTHING;

-- ==========================================================================
-- 7. Signals (5)
-- ==========================================================================
INSERT INTO signals (id, topic_id, cluster_id, signal_type, description, evidence, status, created_at, updated_at, labels) VALUES
    ('iaf-sig-01', 'iaf-topic-01', 'iaf-cl-01', 'multi_source_convergence',
     'J-20 deployment near LAC confirmed by 5 independent sources (Jane''s, SCMP, Bellingcat, @china_mil_watch, @defence_osint)',
     '{"independent_source_count":5,"severity":"HIGH","platforms":["rss","web","telegram"]}'::jsonb,
     'new', NOW()-INTERVAL '20 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"iaf"}'::jsonb),
    ('iaf-sig-02', 'iaf-topic-02', 'iaf-cl-03', 'threshold_breach',
     'Coordinated deepfake campaign detected across 4 platforms — Telegram, Reddit, Instagram, web. @fake_iaf_leaks identified as origin.',
     '{"independent_source_count":4,"severity":"CRITICAL","deepfake_score":0.94,"platforms":["telegram","reddit","instagram","web"]}'::jsonb,
     'new', NOW()-INTERVAL '12 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"iaf"}'::jsonb),
    ('iaf-sig-03', 'iaf-topic-03', 'iaf-cl-04', 'multi_source_convergence',
     'PAF JF-17 Block 3 induction confirmed by Jane''s, SIPRI, and @paf_tracker with corroborating AESA radar specifications',
     '{"independent_source_count":3,"severity":"MEDIUM","platforms":["rss","web","telegram"]}'::jsonb,
     'new', NOW()-INTERVAL '16 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"iaf"}'::jsonb),
    ('iaf-sig-04', 'iaf-topic-01', 'iaf-cl-05', 'multi_source_convergence',
     'Tibet airbase infrastructure expansion confirmed across 4 independent sources — Bellingcat, Jane''s, @china_mil_watch, SCMP',
     '{"independent_source_count":4,"severity":"HIGH","platforms":["web","rss","telegram"]}'::jsonb,
     'new', NOW()-INTERVAL '14 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"iaf"}'::jsonb),
    ('iaf-sig-05', 'iaf-topic-02', NULL, 'identifier_convergence',
     'Telegram handle @fake_iaf_leaks identified across 4 independent sources as coordinated amplification node for anti-IAF disinformation',
     '{"independent_source_count":4,"severity":"HIGH","identifier_type":"TELEGRAM_HANDLE","identifier_value":"fake_iaf_leaks"}'::jsonb,
     'new', NOW()-INTERVAL '10 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"iaf"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 8. Keyword Alert Rules + Triggers
-- ==========================================================================
INSERT INTO keyword_alert_rules (id, topic_id, keywords, match_mode, is_active, notify_websocket, created_by, org_id, created_at, updated_at, labels) VALUES
    ('iaf-alert-01', 'iaf-topic-01', ARRAY['J-20', 'stealth', 'Hotan', 'WS-15', 'fifth-gen'], 'any', true, true, 'iaf-user-analyst', 'org_iaf', NOW()-INTERVAL '28 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-alert-02', 'iaf-topic-02', ARRAY['deepfake', 'fabricated', 'propaganda', 'fake video', 'AI-generated'], 'any', true, true, 'iaf-user-analyst', 'org_iaf', NOW()-INTERVAL '28 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-alert-03', 'iaf-topic-03', ARRAY['JF-17', 'Block 3', 'PL-15', 'PAF', 'Shaheen'], 'any', true, true, 'iaf-user-analyst', 'org_iaf', NOW()-INTERVAL '28 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-alert-04', 'iaf-topic-01', ARRAY['airbase', 'runway', 'Tibet', 'Ngari', 'hardened shelter'], 'any', true, true, 'iaf-user-analyst', 'org_iaf', NOW()-INTERVAL '28 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO keyword_alert_triggers (id, rule_id, content_item_id, matched_keywords, triggered_at, labels) VALUES
    -- J-20/stealth alerts
    ('iaf-trig-01', 'iaf-alert-01', 'iaf-ci-01', ARRAY['J-20','Hotan'], NOW()-INTERVAL '28 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-trig-02', 'iaf-alert-01', 'iaf-ci-03', ARRAY['J-20'], NOW()-INTERVAL '26 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-trig-03', 'iaf-alert-01', 'iaf-ci-05', ARRAY['WS-15'], NOW()-INTERVAL '24 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-trig-04', 'iaf-alert-01', 'iaf-ci-10', ARRAY['J-20','Hotan'], NOW()-INTERVAL '18 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    -- Deepfake alerts
    ('iaf-trig-05', 'iaf-alert-02', 'iaf-ci-21', ARRAY['fabricated'], NOW()-INTERVAL '15 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-trig-06', 'iaf-alert-02', 'iaf-ci-22', ARRAY['deepfake','AI-generated'], NOW()-INTERVAL '14 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-trig-07', 'iaf-alert-02', 'iaf-ci-26', ARRAY['deepfake'], NOW()-INTERVAL '11 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    -- PAF alerts
    ('iaf-trig-08', 'iaf-alert-03', 'iaf-ci-31', ARRAY['JF-17','Block 3','PL-15'], NOW()-INTERVAL '20 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-trig-09', 'iaf-alert-03', 'iaf-ci-34', ARRAY['PAF','Shaheen','PL-15'], NOW()-INTERVAL '16 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-trig-10', 'iaf-alert-03', 'iaf-ci-39', ARRAY['Shaheen','PL-15'], NOW()-INTERVAL '6 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    -- Airbase/Tibet alerts
    ('iaf-trig-11', 'iaf-alert-04', 'iaf-ci-41', ARRAY['runway','Ngari'], NOW()-INTERVAL '22 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-trig-12', 'iaf-alert-04', 'iaf-ci-42', ARRAY['hardened shelter'], NOW()-INTERVAL '20 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb),
    ('iaf-trig-13', 'iaf-alert-04', 'iaf-ci-44', ARRAY['Tibet','airbase'], NOW()-INTERVAL '16 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"iaf"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 9. Forwarding Chains (Telegram network graph)
-- ==========================================================================
-- @china_mil_watch → @defence_osint (LAC content)
UPDATE content_items SET forwarded_from_channel_name = 'china_mil_watch' WHERE id IN ('iaf-ci-04', 'iaf-ci-12', 'iaf-ci-16');
-- @iaf_disinfo_alert → @airpower_india (deepfake alerts)
UPDATE content_items SET forwarded_from_channel_name = 'iaf_disinfo_alert' WHERE id IN ('iaf-ci-26', 'iaf-ci-51');
-- @paf_tracker → @defence_osint (PAF content)
UPDATE content_items SET forwarded_from_channel_name = 'paf_tracker' WHERE id IN ('iaf-ci-36');

-- ==========================================================================
-- 10. Vision Analysis Job (deepfake detection)
-- ==========================================================================
INSERT INTO analysis_jobs (
    id, job_type, topic_id, status,
    payload, result, error, labels, created_at, updated_at
) VALUES (
    'iaf-vision-01',
    'vision_analysis',
    'iaf-topic-02',
    'completed',
    '{"content_item_id": "iaf-ci-21"}'::jsonb,
    '{
        "deepfake_score": 0.94,
        "deepfake_model": "facetorch",
        "objects_detected": ["aircraft", "missile", "explosion"],
        "yolo_model": "yolov8n",
        "exif_anomalies": ["GPS stripped", "software: Runway Gen-3", "creation_date inconsistent"],
        "phash": "a1b2c3d4e5f67890",
        "temporal_artifacts": ["frame 0:14 — texture discontinuity", "frame 0:23 — shadow direction mismatch"],
        "source_footage_match": "French Air Force 2019 training exercise, Istres AB"
    }'::jsonb,
    NULL,
    '{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb,
    NOW() - INTERVAL '14 days',
    NOW() - INTERVAL '14 days'
) ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 11. Credibility Audit Log
-- ==========================================================================
INSERT INTO credibility_audit_log (id, source_id, old_score, new_score, reason, changed_by, created_at, org_id) VALUES
(
    'iaf-audit-01',
    'iaf-src-06',
    50.0,
    35.0,
    'Source shared unverified deepfake content 3 times in 30 days and amplified AMCA cancellation rumor — auto-downgrade',
    'system:credibility-auto-update',
    NOW() - INTERVAL '10 days',
    'org_iaf'
) ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 12. Sample Report (Intelligence Brief)
-- ==========================================================================
INSERT INTO reports (
    id, topic_id, report_type,
    time_window_start, time_window_end, credibility_min_filter,
    content_md, generated_at, source_snapshot, content_item_count,
    labels, created_at, updated_at
) VALUES (
    'iaf-report-01',
    'iaf-topic-01',
    'intelligence_brief',
    NOW() - INTERVAL '30 days',
    NOW(),
    30.0,
    E'<!-- report-v2 -->\n## BLUF (Bottom Line Up Front)\n\nPLAAF has established operational J-20 stealth fighter presence at Hotan and Kashgar airbases with 24/7 alert readiness, significantly altering the air power balance along the LAC. Concurrent expansion of UAV operations (WZ-7, Wing Loong III) and Tibet airbase infrastructure (Ngari Gunsa, Lhasa Gonggar, Shigatse) indicates sustained force projection buildup. Assessment confidence: HIGH.\n\n## Key Findings\n\n### 1. J-20 Stealth Deployment (5 independent sources)\n- 8+ J-20 confirmed at Hotan, 4 at Kashgar forward operating base\n- WS-15 engine upgrade extends combat radius to 2,200 km — covering all of northern Ladakh\n- 24/7 alert readiness achieved (hangar pattern analysis over 14 days)\n- Night operations capability confirmed via thermal satellite imagery\n- Serial numbers 78271 and 78273 tracked across multiple passes\n\n### 2. PLAAF Drone Buildup (4 independent sources)\n- WZ-7 Soaring Dragon ISR at 65,000 ft near Ladakh airspace\n- Wing Loong III armed UCAVs at Kashgar (strike capable, 480 km radius)\n- GJ-11 stealth UCAV test reports from Shigatse (unconfirmed)\n- Drone sorties increase 3x during Indian military exercises\n- PLAAF ordered 120 additional Wing Loong III platforms\n\n### 3. Tibet Airbase Expansion (4 independent sources)\n- Ngari Gunsa: new 3,500m runway operational\n- Lhasa Gonggar: 16 new hardened aircraft shelters\n- Shigatse: underground fuel and ammunition depot\n- Combined capacity: 150+ combat aircraft across 5 bases\n- HQ-9B SAM and YLC-8E counter-stealth radar deployed\n\n## Source Assessment\n\n| Source | Credibility | Contribution |\n|--------|------------|-------------|\n| Jane''s Defence | 91% | J-20 confirmation, Wing Loong procurement |\n| Bellingcat | 85% | Geospatial analysis, amplification network |\n| The War Zone | 80% | WS-15 analysis, Tibet network assessment |\n| Indian Defence Review | 76% | Strategic implications analysis |\n| SCMP | 72% | PLA air defence deployment |\n| LiveFist | 74% | Night ops, construction timeline |\n\n## Recommended Actions\n\n1. Accelerate AMCA program timeline — stealth parity critical\n2. Fast-track integrated counter-UAS network along LAC\n3. Evaluate additional Rafale squadron acquisition\n4. Enhance satellite ISR coverage of Hotan/Kashgar/Tibet bases\n5. Establish standing air patrol protocols for LAC sector\n\n## Confidence Level\n\nHIGH. Assessment based on 5 independent high-credibility sources with satellite imagery corroboration. J-20 deployment confirmed by Jane''s (91%), Bellingcat (85%), and SCMP (72%). Infrastructure expansion independently verified by geospatial analysis.\n\n*This brief was generated automatically by Anveshak. Analyst review recommended before dissemination.*',
    NOW() - INTERVAL '3 days',
    '{
        "iaf-src-01": {"name": "Janes Defence Weekly", "credibility_score": 91.0},
        "iaf-src-02": {"name": "The War Zone", "credibility_score": 80.0},
        "iaf-src-03": {"name": "Indian Defence Review", "credibility_score": 76.0},
        "iaf-src-04": {"name": "LiveFist Defence", "credibility_score": 74.0},
        "iaf-src-05": {"name": "SCMP Defence", "credibility_score": 72.0},
        "iaf-src-16": {"name": "Bellingcat OSINT", "credibility_score": 85.0}
    }'::jsonb,
    28,
    '{"classification":"RESTRICTED","domain":"air_intelligence","owner_org":"iaf","topic_id":"iaf-topic-01"}'::jsonb,
    NOW() - INTERVAL '3 days',
    NOW() - INTERVAL '3 days'
) ON CONFLICT (id) DO NOTHING;

COMMIT;

-- ==========================================================================
-- Verify counts
-- ==========================================================================
SELECT 'Topics' AS entity, COUNT(*) FROM topics WHERE id LIKE 'iaf-topic-%'
UNION ALL SELECT 'Sources', COUNT(*) FROM sources WHERE id LIKE 'iaf-src-%'
UNION ALL SELECT 'Content Items', COUNT(*) FROM content_items WHERE id LIKE 'iaf-ci-%'
UNION ALL SELECT 'Clusters', COUNT(*) FROM narrative_clusters WHERE id LIKE 'iaf-cl-%'
UNION ALL SELECT 'Entities', COUNT(*) FROM extracted_entities WHERE id LIKE 'iaf-ent-%'
UNION ALL SELECT 'ID Clusters', COUNT(*) FROM identifier_clusters WHERE id LIKE 'iaf-ic-%'
UNION ALL SELECT 'Signals', COUNT(*) FROM signals WHERE id LIKE 'iaf-sig-%'
UNION ALL SELECT 'Alert Rules', COUNT(*) FROM keyword_alert_rules WHERE id LIKE 'iaf-alert-%'
UNION ALL SELECT 'Alert Triggers', COUNT(*) FROM keyword_alert_triggers WHERE id LIKE 'iaf-trig-%'
UNION ALL SELECT 'Reports', COUNT(*) FROM reports WHERE id LIKE 'iaf-report-%'
UNION ALL SELECT 'Vision Jobs', COUNT(*) FROM analysis_jobs WHERE id LIKE 'iaf-vision-%';
