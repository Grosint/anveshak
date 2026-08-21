-- ==========================================================================
-- NCB Demo — Narcotics Control Bureau Intelligence Operations
-- ==========================================================================
-- Scenario: NCB monitoring three concurrent narcotics operations:
-- 1. Golden Crescent heroin pipeline (Afghanistan → Pakistan → India)
-- 2. Synthetic drug networks (dark web → Telegram → street)
-- 3. Maritime drug interdiction (Gujarat/Kerala coast)
--
-- Org: org_ncb (NCB Intelligence Division)
-- User: ncb_demo@anveshak.local / AnveshakDemo2024!
--
-- Idempotent: all INSERTs use ON CONFLICT DO NOTHING.
-- Run: docker exec -i anveshak-postgres-1 psql -U anveshak -d anveshak < scripts/seed_ncb_demo.sql
-- ==========================================================================

BEGIN;

-- ==========================================================================
-- 0. Organization + User
-- ==========================================================================
INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
VALUES (
    'org_ncb',
    'NCB Intelligence Division',
    'ncb',
    NOW(), NOW(),
    '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb
) ON CONFLICT (id) DO NOTHING;

-- Password: AnveshakDemo2024!
INSERT INTO users (id, username, password_hash, role, org_id, created_at, updated_at, labels)
VALUES (
    'ncb-user-analyst',
    'ncb_demo@anveshak.local',
    '$2b$12$exK0vBQZHOMCPjg37GTJZ.AtYqz1NI5SXwMLrWjnPvP2IqZMZKaei',
    'analyst',
    'org_ncb',
    NOW(), NOW(),
    '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb
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
    'ncb-topic-01',
    'Golden Crescent Heroin Pipeline — Afghanistan to Mumbai',
    ARRAY['Afghan heroin', 'Golden Crescent', 'Pakistan border', 'Punjab corridor',
          'Gujarat coast', 'Mumbai', 'DRI', 'BSF', 'heroin', 'morphine base',
          'precursor', 'acetic anhydride', 'hawala'],
    3, 2, 'active', ARRAY['en', 'hi', 'ur'], 20.0,
    '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb,
    NOW() - INTERVAL '45 days', NOW(), 'org_ncb'
),
(
    'ncb-topic-02',
    'Synthetic Drug Networks — Dark Web to Street',
    ARRAY['mephedrone', 'MDMA', 'synthetic drugs', 'dark web', 'Telegram vendor',
          'crypto payment', 'laboratory', 'precursor chemical', 'ephedrine',
          'pseudoephedrine', 'clandestine lab'],
    2, 2, 'active', ARRAY['en', 'hi'], 15.0,
    '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb,
    NOW() - INTERVAL '45 days', NOW(), 'org_ncb'
),
(
    'ncb-topic-03',
    'Maritime Drug Interdiction — Western & Southern Coast',
    ARRAY['maritime', 'fishing vessel', 'Gujarat coast', 'Kerala coast', 'Mundra port',
          'Coast Guard', 'Navy', 'heroin', 'hashish', 'methamphetamine',
          'Sri Lanka', 'Porbandar', 'Jakhau'],
    2, 2, 'active', ARRAY['en', 'hi', 'ml'], 20.0,
    '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb,
    NOW() - INTERVAL '45 days', NOW(), 'org_ncb'
)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 2. Sources (17)
-- ==========================================================================
INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, health_status, labels, created_at, updated_at, org_id) VALUES
    -- ── Official / Institutional ──
    ('ncb-src-01', 'NCB India Official',        'https://narcoticsindia.nic.in',          'web',  95.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-02', 'DRI India',                  'https://dri.nic.in',                    'web',  90.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-03', 'UNODC World Drug Report',    'https://www.unodc.org/unodc/en/data-and-analysis/', 'web', 92.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-04', 'Indian Coast Guard',          'https://indiancoastguard.gov.in',       'web',  88.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-05', 'BSF India',                   'https://bsf.gov.in',                    'web',  87.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),

    -- ── RSS / News ──
    ('ncb-src-06', 'Times of India - Crime',      'https://timesofindia.indiatimes.com/rss/crime', 'rss', 78.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-07', 'NDTV India',                  'https://feeds.ndtv.com/india',          'rss',  80.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-08', 'Indian Express Investigation', 'https://indianexpress.com/section/india/feed/', 'rss', 82.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-09', 'Hindustan Times - Crime',      'https://www.hindustantimes.com/feeds/rss/crime/rssfeed.xml', 'rss', 79.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-10', 'Mumbai Mirror',                'https://mumbaimirror.indiatimes.com/rss/crime', 'rss', 72.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),

    -- ── Telegram ──
    ('ncb-src-11', 'Drug Intel Network',          'drug_intel_network',         'telegram', 18.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-12', 'Mumbai Underground',          'mumbai_underground_intel',   'telegram', 15.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-13', 'Gujarat Seizure Watch',       'gujarat_seizure_watch',      'telegram', 20.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-14', 'Coast Guard Alerts',          'coast_guard_alerts_in',      'telegram', 22.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),
    ('ncb-src-15', 'Dark Web Drug Intel',         'darkweb_drug_intel',         'telegram', 10.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),

    -- ── Dark Web ──
    ('ncb-src-16', 'Ahmia Onion Search',          'http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/', 'darkweb', 5.0, true, 'healthy', '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb'),

    -- ── Instagram ──
    ('ncb-src-17', 'Indian Drug Bust News',       'indian_drug_bust_news',      'instagram', 25.0, true, 'healthy', '{"classification":"OPEN","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb, NOW()-INTERVAL '45 days', NOW(), 'org_ncb')
ON CONFLICT (id) DO NOTHING;

-- org_sources
INSERT INTO org_sources (org_id, source_id) VALUES
    ('org_ncb','ncb-src-01'),('org_ncb','ncb-src-02'),('org_ncb','ncb-src-03'),
    ('org_ncb','ncb-src-04'),('org_ncb','ncb-src-05'),('org_ncb','ncb-src-06'),
    ('org_ncb','ncb-src-07'),('org_ncb','ncb-src-08'),('org_ncb','ncb-src-09'),
    ('org_ncb','ncb-src-10'),('org_ncb','ncb-src-11'),('org_ncb','ncb-src-12'),
    ('org_ncb','ncb-src-13'),('org_ncb','ncb-src-14'),('org_ncb','ncb-src-15'),
    ('org_ncb','ncb-src-16'),('org_ncb','ncb-src-17')
ON CONFLICT DO NOTHING;

-- topic_sources (shared across topics)
-- Topic 1: Golden Crescent — all official + news + relevant telegram + dark web
INSERT INTO topic_sources (topic_id, source_id) VALUES
    ('ncb-topic-01','ncb-src-01'),('ncb-topic-01','ncb-src-02'),('ncb-topic-01','ncb-src-03'),
    ('ncb-topic-01','ncb-src-05'),('ncb-topic-01','ncb-src-06'),('ncb-topic-01','ncb-src-07'),
    ('ncb-topic-01','ncb-src-08'),('ncb-topic-01','ncb-src-09'),('ncb-topic-01','ncb-src-10'),
    ('ncb-topic-01','ncb-src-11'),('ncb-topic-01','ncb-src-12'),('ncb-topic-01','ncb-src-15'),
    ('ncb-topic-01','ncb-src-16'),('ncb-topic-01','ncb-src-17')
ON CONFLICT DO NOTHING;
-- Topic 2: Synthetic — dark web, telegram, news, instagram
INSERT INTO topic_sources (topic_id, source_id) VALUES
    ('ncb-topic-02','ncb-src-01'),('ncb-topic-02','ncb-src-06'),('ncb-topic-02','ncb-src-07'),
    ('ncb-topic-02','ncb-src-08'),('ncb-topic-02','ncb-src-09'),('ncb-topic-02','ncb-src-10'),
    ('ncb-topic-02','ncb-src-11'),('ncb-topic-02','ncb-src-12'),('ncb-topic-02','ncb-src-15'),
    ('ncb-topic-02','ncb-src-16'),('ncb-topic-02','ncb-src-17')
ON CONFLICT DO NOTHING;
-- Topic 3: Maritime — coast guard, DRI, news, telegram
INSERT INTO topic_sources (topic_id, source_id) VALUES
    ('ncb-topic-03','ncb-src-01'),('ncb-topic-03','ncb-src-02'),('ncb-topic-03','ncb-src-04'),
    ('ncb-topic-03','ncb-src-06'),('ncb-topic-03','ncb-src-07'),('ncb-topic-03','ncb-src-08'),
    ('ncb-topic-03','ncb-src-09'),('ncb-topic-03','ncb-src-13'),('ncb-topic-03','ncb-src-14'),
    ('ncb-topic-03','ncb-src-17')
ON CONFLICT DO NOTHING;


-- ==========================================================================
-- 3. Narrative Clusters (12)
-- ==========================================================================
INSERT INTO narrative_clusters (id, topic_id, label, item_count, independent_source_count, executive_summary, created_at, updated_at, labels) VALUES
    -- ── Topic 1: Golden Crescent (5 clusters) ──
    ('ncb-cl-01', 'ncb-topic-01', 'Afghan Heroin Entry via Punjab Border', 8, 5,
     'BSF and NCB intercept heroin shipments crossing Pakistan-Punjab border. Drone drops, tunnel routes, and truck concealment detected. Multi-agency coordination between BSF, NCB, and Punjab Police.',
     NOW()-INTERVAL '40 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    ('ncb-cl-02', 'ncb-topic-01', 'Gujarat Maritime Heroin Consignments', 5, 4,
     'DRI operations at Mundra and Kandla ports intercept Afghan heroin in container consignments. Fishing vessels used as mid-sea transfer points off Gujarat coast. Shell companies in UAE used for shipping documentation.',
     NOW()-INTERVAL '35 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    ('ncb-cl-03', 'ncb-topic-01', 'Mumbai Distribution Network Dismantled', 4, 4,
     'NCB Mumbai zonal unit dismantles major distribution network operating across Dongri, Kurla, and Andheri. Heroin sourced from Golden Crescent via Punjab corridor. Telegram used for coordination.',
     NOW()-INTERVAL '28 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    ('ncb-cl-04', 'ncb-topic-01', 'Pakistan-Based Handlers & Hawala Networks', 3, 3,
     'Cross-border handler network coordinating drug supply from Pakistan to India. Hawala channels and cryptocurrency used for payment. Same phone numbers appearing across multiple operations.',
     NOW()-INTERVAL '20 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),

    -- ── Topic 2: Synthetic Drugs (4 clusters) ──
    ('ncb-cl-05', 'ncb-topic-02', 'Gujarat Mephedrone Lab Busts', 6, 4,
     'Clandestine mephedrone manufacturing labs busted across Gujarat — Ankleshwar, Vapi, and Bharuch industrial zones. Chemistry graduates recruited as cooks. Precursor chemicals diverted from pharmaceutical industry.',
     NOW()-INTERVAL '38 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    ('ncb-cl-06', 'ncb-topic-02', 'Dark Web Drug Marketplace Operations', 5, 3,
     'Dark web marketplace listings offering mephedrone, MDMA, and LSD with India delivery. Vendors accept Bitcoin and USDT. Dead drop delivery in Mumbai and Delhi. Vendor identity linked to Telegram channels.',
     NOW()-INTERVAL '32 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    ('ncb-cl-07', 'ncb-topic-02', 'Telegram Vendor Networks — NCR & Mumbai', 5, 3,
     'Telegram channels operating as drug vendor storefronts in NCR and Mumbai. Vendors change handles frequently after takedowns. Phone numbers and UPI IDs persist across identity changes.',
     NOW()-INTERVAL '25 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    ('ncb-cl-08', 'ncb-topic-02', 'MDMA Party Drug Circuit — Metro Cities', 4, 3,
     'MDMA and cocaine supply chain targeting rave parties and nightclubs in Mumbai, Bangalore, and Goa. Instagram used for coded marketing. Supply linked to European dark web vendors.',
     NOW()-INTERVAL '18 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),

    -- ── Topic 3: Maritime (3 clusters) ──
    ('ncb-cl-09', 'ncb-topic-03', 'Gujarat Coast Heroin Interdiction', 6, 4,
     'Coast Guard and Navy intercept heroin-laden fishing vessels off Porbandar-Jakhau coast. Mother ships from Pakistan/Iran transfer cargo mid-sea. Satellite phone intercepts reveal coordination patterns.',
     NOW()-INTERVAL '42 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    ('ncb-cl-10', 'ncb-topic-03', 'Kerala-Sri Lanka Drug Corridor', 5, 3,
     'Kerala fishermen recruited as drug mules for Sri Lanka-origin heroin and hashish. Vizhinjam and Kochi used as landing points. NCB Kochi and Coast Guard Station Kochi coordination.',
     NOW()-INTERVAL '30 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    ('ncb-cl-11', 'ncb-topic-03', 'Mundra Port Container Seizures', 4, 3,
     'DRI container scanning at Mundra port detects heroin concealed in talc powder and semi-precious stone consignments from Afghanistan via Iran. Shell companies in UAE and Turkey used for freight forwarding.',
     NOW()-INTERVAL '22 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb)
ON CONFLICT (id) DO NOTHING;


-- ==========================================================================
-- 4. Content Items
-- ==========================================================================

-- ── Topic 1, Cluster 1: Afghan Heroin Entry via Punjab Border (8 items) ──
INSERT INTO content_items (id, topic_id, source_id, url, raw_text, clean_text, content_hash, language, captured_at, credibility_score_at_capture, narrative_cluster_id, labels, created_at, updated_at, org_id) VALUES
('ncb-ci-01','ncb-topic-01','ncb-src-05','https://bsf.gov.in/press-release-punjab-heroin','BSF seizes 25 kg heroin at Attari border','BSF troops seized 25 kg heroin worth Rs 125 crore at the Attari-Wagah border sector. Consignment was being pushed through a cross-border tunnel discovered during patrol. Two Pakistani nationals apprehended. NCB informed for further investigation.',md5('ncb-ci-01'),'en',NOW()-INTERVAL '42 days',87.0,'ncb-cl-01','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["BSF","heroin","Attari","tunnel","Pakistan"]}'::jsonb,NOW()-INTERVAL '42 days',NOW(),'org_ncb'),
('ncb-ci-02','ncb-topic-01','ncb-src-01','https://narcoticsindia.nic.in/punjab-ops-2026','NCB Punjab operations summary Q2 2026','NCB zonal unit Punjab conducts 47 operations in Q2 2026. Total seizures: 156 kg heroin, 45 kg opium, 12 kg morphine base. 89 persons arrested under NDPS Act. Afghan heroin constitutes 78% of seizures. Drone-based smuggling attempts up 200% year-over-year.',md5('ncb-ci-02'),'en',NOW()-INTERVAL '40 days',95.0,'ncb-cl-01','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["NCB","Punjab","heroin","seizures","drone","Afghan"]}'::jsonb,NOW()-INTERVAL '40 days',NOW(),'org_ncb'),
('ncb-ci-03','ncb-topic-01','ncb-src-11','https://t.me/drug_intel_network/156','Punjab border handler using new routes','INTEL: Punjab border handler shifting routes from Attari to Fazilka sector. Using agricultural trucks during harvest season as cover. Contact number +91-98765-44444 linked to coordinator on Pakistan side. Drone drops at night near BSF post Hussainiwala.',md5('ncb-ci-03'),'en',NOW()-INTERVAL '38 days',18.0,'ncb-cl-01','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["Punjab","handler","Fazilka","drone","agricultural trucks"]}'::jsonb,NOW()-INTERVAL '38 days',NOW(),'org_ncb'),
('ncb-ci-04','ncb-topic-01','ncb-src-08','https://indianexpress.com/punjab-drone-heroin','Drone-based heroin smuggling surge at Punjab border','Indian Express investigation: 47 drone incidents at Punjab border in 2026 so far — each carrying 5-10 kg heroin worth Rs 25-50 crore. Drones purchased from China via dark web, GPS-guided to pre-set coordinates. BSF shot down 12 drones, recovered 85 kg heroin.',md5('ncb-ci-04'),'en',NOW()-INTERVAL '36 days',82.0,'ncb-cl-01','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["drone","heroin","Punjab","BSF","China","GPS"]}'::jsonb,NOW()-INTERVAL '36 days',NOW(),'org_ncb'),
('ncb-ci-05','ncb-topic-01','ncb-src-07','https://ndtv.com/india-news/ncb-amritsar-bust','NCB busts Amritsar heroin syndicate with Pak links','NDTV: NCB busts major heroin syndicate operating from Amritsar. 50 kg heroin seized worth Rs 250 crore. Syndicate head Tariq Shah had direct links to Pakistan-based supplier. Hawala network used for payments routed through Dubai.',md5('ncb-ci-05'),'en',NOW()-INTERVAL '33 days',80.0,'ncb-cl-01','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.55,"label":"negative"},"keywords":["NCB","Amritsar","heroin","Pakistan","hawala","Dubai"]}'::jsonb,NOW()-INTERVAL '33 days',NOW(),'org_ncb'),
('ncb-ci-06','ncb-topic-01','ncb-src-15','https://t.me/darkweb_drug_intel/78','Dark web listing for Afghan No.4 heroin India delivery','Dark web vendor "KabulExpress" offering Afghan No.4 heroin (93% purity) with India delivery. Prices: $2800/100g. Ships via Pakistan-Punjab route. Accepts BTC/USDT. Wallet: bc1q7cgxhf2awzyjlkm6tqf4m3xnr0v. Reviews mention reliable 7-day delivery.',md5('ncb-ci-06'),'en',NOW()-INTERVAL '30 days',10.0,'ncb-cl-01','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.8,"label":"negative"},"keywords":["dark web","Afghan heroin","No.4","BTC","USDT","Pakistan"]}'::jsonb,NOW()-INTERVAL '30 days',NOW(),'org_ncb'),
('ncb-ci-07','ncb-topic-01','ncb-src-06','https://timesofindia.com/india/bsf-tunnel-fazilka','BSF discovers third cross-border tunnel near Fazilka','Times of India: BSF discovers third cross-border tunnel in Fazilka sector this year. Tunnel was 150 meters long with electric lighting and ventilation. 8 kg heroin recovered inside. Tunnel exit on Pakistan side located near a farmhouse.',md5('ncb-ci-07'),'en',NOW()-INTERVAL '25 days',78.0,'ncb-cl-01','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["BSF","tunnel","Fazilka","heroin","Pakistan"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_ncb'),
('ncb-ci-08','ncb-topic-01','ncb-src-03','https://unodc.org/wdr2026-south-asia','UNODC: South Asia heroin flow from Golden Crescent increasing','UNODC World Drug Report 2026: Heroin flow from Golden Crescent (Afghanistan-Pakistan-Iran) to South Asia increased 15% in 2025. India remains primary transit and destination country. Punjab border accounts for 65% of land-route seizures. Maritime route via Makran coast growing.',md5('ncb-ci-08'),'en',NOW()-INTERVAL '20 days',92.0,'ncb-cl-01','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["UNODC","Golden Crescent","heroin","South Asia","Punjab","Makran"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_ncb'),

-- ── Topic 1, Cluster 2: Gujarat Maritime Heroin (5 items) ──
('ncb-ci-09','ncb-topic-01','ncb-src-02','https://dri.nic.in/mundra-container-seizure','DRI seizes 3000 kg heroin at Mundra port','DRI Ahmedabad zonal unit seizes 3000 kg heroin concealed in talc powder consignment at Adani Mundra port. Consignment originated from Afghanistan via Bandar Abbas, Iran. Shell company in Sharjah used for import documentation. Largest single seizure in Indian history.',md5('ncb-ci-09'),'en',NOW()-INTERVAL '40 days',90.0,'ncb-cl-02','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["DRI","Mundra","heroin","talc","Afghanistan","Iran","Sharjah"]}'::jsonb,NOW()-INTERVAL '40 days',NOW(),'org_ncb'),
('ncb-ci-10','ncb-topic-01','ncb-src-13','https://t.me/gujarat_seizure_watch/234','Fishing vessel with heroin off Porbandar','Gujarat ATS and Coast Guard intercept fishing vessel 80 nautical miles off Porbandar. 120 kg heroin recovered from hidden compartment. Crew of 6 Pakistani nationals. Mid-sea transfer from Iranian dhow confirmed via satellite imagery.',md5('ncb-ci-10'),'en',NOW()-INTERVAL '35 days',20.0,'ncb-cl-02','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.65,"label":"negative"},"keywords":["fishing vessel","Porbandar","heroin","Pakistan","Coast Guard","Iran"]}'::jsonb,NOW()-INTERVAL '35 days',NOW(),'org_ncb'),
('ncb-ci-11','ncb-topic-01','ncb-src-09','https://hindustantimes.com/india/gujarat-heroin-route','Gujarat emerges as major heroin entry point','Hindustan Times: Gujarat coast has emerged as a major heroin entry point bypassing heavily guarded Punjab border. 5 major maritime seizures in 2026 totaling 3,500 kg. Porbandar-Jakhau-Mundra triangle identified as hotspot. NCB-Coast Guard joint operations intensified.',md5('ncb-ci-11'),'en',NOW()-INTERVAL '28 days',79.0,'ncb-cl-02','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Gujarat","heroin","maritime","Porbandar","Jakhau","Mundra"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_ncb'),
('ncb-ci-12','ncb-topic-01','ncb-src-08','https://indianexpress.com/dri-mundra-shell-companies','Shell companies behind Mundra drug imports exposed','Indian Express: DRI investigation reveals network of 14 shell companies in UAE, Turkey, and Hong Kong used to import heroin-laced consignments through Mundra. Same directors linked across companies. Enforcement Directorate freezes Rs 350 crore in assets.',md5('ncb-ci-12'),'en',NOW()-INTERVAL '22 days',82.0,'ncb-cl-02','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.55,"label":"negative"},"keywords":["DRI","Mundra","shell companies","UAE","Turkey","ED"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_ncb'),
('ncb-ci-13','ncb-topic-01','ncb-src-17','https://instagram.com/p/indian_drug_bust_mundra','Mundra port seizure — India largest heroin bust','Instagram @indian_drug_bust_news: Photos of 3000 kg heroin seizure at Mundra port. Heroin packed in 300 bags inside talc consignment. DRI officers with seized contraband. 2.3M views. Caption details Afghanistan-Iran-India route.',md5('ncb-ci-13'),'en',NOW()-INTERVAL '18 days',25.0,'ncb-cl-02','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["Mundra","heroin","DRI","Instagram","seizure","Afghanistan"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_ncb'),

-- ── Topic 1, Cluster 3: Mumbai Distribution (4 items) ──
('ncb-ci-14','ncb-topic-01','ncb-src-01','https://narcoticsindia.nic.in/mumbai-network-bust','NCB Mumbai dismantles major heroin distribution network','NCB Mumbai zonal unit dismantles heroin distribution network operating across Dongri, Kurla, and Andheri West. 35 kg heroin seized worth Rs 175 crore. 12 arrested including kingpin Salim Patel. Network received heroin from Punjab corridor via Rajasthan route.',md5('ncb-ci-14'),'en',NOW()-INTERVAL '30 days',95.0,'ncb-cl-03','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["NCB","Mumbai","Dongri","heroin","distribution","Salim Patel"]}'::jsonb,NOW()-INTERVAL '30 days',NOW(),'org_ncb'),
('ncb-ci-15','ncb-topic-01','ncb-src-12','https://t.me/mumbai_underground_intel/345','Mumbai pedlar network using Telegram for orders','Mumbai pedlar network operating via Telegram. Handle @maaldelivery_mum active since 6 months. Takes orders via encrypted chat, delivers within 2 hours in Mumbai. Heroin, mephedrone, MDMA available. Phone: +91-98765-44444 for bulk orders.',md5('ncb-ci-15'),'en',NOW()-INTERVAL '26 days',15.0,'ncb-cl-03','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.75,"label":"negative"},"keywords":["Mumbai","Telegram","pedlar","heroin","mephedrone","delivery"]}'::jsonb,NOW()-INTERVAL '26 days',NOW(),'org_ncb'),
('ncb-ci-16','ncb-topic-01','ncb-src-10','https://mumbaimirror.com/ncb-dongri-raids','NCB raids Dongri — 8 arrested in heroin operation','Mumbai Mirror: NCB conducts pre-dawn raids in Dongri. 8 persons arrested, 12 kg heroin recovered from 4 locations. Arrested include Mustafa alias Baba — top distributor supplying to South Mumbai nightclubs. Cash Rs 45 lakh and 3 luxury cars seized.',md5('ncb-ci-16'),'en',NOW()-INTERVAL '20 days',72.0,'ncb-cl-03','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["NCB","Dongri","heroin","raids","Mustafa","South Mumbai"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_ncb'),
('ncb-ci-17','ncb-topic-01','ncb-src-06','https://timesofindia.com/mumbai/ncb-bollywood-drug','NCB probes Bollywood drug nexus — supply chain traced to Punjab','Times of India: NCB investigation into Bollywood party drug supply chain traces heroin and cocaine to Punjab-based syndicate. Three talent managers questioned. Payments made via cryptocurrency. Network operated through high-end salon in Bandra.',md5('ncb-ci-17'),'en',NOW()-INTERVAL '15 days',78.0,'ncb-cl-03','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["NCB","Bollywood","drug","Punjab","cryptocurrency","Bandra"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_ncb'),

-- ── Topic 1, Cluster 4: Pakistan Handlers & Hawala (3 items) ──
('ncb-ci-18','ncb-topic-01','ncb-src-11','https://t.me/drug_intel_network/178','Pakistan handler coordinates multi-route supply','ALERT: Pakistan-based handler coordinating drug supply through BOTH Punjab border AND Gujarat coast. Uses satellite phone and Telegram. Same phone +91-98765-44444 linked to Punjab drone coordinator and Gujarat fishing vessel operator. Crypto wallet bc1q7cgxhf2awzyjlkm6tqf4m3xnr0v used for payments.',md5('ncb-ci-18'),'en',NOW()-INTERVAL '22 days',18.0,'ncb-cl-04','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.8,"label":"negative"},"keywords":["Pakistan","handler","Punjab","Gujarat","crypto","satellite phone"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_ncb'),
('ncb-ci-19','ncb-topic-01','ncb-src-09','https://hindustantimes.com/india/hawala-drug-money','Hawala network laundering Rs 500 crore drug money','Hindustan Times: ED and NCB joint investigation uncovers hawala network laundering Rs 500 crore in drug money. Operations span Mumbai, Delhi, Dubai, and Karachi. 8 hawala operators arrested. Money trail links Punjab heroin seizures to Gujarat maritime operations.',md5('ncb-ci-19'),'en',NOW()-INTERVAL '16 days',79.0,'ncb-cl-04','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["hawala","drug money","ED","NCB","Dubai","Karachi"]}'::jsonb,NOW()-INTERVAL '16 days',NOW(),'org_ncb'),
('ncb-ci-20','ncb-topic-01','ncb-src-07','https://ndtv.com/india-news/nia-drug-terror-nexus','NIA probes drug-terror nexus along Punjab border','NDTV: NIA investigation reveals drug trafficking proceeds funding terror operations. Pakistan-based handler using same logistics network for heroin and weapons. NCB sharing intelligence with NIA. Five suspects on NIA radar include two ISI-linked operatives.',md5('ncb-ci-20'),'en',NOW()-INTERVAL '10 days',80.0,'ncb-cl-04','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["NIA","drug-terror","Pakistan","ISI","NCB","weapons"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_ncb')
ON CONFLICT (id) DO NOTHING;


-- ── Topic 2, Cluster 5: Gujarat Mephedrone Lab Busts (6 items) ──
INSERT INTO content_items (id, topic_id, source_id, url, raw_text, clean_text, content_hash, language, captured_at, credibility_score_at_capture, narrative_cluster_id, labels, created_at, updated_at, org_id) VALUES
('ncb-ci-21','ncb-topic-02','ncb-src-01','https://narcoticsindia.nic.in/gujarat-meow-lab','NCB busts mephedrone lab in Ankleshwar industrial zone','NCB Gujarat zonal unit busts clandestine mephedrone manufacturing lab in Ankleshwar GIDC. 80 kg mephedrone worth Rs 160 crore seized. Lab operated by chemistry graduate Rajesh Thakkar using diverted precursor chemicals. Equipment worth Rs 2 crore destroyed.',md5('ncb-ci-21'),'en',NOW()-INTERVAL '40 days',95.0,'ncb-cl-05','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["NCB","mephedrone","Ankleshwar","lab","precursor","Gujarat"]}'::jsonb,NOW()-INTERVAL '40 days',NOW(),'org_ncb'),
('ncb-ci-22','ncb-topic-02','ncb-src-08','https://indianexpress.com/gujarat-meow-labs-surge','Gujarat emerges as mephedrone manufacturing hub','Indian Express: Gujarat has become India mephedrone manufacturing hub with 12 lab busts in 2026. Industrial zones in Ankleshwar, Vapi, and Bharuch provide cover. Precursor chemicals easily available from pharma industry. NCB estimates only 30% of labs detected.',md5('ncb-ci-22'),'en',NOW()-INTERVAL '35 days',82.0,'ncb-cl-05','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.55,"label":"negative"},"keywords":["Gujarat","mephedrone","labs","Ankleshwar","Vapi","Bharuch","precursor"]}'::jsonb,NOW()-INTERVAL '35 days',NOW(),'org_ncb'),
('ncb-ci-23','ncb-topic-02','ncb-src-11','https://t.me/drug_intel_network/167','New meow lab near Vapi — chemistry students recruited','INTEL: New mephedrone lab operating near Vapi industrial estate. Recruits chemistry students from local colleges. Output: 50 kg/month. Supplies to Mumbai and Pune via courier services. Lab uses legitimate chemical supply invoices as cover.',md5('ncb-ci-23'),'en',NOW()-INTERVAL '30 days',18.0,'ncb-cl-05','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["mephedrone","Vapi","lab","chemistry students","Mumbai","Pune"]}'::jsonb,NOW()-INTERVAL '30 days',NOW(),'org_ncb'),
('ncb-ci-24','ncb-topic-02','ncb-src-07','https://ndtv.com/india/ncb-precursor-chemical-raid','NCB raids precursor chemical diversion network','NDTV: NCB raids pharmaceutical companies in Gujarat and Maharashtra diverting ephedrine and pseudoephedrine. 500 kg precursor chemicals seized. Companies operating with valid drug licences but diverting 20% of production to illegal mephedrone labs.',md5('ncb-ci-24'),'en',NOW()-INTERVAL '25 days',80.0,'ncb-cl-05','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["NCB","precursor","ephedrine","pharma","Gujarat","Maharashtra"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_ncb'),
('ncb-ci-25','ncb-topic-02','ncb-src-15','https://t.me/darkweb_drug_intel/89','Dark web vendor sourcing mephedrone from Gujarat labs','Dark web vendor "BombayChemist" listing mephedrone at $180/10g with India delivery. Claims sourcing from Gujarat labs. Same phone +91-98765-44444 found in vendor contact info. Accepts BTC via wallet bc1q7cgxhf2awzyjlkm6tqf4m3xnr0v. 4.8-star rating, 200+ reviews.',md5('ncb-ci-25'),'en',NOW()-INTERVAL '20 days',10.0,'ncb-cl-05','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.8,"label":"negative"},"keywords":["dark web","mephedrone","Gujarat","BTC","vendor","delivery"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_ncb'),
('ncb-ci-26','ncb-topic-02','ncb-src-17','https://instagram.com/p/ncb_gujarat_lab_bust','NCB Gujarat lab bust photos — 80 kg mephedrone','Instagram @indian_drug_bust_news: Photos of NCB Gujarat mephedrone lab bust. Chemistry equipment, precursor chemical drums, finished product in bags. Officers in hazmat suits dismantling lab. 1.8M views.',md5('ncb-ci-26'),'en',NOW()-INTERVAL '15 days',25.0,'ncb-cl-05','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["NCB","Gujarat","mephedrone","lab","Instagram","bust"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_ncb'),

-- ── Topic 2, Cluster 6: Dark Web Marketplace (5 items) ──
('ncb-ci-27','ncb-topic-02','ncb-src-16','http://ahmia.onion/india-drug-market-listing','Dark web marketplace with India drug delivery','Dark web marketplace "IndiaConnect" listing 47 drug products with domestic India delivery. Mephedrone, MDMA, LSD, cocaine available. Dead drop locations in Mumbai (Andheri, Bandra, Colaba) and Delhi (Connaught Place, Hauz Khas). BTC and Monero accepted.',md5('ncb-ci-27'),'en',NOW()-INTERVAL '38 days',5.0,'ncb-cl-06','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.8,"label":"negative"},"keywords":["dark web","marketplace","Mumbai","Delhi","dead drop","crypto"]}'::jsonb,NOW()-INTERVAL '38 days',NOW(),'org_ncb'),
('ncb-ci-28','ncb-topic-02','ncb-src-15','https://t.me/darkweb_drug_intel/82','Vendor BombayChemist shipping via India Post','ALERT: Dark web vendor "BombayChemist" shipping drugs via India Post in vacuum-sealed packages disguised as electronics. Mephedrone and MDMA. Average delivery: 3-5 days pan-India. Using fake return addresses in Surat industrial area.',md5('ncb-ci-28'),'en',NOW()-INTERVAL '32 days',10.0,'ncb-cl-06','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.75,"label":"negative"},"keywords":["dark web","India Post","mephedrone","MDMA","Surat","delivery"]}'::jsonb,NOW()-INTERVAL '32 days',NOW(),'org_ncb'),
('ncb-ci-29','ncb-topic-02','ncb-src-06','https://timesofindia.com/india/dark-web-drug-bust','NCB cyber cell busts dark web drug delivery ring','Times of India: NCB cyber cell in coordination with CBI busts dark web drug delivery ring operating from Navi Mumbai. 3 arrested, 15 kg MDMA and 8 kg mephedrone seized. Ring operated on two dark web marketplaces with 500+ transactions over 18 months.',md5('ncb-ci-29'),'en',NOW()-INTERVAL '26 days',78.0,'ncb-cl-06','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["NCB","dark web","Navi Mumbai","MDMA","mephedrone","cyber cell"]}'::jsonb,NOW()-INTERVAL '26 days',NOW(),'org_ncb'),
('ncb-ci-30','ncb-topic-02','ncb-src-09','https://hindustantimes.com/india/crypto-drug-payments','Cryptocurrency becoming drug trade currency of choice','Hindustan Times: NCB reports 300% increase in cryptocurrency-based drug payments since 2024. Bitcoin, USDT, and Monero primary currencies. Wallet analysis reveals clusters of transactions linked to known dark web vendors. ED assisting with blockchain forensics.',md5('ncb-ci-30'),'en',NOW()-INTERVAL '20 days',79.0,'ncb-cl-06','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["cryptocurrency","drug","Bitcoin","USDT","Monero","NCB","blockchain"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_ncb'),
('ncb-ci-31','ncb-topic-02','ncb-src-16','http://ahmia.onion/vendor-bombaychemist-review','Vendor reviews for BombayChemist — India delivery','Dark web forum reviews for vendor "BombayChemist": "Excellent meow quality, Gujarat lab-fresh." "Delivery in 4 days to Bangalore." "UPI payment option available — UPI ID fastcash786@paytm." Multiple reviews mention same UPI for off-platform payments.',md5('ncb-ci-31'),'en',NOW()-INTERVAL '14 days',5.0,'ncb-cl-06','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["dark web","vendor","mephedrone","Gujarat","UPI","Bangalore"]}'::jsonb,NOW()-INTERVAL '14 days',NOW(),'org_ncb'),

-- ── Topic 2, Cluster 7: Telegram Vendor Networks (5 items) ──
('ncb-ci-32','ncb-topic-02','ncb-src-12','https://t.me/mumbai_underground_intel/367','Telegram vendor @maaldelivery_mum — price list','Mumbai Telegram vendor @maaldelivery_mum posting price list: Mephedrone Rs 3000/g, MDMA Rs 4000/pill, Cocaine Rs 8000/g. Delivery within 2 hours in Mumbai. Payment via UPI fastcash786@paytm or crypto. Handle active 8 months — previously @mumbai_maal_24x7 (seized).',md5('ncb-ci-32'),'en',NOW()-INTERVAL '28 days',15.0,'ncb-cl-07','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.8,"label":"negative"},"keywords":["Telegram","vendor","mephedrone","MDMA","Mumbai","UPI"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_ncb'),
('ncb-ci-33','ncb-topic-02','ncb-src-11','https://t.me/drug_intel_network/172','Vendor identity change detected — same phone persists','ANALYSIS: @maaldelivery_mum is the fourth identity of a Mumbai-based vendor. Previous handles: @mumbai_maal_24x7, @quality_stuff_mum, @fast_delivery_bom. All four linked by same phone +91-98765-44444 and UPI fastcash786@paytm. Channel seizure → new handle within 48 hours.',md5('ncb-ci-33'),'en',NOW()-INTERVAL '22 days',18.0,'ncb-cl-07','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["identity change","Telegram","vendor","phone","UPI","Mumbai"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_ncb'),
('ncb-ci-34','ncb-topic-02','ncb-src-08','https://indianexpress.com/telegram-drug-vendors','Telegram emerges as open drug marketplace in India','Indian Express investigation: Over 200 Telegram channels operating as drug storefronts in Indian cities. NCR and Mumbai highest concentration. Channels use coded language: "ice" for meth, "meow" for mephedrone, "paper" for LSD. Average channel lifespan: 3 months before takedown.',md5('ncb-ci-34'),'en',NOW()-INTERVAL '18 days',82.0,'ncb-cl-07','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["Telegram","drug","channels","NCR","Mumbai","coded language"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_ncb'),
('ncb-ci-35','ncb-topic-02','ncb-src-07','https://ndtv.com/india/ncb-telegram-crackdown','NCB announces Telegram drug channel crackdown','NDTV: NCB announces coordinated crackdown on Telegram drug vendor channels. 45 channels reported to Telegram for takedown. 12 channel operators identified, 7 arrested across Mumbai, Delhi, and Bangalore. NCB cyber cell developing automated detection capabilities.',md5('ncb-ci-35'),'en',NOW()-INTERVAL '12 days',80.0,'ncb-cl-07','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.3,"label":"negative"},"keywords":["NCB","Telegram","crackdown","channels","Mumbai","Delhi"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_ncb'),
('ncb-ci-36','ncb-topic-02','ncb-src-10','https://mumbaimirror.com/ncb-telegram-vendor-arrest','NCB arrests Telegram drug vendor in Andheri','Mumbai Mirror: NCB arrests operator of Telegram channel @maaldelivery_mum from Andheri East flat. 5 kg mephedrone, 200 MDMA pills, Rs 12 lakh cash seized. Accused Vikram Joshi (26) ran deliveries using food delivery rider uniforms as cover.',md5('ncb-ci-36'),'en',NOW()-INTERVAL '8 days',72.0,'ncb-cl-07','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["NCB","Telegram","vendor","arrest","Andheri","mephedrone"]}'::jsonb,NOW()-INTERVAL '8 days',NOW(),'org_ncb'),

-- ── Topic 2, Cluster 8: MDMA Party Drug Circuit (4 items) ──
('ncb-ci-37','ncb-topic-02','ncb-src-10','https://mumbaimirror.com/rave-party-drug-bust','NCB raids rave party in Alibaug — 45 detained','Mumbai Mirror: NCB raids farmhouse rave party in Alibaug. 45 persons detained, 15 tested positive. 500 MDMA pills, 200g cocaine, 50g ketamine seized. Party organized via invite-only Instagram group. DJ and two organizers arrested.',md5('ncb-ci-37'),'en',NOW()-INTERVAL '25 days',72.0,'ncb-cl-08','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["NCB","rave","Alibaug","MDMA","cocaine","Instagram"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_ncb'),
('ncb-ci-38','ncb-topic-02','ncb-src-17','https://instagram.com/p/goa-party-drug-scene','Goa party drug scene — coded Instagram marketing','Instagram @indian_drug_bust_news: Investigation into coded drug marketing on Instagram targeting Goa party scene. Accounts use terms like "party supplies" and "good vibes kit." DM conversations reveal MDMA, cocaine, ketamine available at tourist hotspots. 3 accounts reported to NCB.',md5('ncb-ci-38'),'en',NOW()-INTERVAL '18 days',25.0,'ncb-cl-08','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.65,"label":"negative"},"keywords":["Instagram","Goa","MDMA","cocaine","party","coded marketing"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_ncb'),
('ncb-ci-39','ncb-topic-02','ncb-src-06','https://timesofindia.com/bangalore-mdma-ring','NCB busts MDMA supply ring in Bangalore','Times of India: NCB Bangalore busts MDMA supply ring targeting tech workers and college students. 2000 MDMA pills seized worth Rs 1 crore. Supply traced to European dark web vendor shipping via postal parcels. 4 arrested including event management company owner.',md5('ncb-ci-39'),'en',NOW()-INTERVAL '12 days',78.0,'ncb-cl-08','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["NCB","MDMA","Bangalore","tech workers","dark web","Europe"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_ncb'),
('ncb-ci-40','ncb-topic-02','ncb-src-09','https://hindustantimes.com/india/party-drug-deaths','Party drug overdose deaths rising in metro cities','Hindustan Times: 23 party drug overdose deaths reported across Mumbai, Bangalore, and Goa in 2026. MDMA laced with fentanyl suspected in 8 cases. NCB warns of contaminated pills entering Indian market. Forensic analysis reveals Chinese-origin fentanyl.',md5('ncb-ci-40'),'en',NOW()-INTERVAL '6 days',79.0,'ncb-cl-08','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.8,"label":"negative"},"keywords":["overdose","MDMA","fentanyl","Mumbai","Bangalore","Goa"]}'::jsonb,NOW()-INTERVAL '6 days',NOW(),'org_ncb')
ON CONFLICT (id) DO NOTHING;


-- ── Topic 3, Cluster 9: Gujarat Coast Heroin Interdiction (6 items) ──
INSERT INTO content_items (id, topic_id, source_id, url, raw_text, clean_text, content_hash, language, captured_at, credibility_score_at_capture, narrative_cluster_id, labels, created_at, updated_at, org_id) VALUES
('ncb-ci-41','ncb-topic-03','ncb-src-04','https://indiancoastguard.gov.in/ops-porbandar','Coast Guard intercepts drug-laden vessel off Porbandar','Indian Coast Guard intercepts suspicious fishing vessel 120 NM south of Porbandar. 200 kg heroin and 50 kg methamphetamine recovered from hidden compartment. 8 crew — 5 Pakistani, 3 Iranian nationals. Vessel tracked via coastal surveillance radar. Satellite phone recovered — number +91-98765-44444 in call log.',md5('ncb-ci-41'),'en',NOW()-INTERVAL '43 days',88.0,'ncb-cl-09','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["Coast Guard","Porbandar","heroin","meth","Pakistan","Iran","satellite phone"]}'::jsonb,NOW()-INTERVAL '43 days',NOW(),'org_ncb'),
('ncb-ci-42','ncb-topic-03','ncb-src-14','https://t.me/coast_guard_alerts_in/189','Mother ship spotted off Jakhau coast','ALERT: Suspected mother ship (Iranian-flagged dhow) spotted 200 NM off Jakhau coast. Coast Guard deploying Dornier aircraft for aerial surveillance. Previous intercepts in same area yielded 300+ kg heroin. Fishing vessels from Okha used for mid-sea transfer.',md5('ncb-ci-42'),'en',NOW()-INTERVAL '40 days',22.0,'ncb-cl-09','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["mother ship","Jakhau","Iran","dhow","Coast Guard","Dornier"]}'::jsonb,NOW()-INTERVAL '40 days',NOW(),'org_ncb'),
('ncb-ci-43','ncb-topic-03','ncb-src-08','https://indianexpress.com/gujarat-coast-drug-route','Gujarat coast: India new front in global drug war','Indian Express: Gujarat coast has become a major heroin entry point from the Makran coast corridor. 8 maritime seizures in 2026 totaling 1,500 kg heroin. Coast Guard, Navy, NCB running joint operation "Sagar Manthan." Fishing vessels registered in Porbandar and Okha used as mules.',md5('ncb-ci-43'),'en',NOW()-INTERVAL '35 days',82.0,'ncb-cl-09','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Gujarat coast","heroin","Makran","Sagar Manthan","fishing vessel","Porbandar"]}'::jsonb,NOW()-INTERVAL '35 days',NOW(),'org_ncb'),
('ncb-ci-44','ncb-topic-03','ncb-src-01','https://narcoticsindia.nic.in/maritime-ops-2026','NCB maritime operations summary — H1 2026','NCB maritime operations H1 2026: 12 joint operations with Coast Guard and Navy. 2,800 kg narcotics seized across Gujarat and Kerala coast. 47 persons arrested including 15 foreign nationals. Operation Sagar Manthan continues — SIGINT integration with Coast Guard improving detection rate.',md5('ncb-ci-44'),'en',NOW()-INTERVAL '28 days',95.0,'ncb-cl-09','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.3,"label":"negative"},"keywords":["NCB","maritime","Coast Guard","Navy","Sagar Manthan","SIGINT"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_ncb'),
('ncb-ci-45','ncb-topic-03','ncb-src-13','https://t.me/gujarat_seizure_watch/256','Fishing vessel crew phone links to Punjab handler','Gujarat ATS analysis of seized fishing vessel crew phones reveals calls to +91-98765-44444 — same number flagged in Punjab border drug intel. Crew confess to 4 previous successful deliveries. Each trip paid Rs 5 lakh per crew member. Drugs transferred to trucks at Porbandar harbour.',md5('ncb-ci-45'),'en',NOW()-INTERVAL '22 days',20.0,'ncb-cl-09','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["fishing vessel","phone","Punjab","handler","Porbandar","ATS"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_ncb'),
('ncb-ci-46','ncb-topic-03','ncb-src-07','https://ndtv.com/india/navy-drug-bust-arabian-sea','Navy seizes 3400 kg heroin in Arabian Sea','NDTV: Indian Navy frigate INS Trishul seizes 3400 kg heroin from a stateless dhow in Arabian Sea, 600 NM off Gujarat coast. Largest maritime drug seizure globally in 2026. Drugs worth Rs 17,000 crore. Joint operation with Coast Guard intelligence.',md5('ncb-ci-46'),'en',NOW()-INTERVAL '15 days',80.0,'ncb-cl-09','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Navy","heroin","Arabian Sea","dhow","Gujarat","INS Trishul"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_ncb'),

-- ── Topic 3, Cluster 10: Kerala-Sri Lanka Corridor (5 items) ──
('ncb-ci-47','ncb-topic-03','ncb-src-01','https://narcoticsindia.nic.in/kerala-drug-corridor','NCB Kochi: Kerala-Sri Lanka drug corridor active','NCB Kochi zonal unit reports increasing drug trafficking via Kerala-Sri Lanka maritime route. Heroin and hashish arriving from Sri Lanka via fishing vessels. Lankan Tamil networks coordinating with Kerala fishermen. 5 seizures in 2026 totaling 85 kg heroin.',md5('ncb-ci-47'),'en',NOW()-INTERVAL '35 days',95.0,'ncb-cl-10','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["NCB","Kochi","Kerala","Sri Lanka","heroin","hashish","fishermen"]}'::jsonb,NOW()-INTERVAL '35 days',NOW(),'org_ncb'),
('ncb-ci-48','ncb-topic-03','ncb-src-14','https://t.me/coast_guard_alerts_in/201','Sri Lankan vessel intercepted off Vizhinjam','Coast Guard Station Kochi intercepts Sri Lankan fishing vessel 15 NM off Vizhinjam. 30 kg heroin and 20 kg hashish recovered. 4 Sri Lankan nationals arrested. GPS analysis shows vessel departed Talaimannar, Sri Lanka. Second interception this month on same route.',md5('ncb-ci-48'),'en',NOW()-INTERVAL '28 days',22.0,'ncb-cl-10','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.6,"label":"negative"},"keywords":["Coast Guard","Sri Lanka","Vizhinjam","heroin","hashish","Talaimannar"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_ncb'),
('ncb-ci-49','ncb-topic-03','ncb-src-06','https://timesofindia.com/kerala-fishermen-drug-mules','Kerala fishermen recruited as drug mules for Sri Lanka route','Times of India: Kerala fishermen from Vizhinjam and Kollam recruited as drug mules by Sri Lankan trafficking networks. Paid Rs 2 lakh per trip. NCB arrests 8 fishermen in 3 months. Fishermen cooperative warns members — cooperating with Coast Guard.',md5('ncb-ci-49'),'en',NOW()-INTERVAL '20 days',78.0,'ncb-cl-10','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.55,"label":"negative"},"keywords":["Kerala","fishermen","drug mules","Sri Lanka","Vizhinjam","Kollam"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_ncb'),
('ncb-ci-50','ncb-topic-03','ncb-src-09','https://hindustantimes.com/kerala-heroin-sri-lanka','Heroin quality indicates Sri Lanka as transit hub','Hindustan Times: Forensic analysis of heroin seized on Kerala coast shows Afghan origin but processed in Sri Lanka. Sri Lanka emerging as major transit hub for Golden Crescent heroin destined for South India and Southeast Asia. UNODC confirms trend.',md5('ncb-ci-50'),'en',NOW()-INTERVAL '14 days',79.0,'ncb-cl-10','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["heroin","Sri Lanka","transit","Afghan","Kerala","forensic"]}'::jsonb,NOW()-INTERVAL '14 days',NOW(),'org_ncb'),
('ncb-ci-51','ncb-topic-03','ncb-src-04','https://indiancoastguard.gov.in/kerala-ops','Coast Guard Kerala: Drug interception ops update','Indian Coast Guard Kerala region: 15 patrol sorties per week dedicated to drug interdiction. New coastal radar installations at Vizhinjam and Beypore. Intelligence sharing with Sri Lanka Navy. Phone number +91-98765-55555 identified as coordinator — fishing vessel skipper from Kollam.',md5('ncb-ci-51'),'en',NOW()-INTERVAL '8 days',88.0,'ncb-cl-10','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.3,"label":"negative"},"keywords":["Coast Guard","Kerala","radar","Vizhinjam","Beypore","Sri Lanka Navy"]}'::jsonb,NOW()-INTERVAL '8 days',NOW(),'org_ncb'),

-- ── Topic 3, Cluster 11: Mundra Port Container Seizures (4 items) ──
('ncb-ci-52','ncb-topic-03','ncb-src-02','https://dri.nic.in/mundra-container-scan','DRI Mundra: Enhanced container scanning reveals drug concealment','DRI Mundra introduces enhanced X-ray scanning for containers from Afghanistan, Iran, and Pakistan. First month: 3 containers flagged, 2 confirmed heroin concealment in talc and semi-precious stone consignments. Shell company "Gulf Star Trading FZE" linked to previous seizures.',md5('ncb-ci-52'),'en',NOW()-INTERVAL '30 days',90.0,'ncb-cl-11','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["DRI","Mundra","container","scanning","Afghanistan","shell company"]}'::jsonb,NOW()-INTERVAL '30 days',NOW(),'org_ncb'),
('ncb-ci-53','ncb-topic-03','ncb-src-08','https://indianexpress.com/mundra-port-drug-hub','Mundra port: How India largest port became drug gateway','Indian Express investigation: Mundra port processes 15,000 containers daily — DRI can scan only 2%. Drug traffickers exploit volume. Same shell companies appear in multiple seizures. Directors are UAE-based Indian nationals. NCB pushing for 100% scanning of Afghanistan-origin cargo.',md5('ncb-ci-53'),'en',NOW()-INTERVAL '22 days',82.0,'ncb-cl-11','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.5,"label":"negative"},"keywords":["Mundra","port","DRI","containers","scanning","UAE","shell companies"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_ncb'),
('ncb-ci-54','ncb-topic-03','ncb-src-13','https://t.me/gujarat_seizure_watch/268','Mundra port insider suspected in drug consignments','INTEL: DRI suspects insider at Mundra port facilitating drug consignment clearance. Specific customs officer cleared all 5 flagged containers in last 6 months. Vigilance department informed. Officer phone records being analysed.',md5('ncb-ci-54'),'en',NOW()-INTERVAL '16 days',20.0,'ncb-cl-11','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.7,"label":"negative"},"keywords":["Mundra","insider","customs","DRI","clearance","vigilance"]}'::jsonb,NOW()-INTERVAL '16 days',NOW(),'org_ncb'),
('ncb-ci-55','ncb-topic-03','ncb-src-17','https://instagram.com/p/mundra-3000kg-heroin','Mundra 3000 kg heroin — largest seizure in Indian history','Instagram @indian_drug_bust_news: Video showing 3000 kg heroin seizure at Mundra port. DRI officers cutting open talc powder bags revealing heroin packets. NCB DG statement: "Largest single seizure in Indian history." 5.2M views, 180K shares.',md5('ncb-ci-55'),'en',NOW()-INTERVAL '10 days',25.0,'ncb-cl-11','{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb","sentiment":{"compound":-0.4,"label":"negative"},"keywords":["Mundra","heroin","DRI","NCB","Instagram","seizure","record"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_ncb')
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 5. Extracted Entities
-- ==========================================================================
INSERT INTO extracted_entities (id, content_item_id, entity_type, entity_text, created_at, labels) VALUES
-- Topic 1 entities
('ncb-ent-001','ncb-ci-01','ORG','BSF',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-002','ncb-ci-01','GPE','Attari',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-003','ncb-ci-02','ORG','NCB',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-004','ncb-ci-02','GPE','Punjab',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-005','ncb-ci-05','PERSON','Tariq Shah',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-006','ncb-ci-05','GPE','Amritsar',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-007','ncb-ci-08','GPE','Afghanistan',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-008','ncb-ci-09','GPE','Mundra',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-009','ncb-ci-09','ORG','DRI',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-010','ncb-ci-10','GPE','Porbandar',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-011','ncb-ci-14','PERSON','Salim Patel',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-012','ncb-ci-14','GPE','Mumbai',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-013','ncb-ci-14','GPE','Dongri',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-014','ncb-ci-19','GPE','Dubai',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-015','ncb-ci-19','ORG','ED',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-016','ncb-ci-20','ORG','NIA',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
-- Topic 2 entities
('ncb-ent-017','ncb-ci-21','GPE','Ankleshwar',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-018','ncb-ci-22','GPE','Gujarat',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-019','ncb-ci-22','GPE','Vapi',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-020','ncb-ci-36','PERSON','Vikram Joshi',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-021','ncb-ci-39','GPE','Bangalore',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
-- Topic 3 entities
('ncb-ent-022','ncb-ci-41','ORG','Indian Coast Guard',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-023','ncb-ci-47','GPE','Kerala',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-024','ncb-ci-47','GPE','Sri Lanka',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-025','ncb-ci-48','GPE','Vizhinjam',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-026','ncb-ci-46','ORG','Indian Navy',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-027','ncb-ci-52','GPE','Iran',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-028','ncb-ci-52','GPE','Pakistan',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
-- Phone entities (cross-topic)
('ncb-ent-029','ncb-ci-03','PHONE_IN','+91-98765-44444',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-030','ncb-ci-15','PHONE_IN','+91-98765-44444',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-031','ncb-ci-18','PHONE_IN','+91-98765-44444',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-032','ncb-ci-25','PHONE_IN','+91-98765-44444',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-033','ncb-ci-33','PHONE_IN','+91-98765-44444',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-034','ncb-ci-41','PHONE_IN','+91-98765-44444',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-035','ncb-ci-45','PHONE_IN','+91-98765-44444',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
('ncb-ent-036','ncb-ci-51','PHONE_IN','+91-98765-55555',NOW(),'{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 6. Identifier Clusters (5)
-- ==========================================================================
INSERT INTO identifier_clusters (id, topic_id, identifier_type, identifier_value, source_count, content_item_count, first_seen_at, last_seen_at, created_at, updated_at, labels) VALUES
    -- Cross-topic phone — THE KILLER MOMENT
    ('ncb-ic-01', 'ncb-topic-01', 'PHONE_IN', '9876544444', 5, 7, NOW()-INTERVAL '42 days', NOW()-INTERVAL '8 days', NOW()-INTERVAL '42 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    -- Crypto wallet — topics 1 & 2
    ('ncb-ic-02', 'ncb-topic-01', 'CRYPTO_WALLET', 'bc1q7cgxhf2awzyjlkm6tqf4m3xnr0v', 3, 3, NOW()-INTERVAL '30 days', NOW()-INTERVAL '20 days', NOW()-INTERVAL '30 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    -- Telegram handle — topics 1 & 2
    ('ncb-ic-03', 'ncb-topic-02', 'TELEGRAM_HANDLE', 'maaldelivery_mum', 3, 4, NOW()-INTERVAL '28 days', NOW()-INTERVAL '8 days', NOW()-INTERVAL '28 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    -- UPI — topic 2
    ('ncb-ic-04', 'ncb-topic-02', 'UPI_ID', 'fastcash786@paytm', 2, 3, NOW()-INTERVAL '28 days', NOW()-INTERVAL '14 days', NOW()-INTERVAL '28 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb),
    -- Fishing vessel skipper phone — topic 3
    ('ncb-ic-05', 'ncb-topic-03', 'PHONE_IN', '9876555555', 2, 2, NOW()-INTERVAL '22 days', NOW()-INTERVAL '8 days', NOW()-INTERVAL '22 days', NOW(), '{"classification":"RESTRICTED","domain":"narcotics_intelligence","owner_org":"ncb"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO identifier_cluster_items (identifier_cluster_id, content_item_id, source_id) VALUES
    -- Phone 9876544444 across all 3 topics
    ('ncb-ic-01', 'ncb-ci-03', 'ncb-src-11'),   -- Topic 1: Punjab handler (Telegram)
    ('ncb-ic-01', 'ncb-ci-15', 'ncb-src-12'),   -- Topic 1: Mumbai pedlar (Telegram)
    ('ncb-ic-01', 'ncb-ci-18', 'ncb-src-11'),   -- Topic 1: Pakistan handler (Telegram)
    ('ncb-ic-01', 'ncb-ci-25', 'ncb-src-15'),   -- Topic 2: Dark web vendor (Telegram)
    ('ncb-ic-01', 'ncb-ci-33', 'ncb-src-11'),   -- Topic 2: Identity change (Telegram)
    ('ncb-ic-01', 'ncb-ci-41', 'ncb-src-04'),   -- Topic 3: Coast Guard intercept (web)
    ('ncb-ic-01', 'ncb-ci-45', 'ncb-src-13'),   -- Topic 3: Fishing vessel crew (Telegram)
    -- Crypto wallet across topics 1 & 2
    ('ncb-ic-02', 'ncb-ci-06', 'ncb-src-15'),   -- Topic 1: Dark web Afghan heroin listing
    ('ncb-ic-02', 'ncb-ci-18', 'ncb-src-11'),   -- Topic 1: Pakistan handler crypto
    ('ncb-ic-02', 'ncb-ci-25', 'ncb-src-15'),   -- Topic 2: Dark web mephedrone vendor
    -- Telegram @maaldelivery_mum
    ('ncb-ic-03', 'ncb-ci-15', 'ncb-src-12'),   -- Topic 1: Mumbai distribution
    ('ncb-ic-03', 'ncb-ci-32', 'ncb-src-12'),   -- Topic 2: Telegram vendor price list
    ('ncb-ic-03', 'ncb-ci-33', 'ncb-src-11'),   -- Topic 2: Identity change analysis
    ('ncb-ic-03', 'ncb-ci-36', 'ncb-src-10'),   -- Topic 2: Vendor arrest
    -- UPI fastcash786@paytm
    ('ncb-ic-04', 'ncb-ci-31', 'ncb-src-16'),   -- Topic 2: Dark web review
    ('ncb-ic-04', 'ncb-ci-32', 'ncb-src-12'),   -- Topic 2: Telegram price list
    ('ncb-ic-04', 'ncb-ci-33', 'ncb-src-11'),   -- Topic 2: Identity change
    -- Phone 9876555555 (fishing vessel skipper)
    ('ncb-ic-05', 'ncb-ci-51', 'ncb-src-04'),   -- Topic 3: Coast Guard ops
    ('ncb-ic-05', 'ncb-ci-49', 'ncb-src-06')    -- Topic 3: Kerala fishermen
ON CONFLICT DO NOTHING;

-- ==========================================================================
-- 7. Signals (8)
-- ==========================================================================
INSERT INTO signals (id, topic_id, cluster_id, signal_type, description, evidence, status, created_at, updated_at, labels) VALUES
    ('ncb-sig-01', 'ncb-topic-01', 'ncb-cl-01', 'multi_source_convergence',
     'Afghan heroin entry via Punjab border confirmed by 5 independent sources (BSF, NCB, Indian Express, NDTV, UNODC)',
     '{"independent_source_count":5,"severity":"HIGH"}'::jsonb,
     'new', NOW()-INTERVAL '35 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"ncb"}'::jsonb),
    ('ncb-sig-02', 'ncb-topic-01', 'ncb-cl-02', 'multi_source_convergence',
     'Gujarat maritime heroin route confirmed by 4 independent sources (DRI, Coast Guard, Hindustan Times, Gujarat Seizure Watch)',
     '{"independent_source_count":4,"severity":"HIGH"}'::jsonb,
     'new', NOW()-INTERVAL '28 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"ncb"}'::jsonb),
    ('ncb-sig-03', 'ncb-topic-01', NULL, 'identifier_convergence',
     'CRITICAL: Phone +91-98765-44444 detected across ALL THREE operations — Golden Crescent, Synthetic Drugs, and Maritime. Same handler operating across heroin pipeline, mephedrone network, and fishing vessel smuggling.',
     '{"independent_source_count":5,"severity":"CRITICAL","identifier_type":"PHONE_IN","identifier_value":"9876544444","cross_topic":true}'::jsonb,
     'new', NOW()-INTERVAL '22 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"ncb"}'::jsonb),
    ('ncb-sig-04', 'ncb-topic-01', NULL, 'identifier_convergence',
     'Crypto wallet bc1q7cgxhf2awzyjlkm6tqf4m3xnr0v linked across Golden Crescent heroin and Synthetic Drug operations',
     '{"independent_source_count":3,"severity":"HIGH","identifier_type":"CRYPTO_WALLET","identifier_value":"bc1q7cgxhf2awzyjlkm6tqf4m3xnr0v","cross_topic":true}'::jsonb,
     'new', NOW()-INTERVAL '20 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"ncb"}'::jsonb),
    ('ncb-sig-05', 'ncb-topic-02', 'ncb-cl-05', 'multi_source_convergence',
     'Gujarat mephedrone lab network confirmed by 4 independent sources (NCB, Indian Express, Drug Intel, Instagram)',
     '{"independent_source_count":4,"severity":"HIGH"}'::jsonb,
     'new', NOW()-INTERVAL '25 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"ncb"}'::jsonb),
    ('ncb-sig-06', 'ncb-topic-02', NULL, 'identifier_convergence',
     'Telegram vendor @maaldelivery_mum linked to Mumbai heroin distribution AND synthetic drug network — same phone and UPI across both',
     '{"independent_source_count":3,"severity":"HIGH","identifier_type":"TELEGRAM_HANDLE","identifier_value":"maaldelivery_mum","cross_topic":true}'::jsonb,
     'new', NOW()-INTERVAL '18 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"ncb"}'::jsonb),
    ('ncb-sig-07', 'ncb-topic-03', 'ncb-cl-09', 'multi_source_convergence',
     'Gujarat coast heroin interdiction confirmed by 4 independent sources (Coast Guard, Indian Express, NCB, Gujarat Seizure Watch)',
     '{"independent_source_count":4,"severity":"HIGH"}'::jsonb,
     'new', NOW()-INTERVAL '30 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"ncb"}'::jsonb),
    ('ncb-sig-08', 'ncb-topic-03', 'ncb-cl-10', 'multi_source_convergence',
     'Kerala-Sri Lanka drug corridor confirmed by 3 independent sources (NCB Kochi, Coast Guard, Times of India)',
     '{"independent_source_count":3,"severity":"MEDIUM"}'::jsonb,
     'new', NOW()-INTERVAL '20 days', NOW(), '{"classification":"RESTRICTED","domain":"signal","owner_org":"ncb"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 8. Keyword Alert Rules + Triggers
-- ==========================================================================
INSERT INTO keyword_alert_rules (id, topic_id, keywords, match_mode, is_active, notify_websocket, created_by, org_id, created_at, updated_at, labels) VALUES
    ('ncb-alert-01', 'ncb-topic-01', ARRAY['heroin', 'cocaine', 'morphine', 'opium', 'precursor', 'acetic anhydride'], 'any', true, true, 'ncb-user-analyst', 'org_ncb', NOW()-INTERVAL '45 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"ncb"}'::jsonb),
    ('ncb-alert-02', 'ncb-topic-02', ARRAY['mephedrone', 'MDMA', 'LSD', 'synthetic', 'clandestine lab', 'ephedrine'], 'any', true, true, 'ncb-user-analyst', 'org_ncb', NOW()-INTERVAL '45 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"ncb"}'::jsonb),
    ('ncb-alert-03', 'ncb-topic-03', ARRAY['seized', 'intercepted', 'arrested', 'busted', 'NDPS'], 'any', true, true, 'ncb-user-analyst', 'org_ncb', NOW()-INTERVAL '45 days', NOW(), '{"classification":"RESTRICTED","domain":"alert","owner_org":"ncb"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO keyword_alert_triggers (id, rule_id, content_item_id, matched_keywords, triggered_at, labels) VALUES
    ('ncb-trig-01', 'ncb-alert-01', 'ncb-ci-01', ARRAY['heroin'], NOW()-INTERVAL '42 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"ncb"}'::jsonb),
    ('ncb-trig-02', 'ncb-alert-01', 'ncb-ci-09', ARRAY['heroin'], NOW()-INTERVAL '40 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"ncb"}'::jsonb),
    ('ncb-trig-03', 'ncb-alert-02', 'ncb-ci-21', ARRAY['mephedrone'], NOW()-INTERVAL '40 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"ncb"}'::jsonb),
    ('ncb-trig-04', 'ncb-alert-02', 'ncb-ci-37', ARRAY['MDMA'], NOW()-INTERVAL '25 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"ncb"}'::jsonb),
    ('ncb-trig-05', 'ncb-alert-03', 'ncb-ci-41', ARRAY['intercepted'], NOW()-INTERVAL '43 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"ncb"}'::jsonb),
    ('ncb-trig-06', 'ncb-alert-03', 'ncb-ci-14', ARRAY['arrested'], NOW()-INTERVAL '30 days', '{"classification":"RESTRICTED","domain":"alert","owner_org":"ncb"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 9. Forwarding Chains (network graph)
-- ==========================================================================
UPDATE content_items SET forwarded_from_channel_name = 'mumbai_underground_intel' WHERE id IN ('ncb-ci-28','ncb-ci-25');
UPDATE content_items SET forwarded_from_channel_name = 'drug_intel_network' WHERE id IN ('ncb-ci-42','ncb-ci-45');
UPDATE content_items SET forwarded_from_channel_name = 'coast_guard_alerts_in' WHERE id IN ('ncb-ci-10','ncb-ci-48');

COMMIT;

-- ==========================================================================
-- Verify counts
-- ==========================================================================
SELECT 'Topics' AS entity, COUNT(*) FROM topics WHERE id LIKE 'ncb-topic-%'
UNION ALL SELECT 'Sources', COUNT(*) FROM sources WHERE id LIKE 'ncb-src-%'
UNION ALL SELECT 'Content Items', COUNT(*) FROM content_items WHERE id LIKE 'ncb-ci-%'
UNION ALL SELECT 'Clusters', COUNT(*) FROM narrative_clusters WHERE id LIKE 'ncb-cl-%'
UNION ALL SELECT 'Entities', COUNT(*) FROM extracted_entities WHERE id LIKE 'ncb-ent-%'
UNION ALL SELECT 'ID Clusters', COUNT(*) FROM identifier_clusters WHERE id LIKE 'ncb-ic-%'
UNION ALL SELECT 'Signals', COUNT(*) FROM signals WHERE id LIKE 'ncb-sig-%'
UNION ALL SELECT 'Alert Rules', COUNT(*) FROM keyword_alert_rules WHERE id LIKE 'ncb-alert-%'
UNION ALL SELECT 'Alert Triggers', COUNT(*) FROM keyword_alert_triggers WHERE id LIKE 'ncb-trig-%';

DO $$
BEGIN
    RAISE NOTICE '═══════════════════════════════════════════════════════';
    RAISE NOTICE 'NCB Demo Seed Complete';
    RAISE NOTICE '═══════════════════════════════════════════════════════';
    RAISE NOTICE '  Login: ncb_demo@anveshak.local';
    RAISE NOTICE '  Password: AnveshakDemo2024!';
    RAISE NOTICE '  Topics: 3 (Golden Crescent, Synthetic Drugs, Maritime)';
    RAISE NOTICE '  Cross-topic phone: +91-98765-44444 across ALL 3 topics';
    RAISE NOTICE '═══════════════════════════════════════════════════════';
END $$;

