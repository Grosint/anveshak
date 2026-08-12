-- ==========================================================================
-- Bidadi Demo — MHA Intelligence Coordination: Bidadi Township Operations
-- ==========================================================================
-- Scenario: MHA monitoring three concurrent intelligence threads on Bidadi:
-- 1. Civil Unrest & Protest Coordination (farmer displacement, escalation)
-- 2. Land Deal Nexus & Financial Irregularities (SEBI, denotification)
-- 3. Foreign Linkages & Information Warfare (FCRA, digital campaigns)
--
-- Org: org_bidadi (MHA Intelligence Coordination)
-- User: demo_bidadi@anveshak.local / AnveshakDemo2024!
--
-- Idempotent: all INSERTs use ON CONFLICT DO NOTHING.
-- Run: docker exec -i anveshak-postgres-1 psql -U anveshak -d anveshak < scripts/seed_bidadi_demo.sql
-- ==========================================================================

BEGIN;

-- ==========================================================================
-- 0. Organization + User
-- ==========================================================================
INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
VALUES (
    'org_bidadi',
    'MHA Intelligence Coordination',
    'mha-bidadi',
    NOW(), NOW(),
    '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb
) ON CONFLICT (id) DO NOTHING;

-- Password: AnveshakDemo2024!
INSERT INTO users (id, username, password_hash, role, org_id, created_at, updated_at, labels)
VALUES (
    'bidadi-user-analyst',
    'demo_bidadi@anveshak.local',
    '$2b$12$exK0vBQZHOMCPjg37GTJZ.AtYqz1NI5SXwMLrWjnPvP2IqZMZKaei',
    'analyst',
    'org_bidadi',
    NOW(), NOW(),
    '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb
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
    'bidadi-topic-01',
    'Bidadi Township — Civil Unrest & Protest Coordination',
    ARRAY['Bidadi', 'GBIT', 'Bidadi Township', 'Save Bidadi', 'Bidadi protest',
          'Byramangala', 'farmer protest Karnataka', 'AI city', 'land acquisition Ramanagara',
          'Bidadi Chalo', 'blood protest', 'GBDA', 'Mandalahalli', 'Kempegowdanapalya',
          'broom protest', 'Punjab-style agitation'],
    3, 2, 'active', ARRAY['en', 'kn'], 15.0,
    '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb,
    NOW() - INTERVAL '45 days', NOW(), 'org_bidadi'
),
(
    'bidadi-topic-02',
    'Bidadi — Land Deal Nexus & Financial Irregularities',
    ARRAY['Sobha Developers', 'SEBI', 'Shivakumar property', 'Benniganahalli',
          'GBDA tender', 'HUDCO', 'Kumaraswamy land', 'Kethaganahalli', 'NICE Road',
          'Puravankara', 'denotification', 'land mafia', 'DK Suresh', 'survey number'],
    3, 2, 'active', ARRAY['en', 'kn'], 15.0,
    '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb,
    NOW() - INTERVAL '45 days', NOW(), 'org_bidadi'
),
(
    'bidadi-topic-03',
    'Bidadi — Foreign Linkages & Information Warfare',
    ARRAY['KRRS', 'La Via Campesina', 'Amrita Bhoomi', 'FCRA', 'foreign funding farmer',
          'Save Bidadi', 'Vijay Nishanth', 'vruksha', 'change.org', 'SaveBidadi',
          'BidadiChalo', 'Agroecology Fund', 'Christensen Fund', 'narrative warfare'],
    3, 2, 'active', ARRAY['en', 'kn'], 15.0,
    '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb,
    NOW() - INTERVAL '45 days', NOW(), 'org_bidadi'
)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 2. Sources (15)
-- ==========================================================================
INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, health_status, labels, created_at, updated_at, org_id) VALUES
    -- ── Official / Gov ──
    ('bidadi-src-01', 'Karnataka State Gazette',        'https://egazette.karnataka.gov.in',          'web',  92.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-02', 'SEBI Enforcement Orders',        'https://www.sebi.gov.in/enforcement/orders.html', 'web', 95.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-03', 'NGO DARPAN Portal',              'https://ngodarpan.gov.in',                   'web',  90.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),

    -- ── RSS / News ──
    ('bidadi-src-04', 'Deccan Herald — Karnataka',      'https://www.deccanherald.com/karnataka',     'web',  82.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-05', 'The News Minute',                'https://www.thenewsminute.com/karnataka',    'web',  78.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-06', 'The Hindu — Karnataka',          'https://www.thehindu.com/news/national/karnataka/feeder/default.rss', 'rss', 85.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-07', 'NDTV India News',                'https://feeds.feedburner.com/ndtvnews-india-news', 'rss', 75.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-08', 'Indian Express',                 'https://indianexpress.com/section/india/feed/', 'rss', 78.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-09', 'The Quint',                      'https://www.thequint.com',                   'web',  76.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),

    -- ── Telegram ──
    ('bidadi-src-10', 'KRRS Haveri District (Telegram)', 'HaveriRaitaSangaKRRS',                     'telegram', 22.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-11', 'ಸ್ವಾಭಿಮಾನ ಸ್ವಾತಂತ್ರ ಸಮಾನತೆ (Telegram)', 'swabhimana_kannada',              'telegram', 15.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),

    -- ── Social / Petition ──
    ('bidadi-src-12', 'Save Bidadi Change.org',         'https://www.change.org/p/save-bidadi',       'web',  35.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-13', 'X/@DKShivakumar',                'DKShivakumar',                               'web',  60.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-14', 'X/@NikhilKSwamy',                'NikhilKSwamy',                               'web',  45.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),
    ('bidadi-src-15', 'X/@vijayvruksha',                'vijayvruksha',                               'web',  40.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_bidadi'),

    -- ── Low-credibility anonymous account ──
    ('bidadi-src-16', 'X/@BidadiExpose247',              'BidadiExpose247',                            'web',  18.0, true, 'healthy', '{"classification":"OPEN","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb, NOW()-INTERVAL '10 days', NOW(), 'org_bidadi')
ON CONFLICT (id) DO NOTHING;

-- org_sources
INSERT INTO org_sources (org_id, source_id) VALUES
    ('org_bidadi','bidadi-src-01'),('org_bidadi','bidadi-src-02'),('org_bidadi','bidadi-src-03'),
    ('org_bidadi','bidadi-src-04'),('org_bidadi','bidadi-src-05'),('org_bidadi','bidadi-src-06'),
    ('org_bidadi','bidadi-src-07'),('org_bidadi','bidadi-src-08'),('org_bidadi','bidadi-src-09'),
    ('org_bidadi','bidadi-src-10'),('org_bidadi','bidadi-src-11'),('org_bidadi','bidadi-src-12'),
    ('org_bidadi','bidadi-src-13'),('org_bidadi','bidadi-src-14'),('org_bidadi','bidadi-src-15'),
    ('org_bidadi','bidadi-src-16')
ON CONFLICT DO NOTHING;

-- topic_sources
-- Topic 1: Civil Unrest — news, telegram, social, gazette
INSERT INTO topic_sources (topic_id, source_id) VALUES
    ('bidadi-topic-01','bidadi-src-01'),('bidadi-topic-01','bidadi-src-04'),('bidadi-topic-01','bidadi-src-05'),
    ('bidadi-topic-01','bidadi-src-06'),('bidadi-topic-01','bidadi-src-07'),('bidadi-topic-01','bidadi-src-08'),
    ('bidadi-topic-01','bidadi-src-09'),('bidadi-topic-01','bidadi-src-10'),('bidadi-topic-01','bidadi-src-11'),
    ('bidadi-topic-01','bidadi-src-14')
ON CONFLICT DO NOTHING;
-- Topic 2: Land Nexus — SEBI, news, X handles
INSERT INTO topic_sources (topic_id, source_id) VALUES
    ('bidadi-topic-02','bidadi-src-01'),('bidadi-topic-02','bidadi-src-02'),('bidadi-topic-02','bidadi-src-04'),
    ('bidadi-topic-02','bidadi-src-05'),('bidadi-topic-02','bidadi-src-06'),('bidadi-topic-02','bidadi-src-07'),
    ('bidadi-topic-02','bidadi-src-08'),('bidadi-topic-02','bidadi-src-13'),('bidadi-topic-02','bidadi-src-14'),
    ('bidadi-topic-02','bidadi-src-16')
ON CONFLICT DO NOTHING;
-- Topic 3: Foreign Linkages — NGO DARPAN, news, telegram, petition, X
INSERT INTO topic_sources (topic_id, source_id) VALUES
    ('bidadi-topic-03','bidadi-src-03'),('bidadi-topic-03','bidadi-src-04'),('bidadi-topic-03','bidadi-src-05'),
    ('bidadi-topic-03','bidadi-src-06'),('bidadi-topic-03','bidadi-src-07'),('bidadi-topic-03','bidadi-src-08'),
    ('bidadi-topic-03','bidadi-src-10'),('bidadi-topic-03','bidadi-src-12'),('bidadi-topic-03','bidadi-src-13'),
    ('bidadi-topic-03','bidadi-src-15')
ON CONFLICT DO NOTHING;


-- ==========================================================================
-- 3. Narrative Clusters (12)
-- ==========================================================================
INSERT INTO narrative_clusters (id, topic_id, label, item_count, independent_source_count, executive_summary, created_at, updated_at, labels) VALUES
    -- ── Topic 1: Civil Unrest & Protest Coordination (4 clusters) ──
    ('bidadi-cl-01', 'bidadi-topic-01', 'Farmer Displacement & Livelihood Destruction', 6, 5,
     '10,580 farmers across 9 villages face displacement for Rs 18,133 crore AI township. Dairy, sericulture, and horticulture livelihoods at stake. 460+ day protest at Byramangala with sustained mobilization from Mandalahalli, Kempegowdanapalya, and surrounding villages.',
     NOW()-INTERVAL '40 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-cl-02', 'bidadi-topic-01', 'Political Weaponization of Protest', 5, 4,
     'BJP Freedom Park rally and JD(S) padayatra indicate coordinated opposition exploitation of farmer grievance. Cross-party meetings in Bengaluru suggest organized amplification strategy beyond organic protest.',
     NOW()-INTERVAL '35 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-cl-03', 'bidadi-topic-01', 'Escalation Rhetoric & Violence Markers', 5, 4,
     'Blood protest, mass suicide threats, Punjab-style agitation language detected across multiple sources. Escalation from peaceful demonstration to confrontational rhetoric. "Give us poison" messaging indicates radicalization risk.',
     NOW()-INTERVAL '30 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-cl-04', 'bidadi-topic-01', 'Women''s Resistance & SHG Mobilization', 4, 4,
     'Mandalahalli broom incident — women chase away survey officials. Self-help group involvement in protest coordination. FIRs registered against women protesters. Priyank Kharge hints at dropping cases — political sensitivity.',
     NOW()-INTERVAL '28 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),

    -- ── Topic 2: Land Deal Nexus & Financial Irregularities (4 clusters) ──
    ('bidadi-cl-05', 'bidadi-topic-02', 'Sobha-Shivakumar SEBI Settlement', 5, 4,
     'SEBI order SO/AA/HP/2022-23/6654-6658 — Rs 2,92,50,000 settlement. Noticees Ravi PNC Menon (Chairman) and Jagdish Chandra Sharma (MD) for misrepresentation of receivables related to DK Shivakumar residence construction.',
     NOW()-INTERVAL '38 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-cl-06', 'bidadi-topic-02', 'GBDA Formation & Insider Appointments', 5, 4,
     'Rs 26 crore tender floated for Detailed Project Report. HUDCO offers Rs 21,000 crore loan. DK Suresh (CM brother) appointed GBDA member. P Rajendra Cholan as commissioner — institutional capture indicators.',
     NOW()-INTERVAL '35 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-cl-07', 'bidadi-topic-02', 'Kumaraswamy Family Land Paradox', 5, 4,
     'Kethaganahalli Sy No 7, 8, 9, 10, 16, 79 — HC orders encroachment report. Wife Anita Kumaraswamy holds 36-37 acres in acquisition zone. Family opposing project publicly while 70% of landowners including family have sought compensation.',
     NOW()-INTERVAL '30 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-cl-08', 'bidadi-topic-02', 'Benniganahalli Denotification Case', 5, 4,
     'Survey No 50/2 Benniganahalli, 4.2 acres. Rs 1.62 crore purchase, Puravankara JV, Lokayukta complaint by Kabbale Gowda and TJ Abraham. SC grants relief to DKS and BSY. HC calls BMIC one of state''s biggest scams.',
     NOW()-INTERVAL '25 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),

    -- ── Topic 3: Foreign Linkages & Information Warfare (4 clusters) ──
    ('bidadi-cl-09', 'bidadi-topic-03', 'KRRS–La Via Campesina Foreign Funding', 5, 4,
     'Amrita Bhoomi registration 129/1997-98 and KRRS registration RMG-S20-2013-14 share same Rajarajeshwari Nagar 560098 locality. Italian, US, UK grants via Agroecology Fund. Christensen Fund and 11th Hour Project donors.',
     NOW()-INTERVAL '35 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-cl-10', 'bidadi-topic-03', 'Save Bidadi Digital Campaign', 4, 4,
     'Environmental activist Vijay Nishanth (@vijayvruksha) spearheads Change.org petition — 79,329 signatures. Project Vruksha Foundation linked. DK Shivakumar tweets AI City branding while Dy CM Parameshwara says project not connected to any AI hub.',
     NOW()-INTERVAL '30 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-cl-11', 'bidadi-topic-03', 'Hashtag Amplification & Coordinated Messaging', 3, 3,
     '#SaveBidadi, #BidadiChalo, #BattleForBidadi trending. BJP-JDS coordination meeting in Bengaluru specifically about Bidadi Township — organized cross-party amplification strategy detected.',
     NOW()-INTERVAL '20 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-cl-12', 'bidadi-topic-03', 'Funding Absence as Intelligence Signal', 3, 3,
     'INTELLIGENCE GAP: 460-day protest, 10,000+ farmers, zero public crowdfunding detected. Compare Shaheen Bagh (crowdfunding within days), farm laws (public donation drives). Absence suggests party-funded or undisclosed funding hypothesis.',
     NOW()-INTERVAL '15 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb)
ON CONFLICT (id) DO NOTHING;


-- ==========================================================================
-- 4. Content Items
-- ==========================================================================

-- ── Topic 1, Cluster 1: Farmer Displacement & Livelihood Destruction (6 items) ──
INSERT INTO content_items (id, topic_id, source_id, url, raw_text, clean_text, content_hash, language, captured_at, credibility_score_at_capture, narrative_cluster_id, labels, created_at, updated_at, org_id) VALUES
('bidadi-ci-01','bidadi-topic-01','bidadi-src-04','https://www.deccanherald.com/karnataka/bidadi-460-day-protest','Give us poison instead: Inside the 460-day protest','Give us poison instead: Inside the 460-day protest against Bidadi AI township. Farmers in Byramangala and surrounding villages say they would rather die than lose their ancestral land. Over 10,580 farmers across 9 villages face displacement for the Rs 18,133 crore Greater Bengaluru Integrated Township project.',md5('bidadi-ci-01'),'en',NOW()-INTERVAL '40 days',82.0,'bidadi-cl-01','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["Bidadi","protest","farmers","displacement","GBIT","poison"]}'::jsonb,NOW()-INTERVAL '40 days',NOW(),'org_bidadi'),
('bidadi-ci-02','bidadi-topic-01','bidadi-src-09','https://www.thequint.com/news/bidadi-farmers-green-belt','Our Green Belt Will Turn Into Concrete Jungle: Bidadi Farmers Fight AI Township','Our Green Belt Will Turn Into Concrete Jungle: Bidadi Farmers Fight AI Township. Sericulture, dairy farming, and horticulture sustain 10,580 families across Byramangala, Mandalahalli, and Kempegowdanapalya. Farmers say the Rs 18,133 crore project will destroy their green belt forever.',md5('bidadi-ci-02'),'en',NOW()-INTERVAL '38 days',76.0,'bidadi-cl-01','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["Bidadi","green belt","farmers","AI township","sericulture","dairy"]}'::jsonb,NOW()-INTERVAL '38 days',NOW(),'org_bidadi'),
('bidadi-ci-03','bidadi-topic-01','bidadi-src-05','https://www.thenewsminute.com/karnataka/bidadi-ground-report','Ground Report: Bidadi farmers resist AI city land acquisition','Ground Report: Bidadi farmers resist AI city land acquisition. Revenue officials unable to complete survey due to farmer resistance. Women and elderly at forefront of protests. Silk and milk cooperatives say they will lose everything if 7,480 acres are acquired.',md5('bidadi-ci-03'),'en',NOW()-INTERVAL '35 days',78.0,'bidadi-cl-01','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Bidadi","ground report","land acquisition","survey","women","cooperatives"]}'::jsonb,NOW()-INTERVAL '35 days',NOW(),'org_bidadi'),
('bidadi-ci-04','bidadi-topic-01','bidadi-src-10','https://t.me/HaveriRaitaSangaKRRS/412','ಬಿಡದಿ ರೈತರ ಪ್ರತಿಭಟನೆ — ಮುಂದಿನ ಸಭೆ ಮಂಗಳವಾರ','ಬಿಡದಿ ರೈತರ ಪ್ರತಿಭಟನೆ ವೇಳಾಪಟ್ಟಿ: ಮಂಗಳವಾರ ಬೆಳಗ್ಗೆ 10 ಗಂಟೆಗೆ ಬೈರಮಂಗಲ ಗೇಟ್ ಬಳಿ ಸಭೆ. ಎಲ್ಲ ಗ್ರಾಮಗಳ ರೈತರು ಕಡ್ಡಾಯವಾಗಿ ಹಾಜರಾಗಬೇಕು. KRRS ಮಾರ್ಗದರ್ಶನ. Bidadi farmer protest schedule: Tuesday meeting at Byramangala gate, all villages must attend.',md5('bidadi-ci-04'),'kn',NOW()-INTERVAL '30 days',22.0,'bidadi-cl-01','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["ಬಿಡದಿ","ರೈತರು","ಪ್ರತಿಭಟನೆ","KRRS","Byramangala"]}'::jsonb,NOW()-INTERVAL '30 days',NOW(),'org_bidadi'),
('bidadi-ci-05','bidadi-topic-01','bidadi-src-06','https://www.thehindu.com/news/national/karnataka/bidadi-punjab-agitation','Farmers oppose Bidadi township, warn of Punjab-style agitation','Farmers oppose Bidadi township, warn of Punjab-style agitation. Karnataka Rajya Raitha Sangha leaders invoke the 2020-21 farm laws protest as a model. Demand complete withdrawal of land acquisition notification. Threaten to block Mysore-Bangalore highway.',md5('bidadi-ci-05'),'en',NOW()-INTERVAL '25 days',85.0,'bidadi-cl-01','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.65,"label":"negative"},"keywords":["Bidadi","Punjab-style","agitation","KRRS","highway blockade","farm laws"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_bidadi'),
('bidadi-ci-06','bidadi-topic-01','bidadi-src-07','https://feeds.feedburner.com/ndtvnews-bidadi-displacement','10,580 farmers across 9 villages face displacement for Rs 18,133 crore project','NDTV: 10,580 farmers across 9 villages face displacement for the Rs 18,133 crore Greater Bengaluru Integrated Township. Ramanagara district administration says project is for ''national interest.'' Farmers counter: ''Our land is our life.'' Protest enters 460th day.',md5('bidadi-ci-06'),'en',NOW()-INTERVAL '20 days',75.0,'bidadi-cl-01','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.55,"label":"negative"},"keywords":["NDTV","10580 farmers","9 villages","displacement","Rs 18133 crore","460 days"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_bidadi'),

-- ── Topic 1, Cluster 2: Political Weaponization of Protest (5 items) ──
('bidadi-ci-07','bidadi-topic-01','bidadi-src-08','https://indianexpress.com/karnataka/bjp-bidadi-protest','Karnataka BJP holds massive protest against Bidadi AI township','Indian Express: Karnataka BJP holds massive protest at Freedom Park against Bidadi AI township. State BJP president calls it ''biggest land grab in Karnataka history.'' Party mobilizes MLAs from Ramanagara, Channapatna, and Magadi constituencies.',md5('bidadi-ci-07'),'en',NOW()-INTERVAL '35 days',78.0,'bidadi-cl-02','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["BJP","Freedom Park","Bidadi","protest","land grab","MLAs"]}'::jsonb,NOW()-INTERVAL '35 days',NOW(),'org_bidadi'),
('bidadi-ci-08','bidadi-topic-01','bidadi-src-07','https://feeds.feedburner.com/ndtvnews-jds-padayatra','Save Bidadi: JDS youth wing announces 3-day padayatra','ANI/NDTV: JDS youth wing announces 3-day padayatra from Ramanagara to Bidadi. Nikhil Kumaraswamy to lead march. Party says ''we stand with farmers against this anti-people project.'' Police impose Section 144 along padayatra route.',md5('bidadi-ci-08'),'en',NOW()-INTERVAL '28 days',70.0,'bidadi-cl-02','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.45,"label":"negative"},"keywords":["JDS","padayatra","Nikhil Kumaraswamy","Ramanagara","Section 144"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_bidadi'),
('bidadi-ci-09','bidadi-topic-01','bidadi-src-04','https://www.deccanherald.com/karnataka/jds-padayatra-halted','Police halt JD(S) padayatra near Kanaminike Village','Deccan Herald: Police halt JD(S) padayatra near Kanaminike Village citing law and order concerns. Nikhil Kumaraswamy detained briefly. Farmers from Mandalahalli join padayatra en route. DC Thamanna issues prohibitory orders.',md5('bidadi-ci-09'),'en',NOW()-INTERVAL '20 days',80.0,'bidadi-cl-02','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["JDS","padayatra","Kanaminike","Nikhil Kumaraswamy","DC Thamanna","detained"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_bidadi'),
('bidadi-ci-10','bidadi-topic-01','bidadi-src-14','https://x.com/NikhilKSwamy/status/bidadi-scam','Rs 33,562 crore real estate scam snatching 7,480 acres from poor farmers','X/@NikhilKSwamy: ''Rs 33,562 crore real estate scam snatching 7,480 acres from poor farmers. This is not AI city — this is land mafia city. We will fight till the last acre is saved. #SaveBidadi #BidadiChalo''',md5('bidadi-ci-10'),'en',NOW()-INTERVAL '15 days',45.0,'bidadi-cl-02','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.8,"label":"negative"},"keywords":["NikhilKSwamy","Rs 33562 crore","scam","7480 acres","SaveBidadi"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_bidadi'),
('bidadi-ci-11','bidadi-topic-01','bidadi-src-14','https://x.com/BYVijayendra/status/bidadi-double','Stop double games with farmers — BJP slams CM over Bidadi','X/@BYVijayendra: ''Stop playing double games with Bidadi farmers. CM announces project, then says it''s under review. Farmers deserve clarity, not politics. BJP will not allow land grab under any name. #BattleForBidadi''',md5('bidadi-ci-11'),'en',NOW()-INTERVAL '12 days',45.0,'bidadi-cl-02','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["BYVijayendra","BJP","CM","double games","BattleForBidadi"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_bidadi'),

-- ── Topic 1, Cluster 3: Escalation Rhetoric & Violence Markers (5 items) ──
('bidadi-ci-12','bidadi-topic-01','bidadi-src-04','https://www.deccanherald.com/karnataka/bidadi-mass-suicide','Battle for Bidadi: Farmers threaten mass suicide as protest escalates','Deccan Herald: Battle for Bidadi — farmers threaten mass suicide if land acquisition proceeds. KRRS leader warns government: ''Blood will be on your hands.'' District administration appeals for calm. Mental health teams deployed to protest site.',md5('bidadi-ci-12'),'en',NOW()-INTERVAL '30 days',82.0,'bidadi-cl-03','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.85,"label":"negative"},"keywords":["mass suicide","Bidadi","KRRS","blood","escalation","mental health"]}'::jsonb,NOW()-INTERVAL '30 days',NOW(),'org_bidadi'),
('bidadi-ci-13','bidadi-topic-01','bidadi-src-04','https://www.deccanherald.com/karnataka/bidadi-blood-protest','Karnataka Bidadi farmers launch blood protest','Deccan Herald: Karnataka Bidadi farmers launch blood protest — smear blood on land acquisition notices. Dramatic escalation from peaceful sit-in. Imagery draws national media attention. Police maintain watch but do not intervene.',md5('bidadi-ci-13'),'en',NOW()-INTERVAL '25 days',82.0,'bidadi-cl-03','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.75,"label":"negative"},"keywords":["blood protest","Bidadi","farmers","escalation","land acquisition","media"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_bidadi'),
('bidadi-ci-14','bidadi-topic-01','bidadi-src-09','https://www.thequint.com/south-first-bidadi-poison','Give us poison instead — inside 460-day protest against Bidadi AI township','The South First/Quint: ''Give us poison instead'' — farmers from Byramangala and Mandalahalli hold poison bottles during protest. Symbolic act draws parallels to Vidarbha farmer suicides. Revenue officials abandon survey attempt.',md5('bidadi-ci-14'),'en',NOW()-INTERVAL '22 days',75.0,'bidadi-cl-03','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.8,"label":"negative"},"keywords":["poison","460 days","Byramangala","Mandalahalli","Vidarbha","survey"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_bidadi'),
('bidadi-ci-15','bidadi-topic-01','bidadi-src-11','https://t.me/swabhimana_kannada/298','ಬಿಡದಿ ರೈತರ ಹೋರಾಟ — ಪಂಜಾಬ್ ಮಾದರಿಯ ಚಳವಳಿ','ಬಿಡದಿ ರೈತರ ಹೋರಾಟ ತೀವ್ರಗೊಳ್ಳುತ್ತಿದೆ. ಪಂಜಾಬ್ ಮಾದರಿಯ ಚಳವಳಿ ಮಾಡಬೇಕಾಗಿದೆ. ಸರ್ಕಾರ ಕೇಳುತ್ತಿಲ್ಲ. ಎಲ್ಲ ರೈತ ಸಂಘಟನೆಗಳು ಒಂದಾಗಬೇಕು. Forwarded escalation message: Punjab-style agitation needed, government not listening.',md5('bidadi-ci-15'),'kn',NOW()-INTERVAL '18 days',15.0,'bidadi-cl-03','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["ಬಿಡದಿ","ಪಂಜಾಬ್","ಚಳವಳಿ","escalation","ಹೋರಾಟ"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_bidadi'),
('bidadi-ci-16','bidadi-topic-01','bidadi-src-08','https://indianexpress.com/the-wire-bidadi-expansion','Bidadi Township: How farmers are paying the price for Bengaluru expansion','The Wire/Indian Express: Bidadi Township — how farmers are paying the price for Bengaluru''s relentless expansion. 460 days of protest, still no resolution. Government caught between real estate interests and farmer votes. Environmental clearance pending.',md5('bidadi-ci-16'),'en',NOW()-INTERVAL '10 days',74.0,'bidadi-cl-03','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Bidadi","Bengaluru expansion","farmers","460 days","environment","real estate"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_bidadi'),

-- ── Topic 1, Cluster 4: Women's Resistance & SHG Mobilization (4 items) ──
('bidadi-ci-17','bidadi-topic-01','bidadi-src-08','https://indianexpress.com/the-print-broom-incident','Women chase away officials with brooms as survey turns chaotic','The Print/Indian Express: Women from Mandalahalli chase away revenue officials with brooms during land survey. Officials flee in vehicles. Women say: ''We will not let you measure our land.'' Self-help group leaders coordinate resistance.',md5('bidadi-ci-17'),'en',NOW()-INTERVAL '28 days',78.0,'bidadi-cl-04','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["women","brooms","Mandalahalli","survey","SHG","resistance"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_bidadi'),
('bidadi-ci-18','bidadi-topic-01','bidadi-src-06','https://www.thehindu.com/india-today-clash','Karnataka Farmers Clash with Officials Over Bidadi Township Survey','India Today/The Hindu: Karnataka farmers clash with officials over Bidadi Township survey. Revenue team of 15 officials confronted by 200+ farmers. Women leading the charge with brooms and agricultural tools. Two officials injured.',md5('bidadi-ci-18'),'en',NOW()-INTERVAL '26 days',80.0,'bidadi-cl-04','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.65,"label":"negative"},"keywords":["clash","officials","Bidadi","survey","women","injured"]}'::jsonb,NOW()-INTERVAL '26 days',NOW(),'org_bidadi'),
('bidadi-ci-19','bidadi-topic-01','bidadi-src-07','https://feeds.feedburner.com/ndtvnews-fir-ramanagara','2 FIRs registered after clash during land survey in Ramanagara — complainant Mohammed Sameer','ANI/NDTV: 2 FIRs registered after clash during land survey in Ramanagara district. Complainant Mohammed Sameer (revenue inspector). Accused include women farmers from Mandalahalli. Charges under IPC 353 (assault on public servant) and 143 (unlawful assembly).',md5('bidadi-ci-19'),'en',NOW()-INTERVAL '25 days',70.0,'bidadi-cl-04','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["FIR","Ramanagara","Mohammed Sameer","Mandalahalli","IPC 353","women"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_bidadi'),
('bidadi-ci-20','bidadi-topic-01','bidadi-src-04','https://www.deccanherald.com/karnataka/bidadi-fir-drop','Bidadi farmers booked, Priyank Kharge hints at dropping case','Deccan Herald: Bidadi farmers booked under IPC sections. Minister Priyank Kharge hints at dropping cases: ''These are mothers and grandmothers protecting their homes.'' Congress caught between pushing project and alienating rural voters.',md5('bidadi-ci-20'),'en',NOW()-INTERVAL '18 days',82.0,'bidadi-cl-04','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["Bidadi","FIR","Priyank Kharge","dropping case","farmers","Congress"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_bidadi')
ON CONFLICT (id) DO NOTHING;


-- ── Topic 2, Cluster 5: Sobha-Shivakumar SEBI Settlement (5 items) ──
INSERT INTO content_items (id, topic_id, source_id, url, raw_text, clean_text, content_hash, language, captured_at, credibility_score_at_capture, narrative_cluster_id, labels, created_at, updated_at, org_id) VALUES
('bidadi-ci-21','bidadi-topic-02','bidadi-src-02','https://www.sebi.gov.in/enforcement/orders/SO-AA-HP-2022-23-6654','Settlement Order SO/AA/HP/2022-23/6654-6658 in matter of Sobha Limited — Rs 2,92,50,000 penalty','SEBI Settlement Order SO/AA/HP/2022-23/6654-6658 in the matter of Sobha Limited. Noticees: Ravi PNC Menon (Chairman), Jagdish Chandra Sharma (MD). Settlement amount: Rs 2,92,50,000. Charges: misrepresentation of receivables for construction of residence for DK Shivakumar.',md5('bidadi-ci-21'),'en',NOW()-INTERVAL '40 days',95.0,'bidadi-cl-05','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["SEBI","Sobha Limited","Ravi PNC Menon","Jagdish Chandra Sharma","Rs 2.93 crore","Shivakumar"]}'::jsonb,NOW()-INTERVAL '40 days',NOW(),'org_bidadi'),
('bidadi-ci-22','bidadi-topic-02','bidadi-src-08','https://indianexpress.com/business-standard-sobha-sebi','Four individuals settle with SEBI in Sobha Ltd case, pay Rs 2.93 crore','Business Standard/Indian Express: Four individuals settle with SEBI in Sobha Ltd case, pay Rs 2.93 crore. Misrepresentation of receivables related to construction of DK Shivakumar residence. BSE code 532784. Sobha share price dips 2% on news.',md5('bidadi-ci-22'),'en',NOW()-INTERVAL '38 days',82.0,'bidadi-cl-05','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.35,"label":"negative"},"keywords":["SEBI","Sobha","settlement","Rs 2.93 crore","BSE 532784","Shivakumar residence"]}'::jsonb,NOW()-INTERVAL '38 days',NOW(),'org_bidadi'),
('bidadi-ci-23','bidadi-topic-02','bidadi-src-04','https://www.deccanherald.com/karnataka/nice-kumaraswamy-sobha','NICE controversy: Kumaraswamy dares Shivakumar to reveal partners of Sobha Developers','Deccan Herald: NICE controversy — Kumaraswamy dares Shivakumar to reveal his partnerships with Sobha Developers. ''Who financed your Sadashivanagar residence? Let SEBI investigate fully.'' Counter-allegations about NICE Road land.',md5('bidadi-ci-23'),'en',NOW()-INTERVAL '30 days',82.0,'bidadi-cl-05','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.55,"label":"negative"},"keywords":["NICE","Kumaraswamy","Sobha","Shivakumar","Sadashivanagar","SEBI"]}'::jsonb,NOW()-INTERVAL '30 days',NOW(),'org_bidadi'),
('bidadi-ci-24','bidadi-topic-02','bidadi-src-05','https://www.thenewsminute.com/swarajya-shivakumar-real-estate','After ascent to CM, Shivakumar ties with Bengaluru real estate firms back in focus — Sobha Ltd BSE:532784','Swarajya/TNM: After ascent to CM, DK Shivakumar''s ties with Bengaluru real estate firms come back into focus. Sobha Ltd (BSE:532784) built his Sadashivanagar residence. SEBI settlement raises questions. Multiple developers linked to CM''s political network.',md5('bidadi-ci-24'),'en',NOW()-INTERVAL '25 days',65.0,'bidadi-cl-05','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.45,"label":"negative"},"keywords":["Shivakumar","CM","real estate","Sobha","BSE 532784","Sadashivanagar"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_bidadi'),
('bidadi-ci-25','bidadi-topic-02','bidadi-src-04','https://www.deccanherald.com/bar-bench-bmic-scam','Karnataka HC calls BMIC one of state''s biggest scams, seeks independent probe — NICE vs Govt of Karnataka','Bar and Bench/Deccan Herald: Karnataka HC calls BMIC one of state''s biggest scams, seeks independent probe. NICE Road framework agreement dated 3 April 1997 covering 20,193 acres. Justice bench questions 25-year concession with no accountability.',md5('bidadi-ci-25'),'en',NOW()-INTERVAL '15 days',85.0,'bidadi-cl-05','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["BMIC","HC","scam","NICE Road","20193 acres","independent probe"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_bidadi'),

-- ── Topic 2, Cluster 6: GBDA Formation & Insider Appointments (5 items) ──
('bidadi-ci-26','bidadi-topic-02','bidadi-src-05','https://www.thenewsminute.com/oneindia-gbda-tender','Bidadi AI City moves ahead despite protests: GBDA floats Rs 26 crore tender for DPR','Oneindia/TNM: Bidadi AI City moves ahead despite protests. Greater Bengaluru Development Authority (GBDA) floats Rs 26 crore tender for Detailed Project Report. Base map consultancy for 8,935 acres. Farmers call it ''death sentence for our villages.''',md5('bidadi-ci-26'),'en',NOW()-INTERVAL '35 days',72.0,'bidadi-cl-06','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["GBDA","Rs 26 crore","tender","DPR","8935 acres","Bidadi"]}'::jsonb,NOW()-INTERVAL '35 days',NOW(),'org_bidadi'),
('bidadi-ci-27','bidadi-topic-02','bidadi-src-04','https://www.deccanherald.com/karnataka/hudco-bidadi-loan','HUDCO offers Rs 21,000 crore loan for Bidadi Integrated Township','Deccan Herald: HUDCO offers Rs 21,000 crore loan for Bidadi Integrated Township. Housing and Urban Development Corporation commits to financing. Project estimated at Rs 33,562 crore total. Environmental clearance still pending.',md5('bidadi-ci-27'),'en',NOW()-INTERVAL '32 days',82.0,'bidadi-cl-06','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.3,"label":"negative"},"keywords":["HUDCO","Rs 21000 crore","loan","Bidadi","Rs 33562 crore","environment"]}'::jsonb,NOW()-INTERVAL '32 days',NOW(),'org_bidadi'),
('bidadi-ci-28','bidadi-topic-02','bidadi-src-04','https://www.deccanherald.com/karnataka/dk-suresh-gbda','DK Suresh appointed as member of GBDA — CM''s brother on oversight body','Deccan Herald: DK Suresh — CM DK Shivakumar''s brother and former Lok Sabha MP — appointed as member of Greater Bengaluru Development Authority. Opposition calls it ''family fiefdom.'' GBDA oversees Rs 33,562 crore Bidadi township project.',md5('bidadi-ci-28'),'en',NOW()-INTERVAL '28 days',82.0,'bidadi-cl-06','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["DK Suresh","GBDA","CM brother","family fiefdom","oversight","Shivakumar"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_bidadi'),
('bidadi-ci-29','bidadi-topic-02','bidadi-src-01','https://egazette.karnataka.gov.in/opencity-tender','Tender documents for Township at Bidadi — base map consultancy for 8,935 acres','OpenCity/Karnataka Gazette: Tender documents for Greater Bengaluru Integrated Township at Bidadi. Base map consultancy and economic corridor preparation for 8,935 acres. Bidder qualification: minimum Rs 50 crore annual turnover. P Rajendra Cholan as GBDA Commissioner.',md5('bidadi-ci-29'),'en',NOW()-INTERVAL '22 days',85.0,'bidadi-cl-06','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.2,"label":"neutral"},"keywords":["tender","base map","8935 acres","P Rajendra Cholan","GBDA Commissioner"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_bidadi'),
('bidadi-ci-30','bidadi-topic-02','bidadi-src-13','https://x.com/IndexKarnataka/status/gbda-tender','GBDA tender: consultancy service for base map + economic corridor preparation','X/@IndexKarnataka: GBDA tender for consultancy service for base map and economic corridor preparation. Rs 26 crore for paper study while farmers lose land. Who benefits? Follow the money. #BidadiScam',md5('bidadi-ci-30'),'en',NOW()-INTERVAL '18 days',55.0,'bidadi-cl-06','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["GBDA","tender","consultancy","Rs 26 crore","BidadiScam"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_bidadi'),

-- ── Topic 2, Cluster 7: Kumaraswamy Family Land Paradox (5 items) ──
('bidadi-ci-31','bidadi-topic-02','bidadi-src-06','https://www.thehindu.com/the-week-kumaraswamy-farm','Kumaraswamy''s Bidadi farm surveyed over land grabbing charges — Kethaganahalli Sy No 7, 8, 9, 10, 16, 79','The Week/The Hindu: Kumaraswamy''s Bidadi farm surveyed over land grabbing charges. Kethaganahalli Survey Numbers 7, 8, 9, 10, 16, and 79 under investigation. Revenue department finds discrepancies in patta records. 110 acres of government land potentially encroached.',md5('bidadi-ci-31'),'en',NOW()-INTERVAL '38 days',80.0,'bidadi-cl-07','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.55,"label":"negative"},"keywords":["Kumaraswamy","Kethaganahalli","Sy 7-79","land grabbing","encroachment","110 acres"]}'::jsonb,NOW()-INTERVAL '38 days',NOW(),'org_bidadi'),
('bidadi-ci-32','bidadi-topic-02','bidadi-src-05','https://www.thenewsminute.com/etv-bharat-hc-encroachment','Karnataka HC orders report on encroachment of government land in Kethaganahalli — 110 acres under investigation','ETV Bharat/TNM: Karnataka HC orders report on encroachment of government land in Kethaganahalli. 110 acres under investigation. Revenue department given 4 weeks to submit report. Multiple political families named in preliminary findings.',md5('bidadi-ci-32'),'en',NOW()-INTERVAL '33 days',78.0,'bidadi-cl-07','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.45,"label":"negative"},"keywords":["HC","Kethaganahalli","encroachment","110 acres","revenue report","political families"]}'::jsonb,NOW()-INTERVAL '33 days',NOW(),'org_bidadi'),
('bidadi-ci-33','bidadi-topic-02','bidadi-src-04','https://www.deccanherald.com/karnataka/ramanagara-clearance-drive','Land encroachment: Revenue dept begins clearance drive in Ramanagara — 14 acres reclaimed, Anita Kumaraswamy 36-37 acres','Deccan Herald: Revenue department begins clearance drive in Ramanagara. 14 acres of government land reclaimed in first phase. Records show Anita Kumaraswamy (wife of HD Kumaraswamy) holds 36-37 acres in the Bidadi acquisition zone through multiple survey numbers.',md5('bidadi-ci-33'),'en',NOW()-INTERVAL '28 days',82.0,'bidadi-cl-07','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Ramanagara","clearance","Anita Kumaraswamy","36 acres","encroachment","Bidadi"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_bidadi'),
('bidadi-ci-34','bidadi-topic-02','bidadi-src-07','https://feeds.feedburner.com/ndtvnews-shivakumar-70-percent','Shivakumar claims 70% land owners including Kumaraswamy''s wife and son have sought compensation — opposing while profiting','ANI/NDTV: CM DK Shivakumar claims 70% of land owners in Bidadi zone have already applied for compensation. ''Including Kumaraswamy''s wife and son.'' Challenges opposition to show consistency. Documents tabled in assembly session.',md5('bidadi-ci-34'),'en',NOW()-INTERVAL '15 days',70.0,'bidadi-cl-07','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["Shivakumar","70%","compensation","Kumaraswamy wife","hypocrisy","assembly"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_bidadi'),
('bidadi-ci-35','bidadi-topic-02','bidadi-src-09','https://www.thequint.com/federal-bidadi-kumaraswamy','Bidadi land row: Kumaraswamy backs protesting farmers, promises legal aid — but family owns land in acquisition zone','The Federal/Quint: Bidadi land row — Kumaraswamy backs protesting farmers, promises legal aid. But records show family owns land in acquisition zone through wife Anita and son Nikhil. ''Opposing while seeking compensation'' — paradox exposed.',md5('bidadi-ci-35'),'en',NOW()-INTERVAL '10 days',76.0,'bidadi-cl-07','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Kumaraswamy","legal aid","family land","paradox","Anita","Nikhil"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_bidadi'),

-- ── Topic 2, Cluster 8: Benniganahalli Denotification Case (5 items) ──
('bidadi-ci-36','bidadi-topic-02','bidadi-src-05','https://www.thenewsminute.com/star-mysore-denotification','Denotification case: DKS BSY get Supreme Court relief — Survey No 50/2 Benniganahalli, 4.2 acres','Star of Mysore/TNM: Denotification case — DK Shivakumar and BS Yediyurappa get Supreme Court relief. Survey No 50/2 Benniganahalli, 4.2 acres. Land purchased at Rs 1.62 crore, current market value exceeds Rs 200 crore. SC stays HC order.',md5('bidadi-ci-36'),'en',NOW()-INTERVAL '40 days',70.0,'bidadi-cl-08','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.35,"label":"negative"},"keywords":["denotification","DKS","BSY","Supreme Court","Sy 50/2","Benniganahalli"]}'::jsonb,NOW()-INTERVAL '40 days',NOW(),'org_bidadi'),
('bidadi-ci-37','bidadi-topic-02','bidadi-src-04','https://www.deccanherald.com/karnataka/hc-benniganahalli-orders','HC reserves orders on denotification of 4.2 acres in Benniganahalli — complaint by Kabbale Gowda and TJ Abraham','Deccan Herald: HC reserves orders on denotification of 4.2 acres in Benniganahalli. Original complaint by activist Kabbale Gowda and anti-corruption crusader TJ Abraham. Allege land acquired at below-market rates and denotified for private benefit.',md5('bidadi-ci-37'),'en',NOW()-INTERVAL '35 days',82.0,'bidadi-cl-08','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.45,"label":"negative"},"keywords":["HC","Benniganahalli","4.2 acres","Kabbale Gowda","TJ Abraham","denotification"]}'::jsonb,NOW()-INTERVAL '35 days',NOW(),'org_bidadi'),
('bidadi-ci-38','bidadi-topic-02','bidadi-src-05','https://www.thenewsminute.com/land2capital-shivakumar','After ascent to CM, Shivakumar''s ties with real estate firms — Prudential Housing co-dev agreement May 2004, Puravankara JV','Land2Capital/TNM: Investigation into Shivakumar''s real estate ties. Prudential Housing co-development agreement dated May 2004. Puravankara joint venture for Benniganahalli land. Rs 1.62 crore purchase price vs Rs 200+ crore current valuation.',md5('bidadi-ci-38'),'en',NOW()-INTERVAL '28 days',60.0,'bidadi-cl-08','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Shivakumar","Prudential Housing","Puravankara","Benniganahalli","Rs 1.62 crore","JV"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_bidadi'),
('bidadi-ci-39','bidadi-topic-02','bidadi-src-02','https://www.sebi.gov.in/indiankanoon-nice-case','Nandi Infrastructure Corridor Enterprises vs Government of Karnataka — BMIC Framework Agreement 3 April 1997, 20,193 acres','IndianKanoon/SEBI: Nandi Infrastructure Corridor Enterprises (NICE) vs Government of Karnataka. BMIC Framework Agreement dated 3 April 1997 covering 20,193 acres. Toll collection rights, land development rights. Multiple pending cases in HC and SC.',md5('bidadi-ci-39'),'en',NOW()-INTERVAL '22 days',90.0,'bidadi-cl-08','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.3,"label":"negative"},"keywords":["NICE","BMIC","Framework Agreement","1997","20193 acres","toll","land rights"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_bidadi'),
('bidadi-ci-40','bidadi-topic-02','bidadi-src-08','https://indianexpress.com/organiser-nice-road','Karnataka BJP exposes Congress government''s land grab scam — NICE Road encroachment at Hosakerehalli','Organiser/Indian Express: Karnataka BJP exposes Congress government''s alleged land grab scam. NICE Road encroachment at Hosakerehalli. 47 acres of BDA land allegedly converted for private use. Documents submitted to Lokayukta.',md5('bidadi-ci-40'),'en',NOW()-INTERVAL '12 days',55.0,'bidadi-cl-08','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["BJP","NICE Road","Hosakerehalli","BDA","land grab","Lokayukta"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_bidadi'),

-- ── Topic 2, Unclustered: Low-credibility unverified social media claim ──
('bidadi-ci-61','bidadi-topic-02','bidadi-src-16','https://x.com/BidadiExpose247/status/shivakumar-500-acres','EXPOSED: Shivakumar secretly owns 500 acres in Bidadi through benami holders','X/@BidadiExpose247: ''EXPOSED: DK Shivakumar secretly owns 500+ acres in Bidadi township zone through benami holders. He is pushing GBIT to multiply his own land value 100x. This is the biggest land scam in Karnataka history. Wake up people! #BidadiScam #BenamiLand #ShivakumarExposed'' [UNVERIFIED — single anonymous source, no corroborating evidence, no named documents or survey numbers]',md5('bidadi-ci-61'),'en',NOW()-INTERVAL '3 days',18.0,NULL,'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.85,"label":"negative"},"keywords":["Shivakumar","500 acres","benami","Bidadi","exposed","land scam"],"credibility_flags":["single_source","anonymous_account","no_corroboration","social_media_only","unverified_claim"]}'::jsonb,NOW()-INTERVAL '3 days',NOW(),'org_bidadi')
ON CONFLICT (id) DO NOTHING;


-- ── Topic 3, Cluster 9: KRRS–La Via Campesina Foreign Funding (5 items) ──
INSERT INTO content_items (id, topic_id, source_id, url, raw_text, clean_text, content_hash, language, captured_at, credibility_score_at_capture, narrative_cluster_id, labels, created_at, updated_at, org_id) VALUES
('bidadi-ci-41','bidadi-topic-03','bidadi-src-03','https://ngodarpan.gov.in/amrita-bhoomi-129','AMRITA BHOOMI — Registration 129/1997-98, 636 Ideal Homes Layout Rajarajeshwari Nagar 560098','NGO DARPAN: AMRITA BHOOMI — Registration No. 129/1997-98 under Karnataka Societies Registration Act. Registered address: 636, Ideal Homes Layout, Rajarajeshwari Nagar, Bengaluru 560098. Aims: farmer education, agroecology training, international exchange programs.',md5('bidadi-ci-41'),'en',NOW()-INTERVAL '35 days',90.0,'bidadi-cl-09','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":0.1,"label":"neutral"},"keywords":["Amrita Bhoomi","129/1997-98","560098","Rajarajeshwari Nagar","NGO DARPAN"]}'::jsonb,NOW()-INTERVAL '35 days',NOW(),'org_bidadi'),
('bidadi-ci-42','bidadi-topic-03','bidadi-src-03','https://ngodarpan.gov.in/krrs-rmg-s20','KARNATAKA RAJYA RAITHA SANGHA — Registration RMG-S20-2013-14, Remco Bhel Layout Kenchenhalli Rajarajeshwari Nagar 560098','NGO DARPAN: KARNATAKA RAJYA RAITHA SANGHA — Registration No. RMG-S20-2013-14. Registered address: Remco Bhel Layout, Kenchenhalli, Rajarajeshwari Nagar, Bengaluru 560098. Same pincode as Amrita Bhoomi. Aims: farmer welfare, protest coordination, policy advocacy.',md5('bidadi-ci-42'),'en',NOW()-INTERVAL '35 days',90.0,'bidadi-cl-09','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":0.1,"label":"neutral"},"keywords":["KRRS","RMG-S20-2013-14","560098","Rajarajeshwari Nagar","NGO DARPAN"]}'::jsonb,NOW()-INTERVAL '35 days',NOW(),'org_bidadi'),
('bidadi-ci-43','bidadi-topic-03','bidadi-src-04','https://www.deccanherald.com/mongabay-chukki-nanjundaswamy','Farmer-to-farmer agroecology — Q&A with Chukki Nanjundaswamy of Amrita Bhoomi, La Via Campesina South Asia school','Mongabay/Deccan Herald: Farmer-to-farmer agroecology — interview with Chukki Nanjundaswamy, head of Amrita Bhoomi. La Via Campesina South Asia agroecology school. Training farmers from 8 countries. Funded by international solidarity grants.',md5('bidadi-ci-43'),'en',NOW()-INTERVAL '30 days',78.0,'bidadi-cl-09','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":0.2,"label":"positive"},"keywords":["Chukki Nanjundaswamy","Amrita Bhoomi","La Via Campesina","agroecology","international"]}'::jsonb,NOW()-INTERVAL '30 days',NOW(),'org_bidadi'),
('bidadi-ci-44','bidadi-topic-03','bidadi-src-06','https://www.thehindu.com/fao-agroecology-fund','Amrita Bhoomi receives collaborative grant from Agroecology Fund — donors include Christensen Fund, 11th Hour Project, Swift Foundation (US)','FAO/The Hindu: Amrita Bhoomi receives collaborative grant from Agroecology Fund. Donor consortium includes Christensen Fund (US), 11th Hour Project (US), and Swift Foundation (US). Grant for promoting farmer-to-farmer training across South Asia.',md5('bidadi-ci-44'),'en',NOW()-INTERVAL '25 days',85.0,'bidadi-cl-09','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":0.15,"label":"neutral"},"keywords":["Agroecology Fund","Christensen Fund","11th Hour Project","Swift Foundation","US funding"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_bidadi'),
('bidadi-ci-45','bidadi-topic-03','bidadi-src-08','https://indianexpress.com/one-earth-amrita-bhoomi','Project funding: Promoting Farmer-to-Farmer Training across South Asia through Amrita Bhoomi — La Via Campesina agroecology school','One Earth/Indian Express: Project funding profile for Amrita Bhoomi. Promoting farmer-to-farmer training across South Asia. La Via Campesina agroecology school model. International donors from US, Italy, and UK. Annual budget: undisclosed.',md5('bidadi-ci-45'),'en',NOW()-INTERVAL '20 days',80.0,'bidadi-cl-09','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":0.1,"label":"neutral"},"keywords":["One Earth","Amrita Bhoomi","La Via Campesina","South Asia","international donors"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_bidadi'),

-- ── Topic 3, Cluster 10: Save Bidadi Digital Campaign (4 items) ──
('bidadi-ci-46','bidadi-topic-03','bidadi-src-12','https://www.change.org/p/save-bidadi-petition','Save Bidadi petition — 79,329 signatures, petition ID 295807609, starter: ''People of Karnataka''','Change.org: Save Bidadi petition has collected 79,329 signatures. Petition ID 295807609. Started by ''People of Karnataka.'' Demands: stop land acquisition, preserve green belt, protect farmers. Shared 42,000 times on social media.',md5('bidadi-ci-46'),'en',NOW()-INTERVAL '30 days',35.0,'bidadi-cl-10','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.3,"label":"negative"},"keywords":["Change.org","Save Bidadi","79329 signatures","petition","green belt"]}'::jsonb,NOW()-INTERVAL '30 days',NOW(),'org_bidadi'),
('bidadi-ci-47','bidadi-topic-03','bidadi-src-04','https://www.deccanherald.com/hans-india-save-bidadi','Save Bidadi online campaign gains momentum — environmental activist Vijay Nishanth @vijayvruksha spearheads effort','Hans India/Deccan Herald: Save Bidadi online campaign gains momentum. Environmental activist Vijay Nishanth (@vijayvruksha) spearheads digital effort. Project Vruksha Foundation provides organizational support. Campaign reaches 2M social media impressions.',md5('bidadi-ci-47'),'en',NOW()-INTERVAL '25 days',72.0,'bidadi-cl-10','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.2,"label":"neutral"},"keywords":["Save Bidadi","Vijay Nishanth","vijayvruksha","Project Vruksha","digital campaign"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_bidadi'),
('bidadi-ci-48','bidadi-topic-03','bidadi-src-15','https://x.com/vijayvruksha/status/save-bidadi-trees','Stop the 9,600-acre land grab. Save 2 lakh trees. Spare 5,000 farmers. Sign the petition.','X/@vijayvruksha: ''Stop the 9,600-acre land grab. Save 2 lakh trees. Spare 5,000 farmers. Sign the petition. This is not development — this is destruction. Bengaluru does not need another concrete jungle. #SaveBidadi #SaveTrees''',md5('bidadi-ci-48'),'en',NOW()-INTERVAL '20 days',40.0,'bidadi-cl-10','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.65,"label":"negative"},"keywords":["vijayvruksha","9600 acres","2 lakh trees","5000 farmers","SaveBidadi"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_bidadi'),
('bidadi-ci-49','bidadi-topic-03','bidadi-src-08','https://indianexpress.com/shivakumar-ai-city-tweet','DK Shivakumar''s AI City tweet — ''India''s First AI City with 2000+ acres for AI & tech'' but Dy CM Parameshwara says ''not connected to any AI hub''','Indian Express: DK Shivakumar tweets about ''India''s First AI City'' with ''2000+ acres for AI & tech industries.'' But Dy CM Parameshwara contradicts: ''Project is not connected to any AI hub or tech corridor.'' Messaging inconsistency exposes branding vs reality gap.',md5('bidadi-ci-49'),'en',NOW()-INTERVAL '15 days',78.0,'bidadi-cl-10','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["Shivakumar","AI City","Parameshwara","contradiction","branding","2000 acres"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_bidadi'),

-- ── Topic 3, Cluster 11: Hashtag Amplification & Coordinated Messaging (3 items) ──
('bidadi-ci-50','bidadi-topic-03','bidadi-src-13','https://x.com/DKShivakumar/status/gbit-announcement','Greater Bengaluru Integrated Township — AI-powered smart city, Work/Live/Play model, 2000+ acres for AI & tech industries','X/@DKShivakumar: ''Greater Bengaluru Integrated Township will be India''s first AI-powered smart city. Work/Live/Play model with 2000+ acres dedicated to AI and tech industries. Karnataka leads India''s technology revolution.''',md5('bidadi-ci-50'),'en',NOW()-INTERVAL '40 days',60.0,'bidadi-cl-11','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":0.5,"label":"positive"},"keywords":["DKShivakumar","GBIT","AI city","smart city","2000 acres","tech"]}'::jsonb,NOW()-INTERVAL '40 days',NOW(),'org_bidadi'),
('bidadi-ci-51','bidadi-topic-03','bidadi-src-10','https://t.me/HaveriRaitaSangaKRRS/445','#BidadiChalo march July 11 — ರೈತರು ಬಿಡದಿಗೆ ನಡೆಯಿರಿ','KRRS Telegram: #BidadiChalo march announced for July 11. All farmer organizations to converge at Bidadi toll gate. KRRS, ಸ್ವಾಭಿಮಾನ, and allied groups coordinating. Buses arranged from Haveri, Dharwad, and Hassan districts.',md5('bidadi-ci-51'),'kn',NOW()-INTERVAL '18 days',22.0,'bidadi-cl-11','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["BidadiChalo","KRRS","march","July 11","Haveri","Dharwad"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_bidadi'),
('bidadi-ci-52','bidadi-topic-03','bidadi-src-04','https://www.deccanherald.com/karnataka/bjp-jds-bidadi-meeting','BJP-JDS coordination meeting in Bengaluru specifically about Bidadi Township — organized cross-party amplification strategy','Deccan Herald: BJP-JDS coordination meeting held in Bengaluru specifically about Bidadi Township. Opposition parties agree on joint strategy. Coordinated social media amplification: #SaveBidadi, #BidadiChalo, #BattleForBidadi. Joint press conferences planned.',md5('bidadi-ci-52'),'en',NOW()-INTERVAL '12 days',82.0,'bidadi-cl-11','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.3,"label":"negative"},"keywords":["BJP-JDS","coordination","Bidadi","amplification","SaveBidadi","BidadiChalo"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_bidadi'),

-- ── Topic 3, Cluster 12: Funding Absence as Intelligence Signal (3 items) ──
('bidadi-ci-53','bidadi-topic-03','bidadi-src-04','https://www.deccanherald.com/analyst-note-funding-gap','INTELLIGENCE GAP: 460-day protest, 10,000+ farmers, zero public crowdfunding','Analyst note: INTELLIGENCE GAP — 460-day protest involving 10,000+ farmers has zero public crowdfunding detected. Compare: Shaheen Bagh mobilized crowdfunding within days. Farm laws protest had multiple public donation drives. Funding absence = intelligence signal. Party-funded hypothesis requires investigation.',md5('bidadi-ci-53'),'en',NOW()-INTERVAL '15 days',50.0,'bidadi-cl-12','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.3,"label":"negative"},"keywords":["intelligence gap","zero crowdfunding","460 days","Shaheen Bagh","party funded"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_bidadi'),
('bidadi-ci-54','bidadi-topic-03','bidadi-src-09','https://www.thequint.com/beincrypto-telegram-audit','Audit of 118 publicly accessible Telegram posts from Indian movement-linked channels found ZERO crypto addresses','BeInCrypto/Quint: Audit of 118 publicly accessible Telegram posts from Indian movement-linked channels found ZERO cryptocurrency addresses. Crypto-protest funding narrative unsubstantiated for Bidadi movement. No Bitcoin, USDT, or UPI crowdfunding detected.',md5('bidadi-ci-54'),'en',NOW()-INTERVAL '10 days',70.0,'bidadi-cl-12','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.1,"label":"neutral"},"keywords":["Telegram audit","zero crypto","no crowdfunding","USDT","Bitcoin","unsubstantiated"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_bidadi'),
('bidadi-ci-55','bidadi-topic-03','bidadi-src-10','https://t.me/HaveriRaitaSangaKRRS/467','Investment scam message in KRRS channel: 3,000 invest return 15,000 in 20 minutes — channel integrity compromised','KRRS Telegram: Suspicious investment scam message posted in official KRRS Haveri channel — ''Invest Rs 3,000 and get Rs 15,000 return in 20 minutes.'' Channel integrity compromised. Either admin account hacked or channel moderation lapsed. Other messages appear genuine.',md5('bidadi-ci-55'),'en',NOW()-INTERVAL '5 days',22.0,'bidadi-cl-12','{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["investment scam","KRRS","Telegram","channel compromised","Rs 3000","integrity"]}'::jsonb,NOW()-INTERVAL '5 days',NOW(),'org_bidadi')
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 5. Extracted Entities
-- ==========================================================================
INSERT INTO extracted_entities (id, content_item_id, entity_type, entity_text, created_at, labels) VALUES
-- PERSON entities
('bidadi-ent-001','bidadi-ci-21','PERSON','DK Shivakumar',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-002','bidadi-ci-28','PERSON','DK Suresh',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-003','bidadi-ci-21','PERSON','Ravi PNC Menon',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-004','bidadi-ci-21','PERSON','Jagdish Chandra Sharma',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-005','bidadi-ci-33','PERSON','Anita Kumaraswamy',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-006','bidadi-ci-08','PERSON','Nikhil Kumaraswamy',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-007','bidadi-ci-31','PERSON','HD Kumaraswamy',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-008','bidadi-ci-09','PERSON','DC Thamanna',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-009','bidadi-ci-29','PERSON','P Rajendra Cholan',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-010','bidadi-ci-47','PERSON','Vijay Nishanth',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-011','bidadi-ci-43','PERSON','Chukki Nanjundaswamy',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-012','bidadi-ci-37','PERSON','Kabbale Gowda',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-013','bidadi-ci-37','PERSON','TJ Abraham',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-014','bidadi-ci-12','PERSON','G Madegowda',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-015','bidadi-ci-19','PERSON','Mohammed Sameer',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-016','bidadi-ci-06','PERSON','Nagaraju R',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-017','bidadi-ci-25','PERSON','Justice Santosh Hegde',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- ORG entities
('bidadi-ent-018','bidadi-ci-26','ORG','GBDA',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-019','bidadi-ci-21','ORG','SEBI',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-020','bidadi-ci-21','ORG','Sobha Limited',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-021','bidadi-ci-04','ORG','KRRS',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-022','bidadi-ci-41','ORG','Amrita Bhoomi',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-023','bidadi-ci-43','ORG','La Via Campesina',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-024','bidadi-ci-44','ORG','Agroecology Fund',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-025','bidadi-ci-38','ORG','Puravankara',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-026','bidadi-ci-39','ORG','NICE',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-027','bidadi-ci-27','ORG','HUDCO',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-028','bidadi-ci-47','ORG','Project Vruksha Foundation',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- GPE entities
('bidadi-ent-029','bidadi-ci-01','GPE','Bidadi',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-030','bidadi-ci-09','GPE','Ramanagara',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-031','bidadi-ci-50','GPE','Bengaluru',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-032','bidadi-ci-31','GPE','Kethaganahalli',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-033','bidadi-ci-36','GPE','Benniganahalli',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-034','bidadi-ci-17','GPE','Mandalahalli',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-035','bidadi-ci-25','GPE','Mysore',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- Special identifier entities
('bidadi-ent-036','bidadi-ci-21','SEBI_ORDER','SO/AA/HP/2022-23/6654-6658',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-037','bidadi-ci-41','NGO_REG','129/1997-98',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-038','bidadi-ci-42','NGO_REG','RMG-S20-2013-14',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-039','bidadi-ci-36','SURVEY_NO','Sy 50/2',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-040','bidadi-ci-31','SURVEY_NO','Sy 7,8,9,10,16,79',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-041','bidadi-ci-21','MONEY','Rs 2,92,50,000',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-042','bidadi-ci-27','MONEY','Rs 21,000 crore',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-043','bidadi-ci-26','MONEY','Rs 26 crore',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-044','bidadi-ci-22','BSE_CODE','532784',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- Cross-topic entity mentions: same entity_text in content items from DIFFERENT topics
-- DK Shivakumar in Topic 1 (protest context) and Topic 3 (AI City tweets)
('bidadi-ent-045','bidadi-ci-08','PERSON','DK Shivakumar',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-046','bidadi-ci-12','PERSON','DK Shivakumar',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-047','bidadi-ci-50','PERSON','DK Shivakumar',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- KRRS in Topic 2 (land context) and Topic 3 (foreign funding)
('bidadi-ent-048','bidadi-ci-23','ORG','KRRS',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-049','bidadi-ci-43','ORG','KRRS',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- Bidadi in all 3 topics
('bidadi-ent-050','bidadi-ci-21','GPE','Bidadi',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-051','bidadi-ci-41','GPE','Bidadi',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- HD Kumaraswamy in Topic 1 (protest) — already in Topic 2 via bidadi-ci-31
('bidadi-ent-052','bidadi-ci-08','PERSON','HD Kumaraswamy',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-053','bidadi-ci-09','PERSON','HD Kumaraswamy',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- Kethaganahalli in Topic 1 (displacement) — already in Topic 2 via bidadi-ci-31
('bidadi-ent-054','bidadi-ci-05','GPE','Kethaganahalli',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- Amrita Bhoomi in Topic 1 (protest support context)
('bidadi-ent-055','bidadi-ci-13','ORG','Amrita Bhoomi',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- Chukki Nanjundaswamy in Topic 1 (protest leader) — already in Topic 3
('bidadi-ent-056','bidadi-ci-04','PERSON','Chukki Nanjundaswamy',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- La Via Campesina mentioned in Topic 1 protest context
('bidadi-ent-057','bidadi-ci-13','ORG','La Via Campesina',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
-- Ramanagara in Topic 2 and Topic 3
('bidadi-ent-058','bidadi-ci-26','GPE','Ramanagara',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
('bidadi-ent-059','bidadi-ci-47','GPE','Ramanagara',NOW(),'{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 6. Identifier Clusters (5)
-- ==========================================================================
INSERT INTO identifier_clusters (id, topic_id, identifier_type, identifier_value, source_count, content_item_count, first_seen_at, last_seen_at, created_at, updated_at, labels) VALUES
    -- Cross-topic: DK Shivakumar across ALL 3 topics
    ('bidadi-ic-01', 'bidadi-topic-01', 'PERSON', 'DK Shivakumar', 5, 6, NOW()-INTERVAL '40 days', NOW()-INTERVAL '12 days', NOW()-INTERVAL '40 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    -- Pincode convergence: Amrita Bhoomi + KRRS same 560098
    ('bidadi-ic-02', 'bidadi-topic-03', 'NGO_REG', '560098', 1, 2, NOW()-INTERVAL '35 days', NOW()-INTERVAL '35 days', NOW()-INTERVAL '35 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    -- Cross-topic: Kethaganahalli Sy 7-79 in protest AND encroachment
    ('bidadi-ic-03', 'bidadi-topic-01', 'SURVEY_NO', 'Kethaganahalli-Sy7-79', 3, 4, NOW()-INTERVAL '38 days', NOW()-INTERVAL '10 days', NOW()-INTERVAL '38 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    -- Cross-topic: Kumaraswamy Family opposing T1 while owning land T2
    ('bidadi-ic-04', 'bidadi-topic-01', 'PERSON', 'Kumaraswamy Family', 4, 5, NOW()-INTERVAL '38 days', NOW()-INTERVAL '10 days', NOW()-INTERVAL '38 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb),
    -- Sobha Developers: SEBI settlement + NICE Road
    ('bidadi-ic-05', 'bidadi-topic-02', 'ORG', 'Sobha Developers', 3, 4, NOW()-INTERVAL '40 days', NOW()-INTERVAL '15 days', NOW()-INTERVAL '40 days', NOW(), '{"classification":"RESTRICTED","domain":"land_intelligence","owner_org":"mha-bidadi"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO identifier_cluster_items (identifier_cluster_id, content_item_id, source_id) VALUES
    -- DK Shivakumar across ALL 3 topics
    ('bidadi-ic-01', 'bidadi-ci-21', 'bidadi-src-02'),   -- Topic 2: SEBI Sobha settlement (client)
    ('bidadi-ic-01', 'bidadi-ci-28', 'bidadi-src-04'),   -- Topic 2: DK Suresh GBDA appointment (brother)
    ('bidadi-ic-01', 'bidadi-ci-34', 'bidadi-src-07'),   -- Topic 2: 70% compensation claim
    ('bidadi-ic-01', 'bidadi-ci-38', 'bidadi-src-05'),   -- Topic 2: Puravankara JV
    ('bidadi-ic-01', 'bidadi-ci-50', 'bidadi-src-13'),   -- Topic 3: AI City tweet
    ('bidadi-ic-01', 'bidadi-ci-49', 'bidadi-src-08'),   -- Topic 3: AI City contradiction
    -- Pincode 560098 convergence
    ('bidadi-ic-02', 'bidadi-ci-41', 'bidadi-src-03'),   -- Topic 3: Amrita Bhoomi 560098
    ('bidadi-ic-02', 'bidadi-ci-42', 'bidadi-src-03'),   -- Topic 3: KRRS 560098
    -- Kethaganahalli Sy 7-79 cross-topic
    ('bidadi-ic-03', 'bidadi-ci-31', 'bidadi-src-06'),   -- Topic 2: Kumaraswamy farm survey
    ('bidadi-ic-03', 'bidadi-ci-32', 'bidadi-src-05'),   -- Topic 2: HC encroachment order
    ('bidadi-ic-03', 'bidadi-ci-33', 'bidadi-src-04'),   -- Topic 2: Revenue clearance drive
    ('bidadi-ic-03', 'bidadi-ci-05', 'bidadi-src-06'),   -- Topic 1: Farmer protest about land
    -- Kumaraswamy Family cross-topic
    ('bidadi-ic-04', 'bidadi-ci-08', 'bidadi-src-07'),   -- Topic 1: JDS padayatra (opposing)
    ('bidadi-ic-04', 'bidadi-ci-09', 'bidadi-src-04'),   -- Topic 1: Padayatra halted
    ('bidadi-ic-04', 'bidadi-ci-31', 'bidadi-src-06'),   -- Topic 2: Farm survey (land owner)
    ('bidadi-ic-04', 'bidadi-ci-33', 'bidadi-src-04'),   -- Topic 2: Anita 36 acres
    ('bidadi-ic-04', 'bidadi-ci-35', 'bidadi-src-09'),   -- Topic 2: Paradox exposed
    -- Sobha Developers
    ('bidadi-ic-05', 'bidadi-ci-21', 'bidadi-src-02'),   -- Topic 2: SEBI settlement
    ('bidadi-ic-05', 'bidadi-ci-22', 'bidadi-src-08'),   -- Topic 2: Business Standard SEBI
    ('bidadi-ic-05', 'bidadi-ci-23', 'bidadi-src-04'),   -- Topic 2: NICE Kumaraswamy dare
    ('bidadi-ic-05', 'bidadi-ci-24', 'bidadi-src-05')    -- Topic 2: Swarajya CM ties
ON CONFLICT DO NOTHING;

-- ==========================================================================
-- 7. Signals (8)
-- ==========================================================================
INSERT INTO signals (id, topic_id, cluster_id, signal_type, description, evidence, status, created_at, updated_at, labels) VALUES
    ('bidadi-sig-01', 'bidadi-topic-01', 'bidadi-cl-01', 'multi_source_convergence',
     'Farmer displacement and livelihood destruction confirmed by 5 independent sources (Deccan Herald, The Quint, TNM, The Hindu, NDTV)',
     '{"independent_source_count":5,"severity":"HIGH"}'::jsonb,
     'new', NOW()-INTERVAL '35 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-sig-02', 'bidadi-topic-01', 'bidadi-cl-03', 'multi_source_convergence',
     'Escalation rhetoric and violence markers confirmed by 4 independent sources (Deccan Herald, Quint, Telegram, Indian Express)',
     '{"independent_source_count":4,"severity":"HIGH"}'::jsonb,
     'new', NOW()-INTERVAL '25 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-sig-03', 'bidadi-topic-01', NULL, 'identifier_convergence',
     'CRITICAL: DK Shivakumar detected across ALL THREE topics — CM pushing GBIT (Topic 1), Sobha client + GBDA creator + Benniganahalli buyer (Topic 2), AI City tweet propaganda (Topic 3)',
     '{"independent_source_count":5,"severity":"CRITICAL","identifier_type":"PERSON","identifier_value":"DK Shivakumar","cross_topic":true}'::jsonb,
     'new', NOW()-INTERVAL '20 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-sig-04', 'bidadi-topic-01', NULL, 'identifier_convergence',
     'Kumaraswamy family opposing project (Topic 1) while owning 36+ acres in acquisition zone and seeking compensation (Topic 2)',
     '{"independent_source_count":4,"severity":"HIGH","identifier_type":"PERSON","identifier_value":"Kumaraswamy Family","cross_topic":true}'::jsonb,
     'new', NOW()-INTERVAL '18 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-sig-05', 'bidadi-topic-02', 'bidadi-cl-05', 'multi_source_convergence',
     'Sobha-SEBI settlement for Shivakumar residence confirmed by 4 independent sources (SEBI portal, Business Standard, Deccan Herald, Swarajya)',
     '{"independent_source_count":4,"severity":"HIGH"}'::jsonb,
     'new', NOW()-INTERVAL '30 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-sig-06', 'bidadi-topic-02', NULL, 'identifier_convergence',
     'Same Kethaganahalli Sy 7-79 appears in farmer protest narrative (Topic 1) AND HC encroachment case against Kumaraswamy (Topic 2)',
     '{"independent_source_count":3,"severity":"HIGH","identifier_type":"SURVEY_NO","identifier_value":"Kethaganahalli-Sy7-79","cross_topic":true}'::jsonb,
     'new', NOW()-INTERVAL '22 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-sig-07', 'bidadi-topic-03', 'bidadi-cl-09', 'multi_source_convergence',
     'KRRS–La Via Campesina foreign funding pathway confirmed by 4 independent sources (NGO DARPAN, Mongabay, FAO/Agroecology Fund, One Earth)',
     '{"independent_source_count":4,"severity":"MEDIUM"}'::jsonb,
     'new', NOW()-INTERVAL '25 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-sig-08', 'bidadi-topic-03', NULL, 'identifier_convergence',
     'Amrita Bhoomi (129/1997-98) and KRRS (RMG-S20-2013-14) share same Rajarajeshwari Nagar 560098 locality — organizational proximity indicator',
     '{"independent_source_count":1,"severity":"MEDIUM","identifier_type":"NGO_REG","identifier_value":"560098","cross_topic":false}'::jsonb,
     'new', NOW()-INTERVAL '20 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"mha-bidadi"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 8. Keyword Alert Rules + Triggers
-- ==========================================================================
INSERT INTO keyword_alert_rules (id, topic_id, keywords, match_mode, is_active, notify_websocket, created_by, org_id, created_at, updated_at, labels) VALUES
    ('bidadi-alert-01', 'bidadi-topic-01', ARRAY['blood protest', 'mass suicide', 'poison', 'Punjab-style', 'agitation'], 'any', true, true, 'bidadi-user-analyst', 'org_bidadi', NOW()-INTERVAL '45 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-alert-02', 'bidadi-topic-02', ARRAY['SEBI', 'denotification', 'encroachment', 'land mafia', 'tender'], 'any', true, true, 'bidadi-user-analyst', 'org_bidadi', NOW()-INTERVAL '45 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-alert-03', 'bidadi-topic-03', ARRAY['FCRA', 'foreign funding', 'La Via Campesina', 'Christensen Fund'], 'any', true, true, 'bidadi-user-analyst', 'org_bidadi', NOW()-INTERVAL '45 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"mha-bidadi"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO keyword_alert_triggers (id, rule_id, content_item_id, matched_keywords, triggered_at, labels) VALUES
    ('bidadi-trig-01', 'bidadi-alert-01', 'bidadi-ci-12', ARRAY['mass suicide'], NOW()-INTERVAL '30 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-trig-02', 'bidadi-alert-01', 'bidadi-ci-13', ARRAY['blood protest'], NOW()-INTERVAL '25 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-trig-03', 'bidadi-alert-02', 'bidadi-ci-21', ARRAY['SEBI'], NOW()-INTERVAL '40 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-trig-04', 'bidadi-alert-02', 'bidadi-ci-37', ARRAY['denotification'], NOW()-INTERVAL '35 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-trig-05', 'bidadi-alert-03', 'bidadi-ci-43', ARRAY['La Via Campesina'], NOW()-INTERVAL '30 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"mha-bidadi"}'::jsonb),
    ('bidadi-trig-06', 'bidadi-alert-03', 'bidadi-ci-44', ARRAY['Christensen Fund'], NOW()-INTERVAL '25 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"mha-bidadi"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 9. Forwarding Chains (network graph)
-- ==========================================================================
UPDATE content_items SET forwarded_from_channel_name = 'HaveriRaitaSangaKRRS' WHERE id IN ('bidadi-ci-15','bidadi-ci-51');
UPDATE content_items SET forwarded_from_channel_name = 'swabhimana_kannada' WHERE id = 'bidadi-ci-04';

COMMIT;

-- ==========================================================================
-- Verify counts
-- ==========================================================================
SELECT 'Topics' AS entity, COUNT(*) FROM topics WHERE id LIKE 'bidadi-topic-%'
UNION ALL SELECT 'Sources', COUNT(*) FROM sources WHERE id LIKE 'bidadi-src-%'
UNION ALL SELECT 'Content Items', COUNT(*) FROM content_items WHERE id LIKE 'bidadi-ci-%'
UNION ALL SELECT 'Clusters', COUNT(*) FROM narrative_clusters WHERE id LIKE 'bidadi-cl-%'
UNION ALL SELECT 'Entities', COUNT(*) FROM extracted_entities WHERE id LIKE 'bidadi-ent-%'
UNION ALL SELECT 'ID Clusters', COUNT(*) FROM identifier_clusters WHERE id LIKE 'bidadi-ic-%'
UNION ALL SELECT 'Signals', COUNT(*) FROM signals WHERE id LIKE 'bidadi-sig-%'
UNION ALL SELECT 'Alert Rules', COUNT(*) FROM keyword_alert_rules WHERE id LIKE 'bidadi-alert-%'
UNION ALL SELECT 'Alert Triggers', COUNT(*) FROM keyword_alert_triggers WHERE id LIKE 'bidadi-trig-%';

DO $$
BEGIN
    RAISE NOTICE '═══════════════════════════════════════════════════════';
    RAISE NOTICE 'Bidadi Demo Seed Complete';
    RAISE NOTICE '═══════════════════════════════════════════════════════';
    RAISE NOTICE '  Login: demo_bidadi@anveshak.local';
    RAISE NOTICE '  Password: AnveshakDemo2024!';
    RAISE NOTICE '  Topics: 3 (Civil Unrest, Land Nexus, Foreign Linkages)';
    RAISE NOTICE '  Cross-topic person: DK Shivakumar across ALL 3 topics';
    RAISE NOTICE '  Cross-topic location: Kethaganahalli Sy 7-79 across Topics 1 & 2';
    RAISE NOTICE '  Cross-topic org: KRRS-Amrita Bhoomi 560098 proximity';
    RAISE NOTICE '═══════════════════════════════════════════════════════';
END $$;
