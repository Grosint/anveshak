-- ==========================================================================
-- Nagaland Police Demo — Social Media Analytics Seed Data
-- ==========================================================================
-- Scenario: Monitoring social unrest, separatist activity, drug trafficking
-- across Northeast India. 4 platforms: Telegram, Instagram, RSS/Web.
-- Org: org_cyber (Police Cyber Cell)
-- User: demo_cyber@anveshak.local
--
-- Idempotent: all INSERTs use ON CONFLICT DO NOTHING.
-- Run: docker exec -i anveshak-postgres-1 psql -U anveshak -d anveshak < scripts/seed_nagaland_demo.sql
-- ==========================================================================

-- ==========================================================================
-- 1. Topic
-- ==========================================================================
INSERT INTO topics (
    id, name, keywords, signal_threshold, identifier_signal_threshold,
    status, languages, credibility_min,
    labels, created_at, updated_at, org_id
) VALUES (
    'nag-topic-01',
    'Nagaland Social Media Monitoring',
    ARRAY['NSCN', 'Nagaland', 'Kohima', 'Dimapur', 'AFSPA', 'ceasefire', 'drugs', 'Hornbill', 'separatist', 'Myanmar border'],
    3, 2, 'active', ARRAY['en', 'hi'], 30.0,
    '{"classification":"OPEN","domain":"social","owner_org":"cyber"}'::jsonb,
    NOW() - INTERVAL '30 days', NOW(), 'org_cyber'
) ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 2. Sources (12)
-- ==========================================================================
INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, health_status, labels, created_at, updated_at, org_id) VALUES
    ('nag-src-01', 'Nagaland Tribune',       'https://nagalandtribune.in',       'rss',       78.0, true, 'healthy', '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-02', 'Eastern Mirror',         'https://easternmirrornagaland.com','rss',       82.0, true, 'healthy', '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-03', 'Morung Express',         'https://morungexpress.com',        'rss',       75.0, true, 'healthy', '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-04', 'NE Now News',            'https://nenow.in',                 'rss',       70.0, true, 'healthy', '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-05', 'Naga Updates',           '@naga_updates',                    'telegram',  45.0, true, 'healthy', '{"classification":"OPEN","domain":"social","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-06', 'Kohima Pulse',           '@kohima_pulse',                    'telegram',  52.0, true, 'healthy', '{"classification":"OPEN","domain":"social","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-07', 'Dimapur Connect',        '@dimapur_connect',                 'telegram',  40.0, true, 'healthy', '{"classification":"OPEN","domain":"social","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-08', 'NE Underground Watch',   '@ne_underground_watch',            'telegram',  35.0, true, 'healthy', '{"classification":"OPEN","domain":"social","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-09', 'Northeast Voices',       '@northeast_voices',                'instagram', 55.0, true, 'healthy', '{"classification":"OPEN","domain":"social","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-10', 'Naga Heritage',          '@naga_heritage_official',          'instagram', 60.0, true, 'healthy', '{"classification":"OPEN","domain":"social","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-11', 'Manipur Alert',          '@manipur_alert',                   'instagram', 48.0, true, 'healthy', '{"classification":"OPEN","domain":"social","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber'),
    ('nag-src-12', 'NE Drug Watch',          'https://nedruwatch.example.com',   'web',       65.0, true, 'healthy', '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb, NOW()-INTERVAL '30 days', NOW(), 'org_cyber')
ON CONFLICT (id) DO NOTHING;

-- org_sources visibility
INSERT INTO org_sources (org_id, source_id) VALUES
    ('org_cyber','nag-src-01'),('org_cyber','nag-src-02'),('org_cyber','nag-src-03'),('org_cyber','nag-src-04'),
    ('org_cyber','nag-src-05'),('org_cyber','nag-src-06'),('org_cyber','nag-src-07'),('org_cyber','nag-src-08'),
    ('org_cyber','nag-src-09'),('org_cyber','nag-src-10'),('org_cyber','nag-src-11'),('org_cyber','nag-src-12')
ON CONFLICT DO NOTHING;

-- topic_sources
INSERT INTO topic_sources (topic_id, source_id) VALUES
    ('nag-topic-01','nag-src-01'),('nag-topic-01','nag-src-02'),('nag-topic-01','nag-src-03'),('nag-topic-01','nag-src-04'),
    ('nag-topic-01','nag-src-05'),('nag-topic-01','nag-src-06'),('nag-topic-01','nag-src-07'),('nag-topic-01','nag-src-08'),
    ('nag-topic-01','nag-src-09'),('nag-topic-01','nag-src-10'),('nag-topic-01','nag-src-11'),('nag-topic-01','nag-src-12')
ON CONFLICT DO NOTHING;

-- ==========================================================================
-- 3. Narrative Clusters (5)
-- ==========================================================================
INSERT INTO narrative_clusters (id, topic_id, label, item_count, independent_source_count, executive_summary, created_at, updated_at, labels) VALUES
    ('nag-cl-01', 'nag-topic-01', 'NSCN Ceasefire Talks and Framework Agreement', 12, 4,
     'Multiple sources report on the ongoing NSCN-IM ceasefire negotiations, with reports of violations near Mon district and renewed calls for Framework Agreement implementation.',
     NOW()-INTERVAL '25 days', NOW(), '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
    ('nag-cl-02', 'nag-topic-01', 'Drug Trafficking via Myanmar-Nagaland Corridor', 10, 3,
     'Rising seizures of methamphetamine and heroin along the Moreh-Imphal-Dimapur corridor. Telegram channels discussing new routes and prices.',
     NOW()-INTERVAL '20 days', NOW(), '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
    ('nag-cl-03', 'nag-topic-01', 'Hornbill Festival Cultural Preparations', 8, 4,
     'Preparations underway for the annual Hornbill Festival in Kisama Heritage Village. Tourism department promoting the event across social media.',
     NOW()-INTERVAL '15 days', NOW(), '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
    ('nag-cl-04', 'nag-topic-01', 'AFSPA Debate and Human Rights Protests', 12, 5,
     'Renewed protests demanding AFSPA repeal following alleged human rights violations. Civil society groups mobilizing across social media platforms.',
     NOW()-INTERVAL '10 days', NOW(), '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
    ('nag-cl-05', 'nag-topic-01', 'Myanmar Refugee Influx at NE Border', 8, 3,
     'Reports of increased Myanmar refugee movement across Nagaland-Myanmar border. Humanitarian concerns raised alongside security implications.',
     NOW()-INTERVAL '5 days', NOW(), '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 4. Content Items (60 items across 5 clusters, 30 days)
-- ==========================================================================

-- Helper: content_hash = md5 of clean_text (unique per item)

-- ── Cluster 1: NSCN Ceasefire (12 items, days 5-15) ──
INSERT INTO content_items (id, topic_id, source_id, url, raw_text, clean_text, content_hash, language, captured_at, credibility_score_at_capture, narrative_cluster_id, labels, created_at, updated_at, org_id) VALUES
('nag-ci-01','nag-topic-01','nag-src-01','https://nagalandtribune.in/nscn-ceasefire-update','NSCN-IM ceasefire talks resume in Delhi','NSCN-IM ceasefire talks resume in Delhi with government interlocutor RN Ravi discussing Framework Agreement implementation timeline with top NSCN leadership including Thuingaleng Muivah.', md5('nag-ci-01'),'en',NOW()-INTERVAL '28 days',78.0,'nag-cl-01','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Nagaland Tribune","author_id":"nag-src-01","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.15,"label":"neutral"},"keywords":["NSCN","ceasefire","Framework Agreement","Muivah"]}'::jsonb,NOW()-INTERVAL '28 days',NOW(),'org_cyber'),
('nag-ci-02','nag-topic-01','nag-src-02','https://easternmirrornagaland.com/framework-agreement','Framework Agreement key demands','Eastern Mirror exclusive: Framework Agreement key demands include shared sovereignty provision, separate flag and constitution for Nagalim. Government reportedly open to cultural autonomy but firm on territorial integrity.', md5('nag-ci-02'),'en',NOW()-INTERVAL '27 days',82.0,'nag-cl-01','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Eastern Mirror","author_id":"nag-src-02","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.05,"label":"neutral"},"keywords":["Framework Agreement","sovereignty","Nagalim","constitution"]}'::jsonb,NOW()-INTERVAL '27 days',NOW(),'org_cyber'),
('nag-ci-03','nag-topic-01','nag-src-05','https://t.me/naga_updates/1234','Ceasefire violation reported near Mon','Breaking: Ceasefire violation reported near Mon district. NSCN-K faction accused of attacking Assam Rifles patrol. Two jawans injured. Area tense.', md5('nag-ci-03'),'en',NOW()-INTERVAL '25 days',45.0,'nag-cl-01','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_updates","author_id":"naga_updates","engagement":{"likes":23,"comments":45,"shares":0,"views":890,"forwards":18},"sentiment":{"compound":-0.65,"label":"negative"},"keywords":["ceasefire","violation","Mon","NSCN-K","Assam Rifles"]}'::jsonb,NOW()-INTERVAL '25 days',NOW(),'org_cyber'),
('nag-ci-04','nag-topic-01','nag-src-06','https://t.me/kohima_pulse/567','Kohima bandh call over ceasefire','Kohima bandh called by tribal bodies over ceasefire violation. Schools and markets to remain closed. NSCN-IM condemns the NSCN-K attack.', md5('nag-ci-04'),'en',NOW()-INTERVAL '24 days',52.0,'nag-cl-01','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@kohima_pulse","author_id":"kohima_pulse","engagement":{"likes":34,"comments":67,"shares":0,"views":1200,"forwards":25},"sentiment":{"compound":-0.45,"label":"negative"},"keywords":["Kohima","bandh","ceasefire","NSCN-IM","NSCN-K"]}'::jsonb,NOW()-INTERVAL '24 days',NOW(),'org_cyber'),
('nag-ci-05','nag-topic-01','nag-src-03','https://morungexpress.com/peace-process','Peace process at crossroads','Morung Express analysis: Naga peace process at crossroads as rival factions NSCN-IM and NSCN-K take divergent paths. Muivah calls for unity among Naga groups.', md5('nag-ci-05'),'en',NOW()-INTERVAL '23 days',75.0,'nag-cl-01','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Morung Express","author_id":"nag-src-03","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.1,"label":"neutral"},"keywords":["peace process","NSCN-IM","NSCN-K","Muivah","unity"]}'::jsonb,NOW()-INTERVAL '23 days',NOW(),'org_cyber'),
('nag-ci-06','nag-topic-01','nag-src-08','https://t.me/ne_underground_watch/89','Arms cache found near Tuensang','ALERT: Arms cache including AK-47s and ammunition found near Tuensang. Sources say linked to NSCN-K. Security forces on high alert.', md5('nag-ci-06'),'en',NOW()-INTERVAL '22 days',35.0,'nag-cl-01','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@ne_underground_watch","author_id":"ne_underground_watch","engagement":{"likes":12,"comments":34,"shares":0,"views":670,"forwards":15},"sentiment":{"compound":-0.78,"label":"negative"},"keywords":["arms","AK-47","Tuensang","NSCN-K","security"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_cyber'),
('nag-ci-07','nag-topic-01','nag-src-04','https://nenow.in/nscn-talks','Government firm on single entity talks','NE Now: Government firm on engaging NSCN as single entity. Talks with multiple factions rejected. Interlocutor meets T.R. Zeliang to discuss political framework.', md5('nag-ci-07'),'en',NOW()-INTERVAL '21 days',70.0,'nag-cl-01','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"NE Now News","author_id":"nag-src-04","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.1,"label":"neutral"},"keywords":["NSCN","government","Zeliang","political framework"]}'::jsonb,NOW()-INTERVAL '21 days',NOW(),'org_cyber'),
('nag-ci-08','nag-topic-01','nag-src-05','https://t.me/naga_updates/1240','Civil society demands peace','Civil society groups demand immediate resumption of peace talks. Joint statement signed by 15 organizations. Call for ceasefire monitoring mechanism.', md5('nag-ci-08'),'en',NOW()-INTERVAL '20 days',45.0,'nag-cl-01','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_updates","author_id":"naga_updates","engagement":{"likes":56,"comments":23,"shares":0,"views":1500,"forwards":12},"sentiment":{"compound":0.2,"label":"positive"},"keywords":["civil society","peace talks","ceasefire","monitoring"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_cyber'),
('nag-ci-09','nag-topic-01','nag-src-07','https://t.me/dimapur_connect/345','Dimapur rally for peace','Thousands join Dimapur peace rally organized by student unions. Banners reading "Nagas want peace not war". Heavy security deployed.', md5('nag-ci-09'),'en',NOW()-INTERVAL '19 days',40.0,'nag-cl-01','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@dimapur_connect","author_id":"dimapur_connect","engagement":{"likes":78,"comments":45,"shares":0,"views":2100,"forwards":30},"sentiment":{"compound":0.35,"label":"positive"},"keywords":["Dimapur","peace rally","student unions","Nagas"]}'::jsonb,NOW()-INTERVAL '19 days',NOW(),'org_cyber'),
('nag-ci-10','nag-topic-01','nag-src-09','https://instagram.com/p/nscn_peace','Instagram post on peace march','Photos from the massive peace march in Kohima. Naga civil society united for peace. Powerful images of traditional shawl-wearing elders leading the march.', md5('nag-ci-10'),'en',NOW()-INTERVAL '18 days',55.0,'nag-cl-01','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@northeast_voices","author_id":"northeast_voices","engagement":{"likes":340,"comments":45,"shares":89,"views":4500},"sentiment":{"compound":0.5,"label":"positive"},"keywords":["peace march","Kohima","Naga","civil society"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_cyber'),
('nag-ci-11','nag-topic-01','nag-src-01','https://nagalandtribune.in/ceasefire-extended','Ceasefire extension announced','Government announces 6-month extension of ceasefire with NSCN-IM. Both sides agree to continue talks. Muivah welcomed the decision.', md5('nag-ci-11'),'en',NOW()-INTERVAL '16 days',78.0,'nag-cl-01','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Nagaland Tribune","author_id":"nag-src-01","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.4,"label":"positive"},"keywords":["ceasefire","extension","NSCN-IM","Muivah"]}'::jsonb,NOW()-INTERVAL '16 days',NOW(),'org_cyber'),
('nag-ci-12','nag-topic-01','nag-src-06','https://t.me/kohima_pulse/580','Ceasefire extension reaction','Mixed reactions to ceasefire extension. NSCN-K says they were not consulted. Tribal bodies cautiously optimistic. Ground situation remains fragile.', md5('nag-ci-12'),'en',NOW()-INTERVAL '15 days',52.0,'nag-cl-01','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@kohima_pulse","author_id":"kohima_pulse","engagement":{"likes":45,"comments":56,"shares":0,"views":1800,"forwards":20},"sentiment":{"compound":-0.15,"label":"neutral"},"keywords":["ceasefire","extension","NSCN-K","tribal","fragile"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_cyber'),

-- ── Cluster 2: Drug Trafficking (10 items, days 10-25) ──
('nag-ci-13','nag-topic-01','nag-src-12','https://nedruwatch.example.com/seizure-moreh','Major drug seizure at Moreh','Massive drug seizure at Moreh border checkpoint. 50 kg methamphetamine worth Rs 25 crore intercepted. Two Myanmar nationals arrested. NCB teams deployed.', md5('nag-ci-13'),'en',NOW()-INTERVAL '26 days',65.0,'nag-cl-02','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"NE Drug Watch","author_id":"nag-src-12","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.6,"label":"negative"},"keywords":["drugs","seizure","Moreh","methamphetamine","NCB"]}'::jsonb,NOW()-INTERVAL '26 days',NOW(),'org_cyber'),
('nag-ci-14','nag-topic-01','nag-src-08','https://t.me/ne_underground_watch/92','New drug route via Tuensang','Sources confirm new drug route from Myanmar via Tuensang district bypassing Moreh. Smaller quantities, multiple carriers. Contact +91-98765-43210 for info.', md5('nag-ci-14'),'en',NOW()-INTERVAL '24 days',35.0,'nag-cl-02','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@ne_underground_watch","author_id":"ne_underground_watch","engagement":{"likes":5,"comments":12,"shares":0,"views":340,"forwards":8},"sentiment":{"compound":-0.7,"label":"negative"},"keywords":["drug route","Tuensang","Myanmar","carriers"]}'::jsonb,NOW()-INTERVAL '24 days',NOW(),'org_cyber'),
('nag-ci-15','nag-topic-01','nag-src-05','https://t.me/naga_updates/1245','Heroin epidemic warning','Heroin addiction reaching epidemic levels in Dimapur and Kohima. Youth groups demand government action. Rehabilitation centers overwhelmed. Contact helpline +91-98765-43210.', md5('nag-ci-15'),'en',NOW()-INTERVAL '22 days',45.0,'nag-cl-02','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_updates","author_id":"naga_updates","engagement":{"likes":67,"comments":89,"shares":0,"views":2300,"forwards":35},"sentiment":{"compound":-0.8,"label":"negative"},"keywords":["heroin","epidemic","Dimapur","Kohima","rehabilitation"]}'::jsonb,NOW()-INTERVAL '22 days',NOW(),'org_cyber'),
('nag-ci-16','nag-topic-01','nag-src-07','https://t.me/dimapur_connect/350','Drug peddler arrested Dimapur','Dimapur police arrest drug peddler with 2 kg heroin near railway station. Suspect linked to cross-border syndicate. Phone +91-87654-32109 found in contacts.', md5('nag-ci-16'),'en',NOW()-INTERVAL '20 days',40.0,'nag-cl-02','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@dimapur_connect","author_id":"dimapur_connect","engagement":{"likes":23,"comments":34,"shares":0,"views":890,"forwards":12},"sentiment":{"compound":-0.55,"label":"negative"},"keywords":["drug peddler","heroin","Dimapur","arrest","syndicate"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_cyber'),
('nag-ci-17','nag-topic-01','nag-src-02','https://easternmirrornagaland.com/drug-crisis','NE drug crisis deepens','Eastern Mirror investigation: Northeast drug crisis deepens as Myanmar conflict pushes production into border areas. Moreh-Imphal-Dimapur corridor now primary route.', md5('nag-ci-17'),'en',NOW()-INTERVAL '18 days',82.0,'nag-cl-02','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Eastern Mirror","author_id":"nag-src-02","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.65,"label":"negative"},"keywords":["drug crisis","Myanmar","Moreh","Imphal","Dimapur","corridor"]}'::jsonb,NOW()-INTERVAL '18 days',NOW(),'org_cyber'),
('nag-ci-18','nag-topic-01','nag-src-08','https://t.me/ne_underground_watch/95','Drug lab busted Mon','Drug manufacturing lab busted in Mon district. Synthetic drugs being produced locally. Links to NSCN-K for protection money. Huge operation.', md5('nag-ci-18'),'en',NOW()-INTERVAL '15 days',35.0,'nag-cl-02','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@ne_underground_watch","author_id":"ne_underground_watch","engagement":{"likes":8,"comments":15,"shares":0,"views":450,"forwards":10},"sentiment":{"compound":-0.75,"label":"negative"},"keywords":["drug lab","Mon","synthetic drugs","NSCN-K"]}'::jsonb,NOW()-INTERVAL '15 days',NOW(),'org_cyber'),
('nag-ci-19','nag-topic-01','nag-src-04','https://nenow.in/ncb-northeast','NCB deploys special teams','NCB deploys 4 special teams across Northeast. Focus on Moreh, Dimapur, Guwahati, and Imphal. Inter-state coordination meeting held.', md5('nag-ci-19'),'en',NOW()-INTERVAL '12 days',70.0,'nag-cl-02','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"NE Now News","author_id":"nag-src-04","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.3,"label":"negative"},"keywords":["NCB","Northeast","Moreh","Dimapur","coordination"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_cyber'),
('nag-ci-20','nag-topic-01','nag-src-06','https://t.me/kohima_pulse/590','Anti-drug rally Kohima','Massive anti-drug rally in Kohima. Mothers Against Drugs organization leads march. Thousands participate demanding strict action.', md5('nag-ci-20'),'en',NOW()-INTERVAL '10 days',52.0,'nag-cl-02','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@kohima_pulse","author_id":"kohima_pulse","engagement":{"likes":120,"comments":78,"shares":0,"views":3200,"forwards":45},"sentiment":{"compound":0.1,"label":"neutral"},"keywords":["anti-drug","rally","Kohima","Mothers Against Drugs"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_cyber'),
('nag-ci-21','nag-topic-01','nag-src-11','https://instagram.com/p/drug_seizure','Instagram drug awareness','Manipur Alert posts infographic on drug seizure statistics in NE India. 300% increase in meth seizures this year. Cross-border routes mapped.', md5('nag-ci-21'),'en',NOW()-INTERVAL '8 days',48.0,'nag-cl-02','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@manipur_alert","author_id":"manipur_alert","engagement":{"likes":210,"comments":34,"shares":67,"views":3800},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["drug seizure","NE India","meth","cross-border"]}'::jsonb,NOW()-INTERVAL '8 days',NOW(),'org_cyber'),
('nag-ci-22','nag-topic-01','nag-src-05','https://t.me/naga_updates/1260','Demand for drug-free Nagaland','Youth organizations launch "Drug-Free Nagaland" campaign on social media. Hashtag trending. Community vigilance committees being formed.', md5('nag-ci-22'),'en',NOW()-INTERVAL '6 days',45.0,'nag-cl-02','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_updates","author_id":"naga_updates","engagement":{"likes":89,"comments":56,"shares":0,"views":2800,"forwards":22},"sentiment":{"compound":0.3,"label":"positive"},"keywords":["Drug-Free Nagaland","youth","campaign","vigilance"]}'::jsonb,NOW()-INTERVAL '6 days',NOW(),'org_cyber'),

-- ── Cluster 3: Hornbill Festival (8 items, days 10-20) ──
('nag-ci-23','nag-topic-01','nag-src-10','https://instagram.com/p/hornbill_prep','Hornbill Festival prep photos','Stunning photos from Kisama Heritage Village as preparations begin for Hornbill Festival. Traditional Naga morung houses being restored. Artisans at work.', md5('nag-ci-23'),'en',NOW()-INTERVAL '20 days',60.0,'nag-cl-03','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_heritage_official","author_id":"naga_heritage_official","engagement":{"likes":450,"comments":67,"shares":120,"views":5200},"sentiment":{"compound":0.75,"label":"positive"},"keywords":["Hornbill Festival","Kisama","heritage","traditional","Naga"]}'::jsonb,NOW()-INTERVAL '20 days',NOW(),'org_cyber'),
('nag-ci-24','nag-topic-01','nag-src-01','https://nagalandtribune.in/hornbill-2026','Hornbill Festival 2026 dates','Nagaland Tourism announces Hornbill Festival dates: December 1-10 at Kisama Heritage Village. Theme: "Unity in Diversity". International artists invited.', md5('nag-ci-24'),'en',NOW()-INTERVAL '19 days',78.0,'nag-cl-03','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Nagaland Tribune","author_id":"nag-src-01","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.6,"label":"positive"},"keywords":["Hornbill Festival","Kisama","tourism","December"]}'::jsonb,NOW()-INTERVAL '19 days',NOW(),'org_cyber'),
('nag-ci-25','nag-topic-01','nag-src-09','https://instagram.com/p/naga_dance','Traditional war dance rehearsal','War dance rehearsal by Ao tribe warriors for Hornbill Festival. Spectacular choreography. 200 dancers practicing daily at Kohima ground.', md5('nag-ci-25'),'en',NOW()-INTERVAL '17 days',55.0,'nag-cl-03','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@northeast_voices","author_id":"northeast_voices","engagement":{"likes":520,"comments":89,"shares":145,"views":6100},"sentiment":{"compound":0.8,"label":"positive"},"keywords":["war dance","Ao tribe","Hornbill Festival","Kohima"]}'::jsonb,NOW()-INTERVAL '17 days',NOW(),'org_cyber'),
('nag-ci-26','nag-topic-01','nag-src-03','https://morungexpress.com/hornbill-security','Security plan for Hornbill','Morung Express: Elaborate security plan announced for Hornbill Festival. 2000 police personnel deployed. CCTV surveillance at all entry points.', md5('nag-ci-26'),'en',NOW()-INTERVAL '16 days',75.0,'nag-cl-03','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Morung Express","author_id":"nag-src-03","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.2,"label":"neutral"},"keywords":["security","Hornbill","police","CCTV","surveillance"]}'::jsonb,NOW()-INTERVAL '16 days',NOW(),'org_cyber'),
('nag-ci-27','nag-topic-01','nag-src-10','https://instagram.com/p/naga_food','Naga cuisine showcase','Naga Heritage showcases traditional cuisine for Hornbill Festival. Smoked pork with raja mirchi, bamboo steamed fish, fermented soybean dishes.', md5('nag-ci-27'),'en',NOW()-INTERVAL '14 days',60.0,'nag-cl-03','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_heritage_official","author_id":"naga_heritage_official","engagement":{"likes":380,"comments":56,"shares":95,"views":4800},"sentiment":{"compound":0.7,"label":"positive"},"keywords":["Naga cuisine","Hornbill","smoked pork","traditional food"]}'::jsonb,NOW()-INTERVAL '14 days',NOW(),'org_cyber'),
('nag-ci-28','nag-topic-01','nag-src-05','https://t.me/naga_updates/1255','Hornbill tourism boost','Tourism dept expects 50,000 visitors at Hornbill 2026. Hotels fully booked in Kohima. New homestay initiative launched for villages near Kisama.', md5('nag-ci-28'),'en',NOW()-INTERVAL '13 days',45.0,'nag-cl-03','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_updates","author_id":"naga_updates","engagement":{"likes":45,"comments":23,"shares":0,"views":1200,"forwards":8},"sentiment":{"compound":0.55,"label":"positive"},"keywords":["tourism","Hornbill","Kohima","homestay","Kisama"]}'::jsonb,NOW()-INTERVAL '13 days',NOW(),'org_cyber'),
('nag-ci-29','nag-topic-01','nag-src-11','https://instagram.com/p/ne_hornbill','Northeast artists at Hornbill','Northeast artists from 7 states to perform at Hornbill Festival. Music, dance, and art workshops planned. Celebrating shared tribal heritage.', md5('nag-ci-29'),'en',NOW()-INTERVAL '12 days',48.0,'nag-cl-03','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@manipur_alert","author_id":"manipur_alert","engagement":{"likes":180,"comments":28,"shares":45,"views":2900},"sentiment":{"compound":0.65,"label":"positive"},"keywords":["Northeast","artists","Hornbill","tribal heritage","music"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_cyber'),
('nag-ci-30','nag-topic-01','nag-src-02','https://easternmirrornagaland.com/hornbill-eco','Eco-friendly Hornbill push','Eastern Mirror: Hornbill Festival goes eco-friendly. Ban on single-use plastic. Bamboo alternatives for cups and plates. Green initiatives applauded.', md5('nag-ci-30'),'en',NOW()-INTERVAL '11 days',82.0,'nag-cl-03','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Eastern Mirror","author_id":"nag-src-02","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.5,"label":"positive"},"keywords":["eco-friendly","Hornbill","plastic ban","bamboo","green"]}'::jsonb,NOW()-INTERVAL '11 days',NOW(),'org_cyber'),

-- ── Cluster 4: AFSPA Debate (12 items, days 1-12) ──
('nag-ci-31','nag-topic-01','nag-src-02','https://easternmirrornagaland.com/afspa-debate','AFSPA repeal demand intensifies','Eastern Mirror editorial: AFSPA repeal demand intensifies after alleged extrajudicial killing in Mon district. Civil society groups unite against draconian law.', md5('nag-ci-31'),'en',NOW()-INTERVAL '12 days',82.0,'nag-cl-04','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Eastern Mirror","author_id":"nag-src-02","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.55,"label":"negative"},"keywords":["AFSPA","repeal","Mon","extrajudicial","civil society"]}'::jsonb,NOW()-INTERVAL '12 days',NOW(),'org_cyber'),
('nag-ci-32','nag-topic-01','nag-src-05','https://t.me/naga_updates/1265','Protest march against AFSPA','Massive protest march against AFSPA in Kohima. 10,000+ participants. Effigies burned. Demands include immediate withdrawal from civilian areas.', md5('nag-ci-32'),'en',NOW()-INTERVAL '11 days',45.0,'nag-cl-04','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_updates","author_id":"naga_updates","engagement":{"likes":156,"comments":123,"shares":0,"views":4500,"forwards":55},"sentiment":{"compound":-0.6,"label":"negative"},"keywords":["AFSPA","protest","Kohima","withdrawal"]}'::jsonb,NOW()-INTERVAL '11 days',NOW(),'org_cyber'),
('nag-ci-33','nag-topic-01','nag-src-06','https://t.me/kohima_pulse/595','Student boycott over AFSPA','All Nagaland student unions call for class boycott in solidarity with AFSPA victims. Universities in Kohima and Dimapur participate. Academic calendar disrupted.', md5('nag-ci-33'),'en',NOW()-INTERVAL '10 days',52.0,'nag-cl-04','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@kohima_pulse","author_id":"kohima_pulse","engagement":{"likes":89,"comments":67,"shares":0,"views":2800,"forwards":35},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["student boycott","AFSPA","Kohima","Dimapur","universities"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_cyber'),
('nag-ci-34','nag-topic-01','nag-src-09','https://instagram.com/p/afspa_protest','Protest images go viral','Powerful protest images from Kohima go viral on Instagram. Young Naga woman holding "Remove AFSPA" placard becomes symbol of movement.', md5('nag-ci-34'),'en',NOW()-INTERVAL '9 days',55.0,'nag-cl-04','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@northeast_voices","author_id":"northeast_voices","engagement":{"likes":890,"comments":234,"shares":345,"views":12000},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["AFSPA","protest","Kohima","viral","Naga woman"]}'::jsonb,NOW()-INTERVAL '9 days',NOW(),'org_cyber'),
('nag-ci-35','nag-topic-01','nag-src-01','https://nagalandtribune.in/afspa-panel','Government panel on AFSPA','Government announces 3-member panel to review AFSPA implementation in Nagaland. Panel to submit report in 90 days. Opposition calls it delaying tactic.', md5('nag-ci-35'),'en',NOW()-INTERVAL '8 days',78.0,'nag-cl-04','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Nagaland Tribune","author_id":"nag-src-01","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.2,"label":"negative"},"keywords":["AFSPA","government panel","review","Nagaland"]}'::jsonb,NOW()-INTERVAL '8 days',NOW(),'org_cyber'),
('nag-ci-36','nag-topic-01','nag-src-07','https://t.me/dimapur_connect/360','Dimapur candlelight vigil','Candlelight vigil in Dimapur for AFSPA victims. Hundreds gather at city center. Speeches by tribal leaders and human rights activists.', md5('nag-ci-36'),'en',NOW()-INTERVAL '7 days',40.0,'nag-cl-04','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@dimapur_connect","author_id":"dimapur_connect","engagement":{"likes":67,"comments":45,"shares":0,"views":1900,"forwards":18},"sentiment":{"compound":-0.35,"label":"negative"},"keywords":["Dimapur","candlelight vigil","AFSPA","human rights"]}'::jsonb,NOW()-INTERVAL '7 days',NOW(),'org_cyber'),
('nag-ci-37','nag-topic-01','nag-src-08','https://t.me/ne_underground_watch/98','Security forces on alert','Security forces on high alert across Nagaland. Additional battalions deployed. Curfew imposed in parts of Mon and Tuensang. Tensions rising.', md5('nag-ci-37'),'en',NOW()-INTERVAL '6 days',35.0,'nag-cl-04','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@ne_underground_watch","author_id":"ne_underground_watch","engagement":{"likes":15,"comments":23,"shares":0,"views":560,"forwards":9},"sentiment":{"compound":-0.65,"label":"negative"},"keywords":["security forces","alert","curfew","Mon","Tuensang"]}'::jsonb,NOW()-INTERVAL '6 days',NOW(),'org_cyber'),
('nag-ci-38','nag-topic-01','nag-src-03','https://morungexpress.com/afspa-history','AFSPA: 60 years of debate','Morung Express deep dive: AFSPA in Northeast India — 60 years of debate, protests, and partial withdrawals. Timeline of key events and court rulings.', md5('nag-ci-38'),'en',NOW()-INTERVAL '5 days',75.0,'nag-cl-04','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Morung Express","author_id":"nag-src-03","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.3,"label":"negative"},"keywords":["AFSPA","history","Northeast","protests","court rulings"]}'::jsonb,NOW()-INTERVAL '5 days',NOW(),'org_cyber'),
('nag-ci-39','nag-topic-01','nag-src-10','https://instagram.com/p/naga_identity','Naga identity and AFSPA','Naga Heritage posts: "Our identity is not a threat. Remove AFSPA." Traditional Naga warrior imagery juxtaposed with modern protest photos.', md5('nag-ci-39'),'en',NOW()-INTERVAL '4 days',60.0,'nag-cl-04','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_heritage_official","author_id":"naga_heritage_official","engagement":{"likes":670,"comments":123,"shares":210,"views":8500},"sentiment":{"compound":-0.25,"label":"negative"},"keywords":["Naga identity","AFSPA","warrior","protest"]}'::jsonb,NOW()-INTERVAL '4 days',NOW(),'org_cyber'),
('nag-ci-40','nag-topic-01','nag-src-06','https://t.me/kohima_pulse/600','International attention on AFSPA','International human rights organizations notice Nagaland AFSPA protests. UN rapporteur expresses concern. MHA under pressure.', md5('nag-ci-40'),'en',NOW()-INTERVAL '3 days',52.0,'nag-cl-04','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@kohima_pulse","author_id":"kohima_pulse","engagement":{"likes":95,"comments":78,"shares":0,"views":3100,"forwards":40},"sentiment":{"compound":-0.45,"label":"negative"},"keywords":["international","human rights","UN","AFSPA","MHA"]}'::jsonb,NOW()-INTERVAL '3 days',NOW(),'org_cyber'),
('nag-ci-41','nag-topic-01','nag-src-04','https://nenow.in/afspa-partial','Partial AFSPA withdrawal proposed','NE Now exclusive: Government considering partial AFSPA withdrawal from 3 Nagaland districts. Mon, Tuensang to remain under AFSPA due to security concerns.', md5('nag-ci-41'),'en',NOW()-INTERVAL '2 days',70.0,'nag-cl-04','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"NE Now News","author_id":"nag-src-04","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":0.1,"label":"neutral"},"keywords":["AFSPA","withdrawal","Nagaland","Mon","Tuensang"]}'::jsonb,NOW()-INTERVAL '2 days',NOW(),'org_cyber'),
('nag-ci-42','nag-topic-01','nag-src-05','https://t.me/naga_updates/1275','Response to partial withdrawal','Civil society rejects partial AFSPA withdrawal as insufficient. Demand complete repeal. Warn of intensified protests if demands not met.', md5('nag-ci-42'),'en',NOW()-INTERVAL '1 day',45.0,'nag-cl-04','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_updates","author_id":"naga_updates","engagement":{"likes":134,"comments":98,"shares":0,"views":3800,"forwards":42},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["AFSPA","repeal","civil society","protests"]}'::jsonb,NOW()-INTERVAL '1 day',NOW(),'org_cyber'),

-- ── Cluster 5: Immigration NE Border (8 items, days 1-10) ──
('nag-ci-43','nag-topic-01','nag-src-04','https://nenow.in/myanmar-refugees','Myanmar refugees at Nagaland border','NE Now: Thousands of Myanmar refugees seeking shelter at Nagaland border. Humanitarian crisis developing. State government sets up temporary camps.', md5('nag-ci-43'),'en',NOW()-INTERVAL '10 days',70.0,'nag-cl-05','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"NE Now News","author_id":"nag-src-04","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.35,"label":"negative"},"keywords":["Myanmar","refugees","Nagaland","border","humanitarian"]}'::jsonb,NOW()-INTERVAL '10 days',NOW(),'org_cyber'),
('nag-ci-44','nag-topic-01','nag-src-08','https://t.me/ne_underground_watch/100','Illegal crossing reports','Reports of increased illegal crossings at multiple points along Myanmar-Nagaland border. BSF stretched thin. Intelligence inputs suggest organized networks.', md5('nag-ci-44'),'en',NOW()-INTERVAL '9 days',35.0,'nag-cl-05','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@ne_underground_watch","author_id":"ne_underground_watch","engagement":{"likes":8,"comments":15,"shares":0,"views":420,"forwards":6},"sentiment":{"compound":-0.5,"label":"negative"},"keywords":["illegal crossing","Myanmar","border","BSF","organized"]}'::jsonb,NOW()-INTERVAL '9 days',NOW(),'org_cyber'),
('nag-ci-45','nag-topic-01','nag-src-01','https://nagalandtribune.in/refugee-camps','Refugee camps overwhelmed','Nagaland Tribune: Temporary refugee camps in Mon and Noklak overwhelmed. Food and medical supplies running low. NGOs appeal for donations.', md5('nag-ci-45'),'en',NOW()-INTERVAL '8 days',78.0,'nag-cl-05','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Nagaland Tribune","author_id":"nag-src-01","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.4,"label":"negative"},"keywords":["refugee camps","Mon","Noklak","humanitarian","NGO"]}'::jsonb,NOW()-INTERVAL '8 days',NOW(),'org_cyber'),
('nag-ci-46','nag-topic-01','nag-src-09','https://instagram.com/p/refugee_aid','Volunteer efforts for refugees','Northeast Voices shares photos of volunteer groups providing food and clothing to Myanmar refugees. Community solidarity on display.', md5('nag-ci-46'),'en',NOW()-INTERVAL '7 days',55.0,'nag-cl-05','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@northeast_voices","author_id":"northeast_voices","engagement":{"likes":290,"comments":45,"shares":78,"views":3900},"sentiment":{"compound":0.4,"label":"positive"},"keywords":["volunteers","Myanmar refugees","community","solidarity"]}'::jsonb,NOW()-INTERVAL '7 days',NOW(),'org_cyber'),
('nag-ci-47','nag-topic-01','nag-src-07','https://t.me/dimapur_connect/365','Security concerns border','Local MLA raises security concerns about unvetted refugees entering Nagaland. Demands proper documentation and screening process.', md5('nag-ci-47'),'en',NOW()-INTERVAL '6 days',40.0,'nag-cl-05','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@dimapur_connect","author_id":"dimapur_connect","engagement":{"likes":34,"comments":56,"shares":0,"views":980,"forwards":14},"sentiment":{"compound":-0.3,"label":"negative"},"keywords":["security","refugees","screening","documentation","MLA"]}'::jsonb,NOW()-INTERVAL '6 days',NOW(),'org_cyber'),
('nag-ci-48','nag-topic-01','nag-src-03','https://morungexpress.com/border-fence','Border fencing debate','Morung Express: Border fencing debate reignited. Centre allocates Rs 500 crore for Myanmar border fencing in Nagaland. Tribal groups oppose fence through ancestral lands.', md5('nag-ci-48'),'en',NOW()-INTERVAL '4 days',75.0,'nag-cl-05','{"classification":"OPEN","domain":"osint","owner_org":"cyber","author_handle":"Morung Express","author_id":"nag-src-03","engagement":{"likes":0,"comments":0,"shares":0,"views":0},"sentiment":{"compound":-0.25,"label":"negative"},"keywords":["border fence","Myanmar","Nagaland","tribal","ancestral lands"]}'::jsonb,NOW()-INTERVAL '4 days',NOW(),'org_cyber'),
('nag-ci-49','nag-topic-01','nag-src-06','https://t.me/kohima_pulse/605','UNHCR involvement sought','Civil society demands UNHCR involvement in Myanmar refugee crisis. Government reluctant to internationalize the issue. Debate over refugee vs illegal immigrant status.', md5('nag-ci-49'),'en',NOW()-INTERVAL '3 days',52.0,'nag-cl-05','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@kohima_pulse","author_id":"kohima_pulse","engagement":{"likes":56,"comments":34,"shares":0,"views":1500,"forwards":18},"sentiment":{"compound":-0.2,"label":"negative"},"keywords":["UNHCR","Myanmar","refugee","government","status"]}'::jsonb,NOW()-INTERVAL '3 days',NOW(),'org_cyber'),
('nag-ci-50','nag-topic-01','nag-src-05','https://t.me/naga_updates/1280','Cross-border ethnic ties','Naga Updates: Cross-border ethnic ties complicate immigration policy. Naga tribes on both sides of Myanmar border share kinship. Hard to draw clear lines.', md5('nag-ci-50'),'en',NOW()-INTERVAL '2 days',45.0,'nag-cl-05','{"classification":"OPEN","domain":"social","owner_org":"cyber","author_handle":"@naga_updates","author_id":"naga_updates","engagement":{"likes":67,"comments":45,"shares":0,"views":1800,"forwards":15},"sentiment":{"compound":-0.1,"label":"neutral"},"keywords":["cross-border","ethnic ties","Naga","Myanmar","kinship"]}'::jsonb,NOW()-INTERVAL '2 days',NOW(),'org_cyber')
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 5. Extracted Entities (NER results for entity graph)
-- ==========================================================================
INSERT INTO extracted_entities (id, content_item_id, entity_type, entity_text, created_at, labels) VALUES
-- NSCN Ceasefire entities
('nag-ent-001','nag-ci-01','ORG','NSCN-IM',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-002','nag-ci-01','PERSON','Thuingaleng Muivah',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-003','nag-ci-01','GPE','Delhi',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-004','nag-ci-03','ORG','NSCN-K',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-005','nag-ci-03','ORG','Assam Rifles',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-006','nag-ci-03','GPE','Mon',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-007','nag-ci-04','GPE','Kohima',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-008','nag-ci-05','PERSON','Muivah',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-009','nag-ci-06','GPE','Tuensang',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-010','nag-ci-07','PERSON','T.R. Zeliang',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-011','nag-ci-09','GPE','Dimapur',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
-- Drug trafficking entities
('nag-ent-012','nag-ci-13','GPE','Moreh',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-013','nag-ci-13','ORG','NCB',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-014','nag-ci-14','PHONE_IN','+91-98765-43210',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-015','nag-ci-15','PHONE_IN','+91-98765-43210',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-016','nag-ci-16','PHONE_IN','+91-87654-32109',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-017','nag-ci-17','GPE','Imphal',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-018','nag-ci-18','ORG','NSCN-K',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-019','nag-ci-19','ORG','NCB',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
-- AFSPA entities
('nag-ent-020','nag-ci-31','GPE','Mon',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-021','nag-ci-32','GPE','Kohima',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-022','nag-ci-34','GPE','Kohima',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-023','nag-ci-37','GPE','Mon',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-024','nag-ci-37','GPE','Tuensang',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-025','nag-ci-40','ORG','UN',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-026','nag-ci-40','ORG','MHA',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-027','nag-ci-35','ORG','Indian Army',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
-- Immigration entities
('nag-ent-028','nag-ci-43','GPE','Myanmar',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-029','nag-ci-45','GPE','Noklak',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-030','nag-ci-48','ORG','Centre',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-031','nag-ci-49','ORG','UNHCR',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
-- Hornbill entities
('nag-ent-032','nag-ci-23','EVENT','Hornbill Festival',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-033','nag-ci-23','GPE','Kisama',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-034','nag-ci-25','ORG','Ao tribe',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
('nag-ent-035','nag-ci-01','ORG','NSCN-IM',NOW(),'{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 6. Identifier Clusters (Engine C)
-- ==========================================================================
INSERT INTO identifier_clusters (id, topic_id, identifier_type, identifier_value, source_count, content_item_count, first_seen_at, last_seen_at, created_at, updated_at, labels) VALUES
    ('nag-ic-01', 'nag-topic-01', 'PHONE_IN', '9876543210', 3, 3, NOW()-INTERVAL '24 days', NOW()-INTERVAL '6 days', NOW()-INTERVAL '24 days', NOW(), '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
    ('nag-ic-02', 'nag-topic-01', 'PHONE_IN', '8765432109', 2, 2, NOW()-INTERVAL '20 days', NOW()-INTERVAL '10 days', NOW()-INTERVAL '20 days', NOW(), '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb),
    ('nag-ic-03', 'nag-topic-01', 'TELEGRAM_HANDLE', 'ne_underground_watch', 1, 6, NOW()-INTERVAL '26 days', NOW()-INTERVAL '6 days', NOW()-INTERVAL '26 days', NOW(), '{"classification":"OPEN","domain":"osint","owner_org":"cyber"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO identifier_cluster_items (identifier_cluster_id, content_item_id, source_id) VALUES
    ('nag-ic-01', 'nag-ci-14', 'nag-src-08'),
    ('nag-ic-01', 'nag-ci-15', 'nag-src-05'),
    ('nag-ic-01', 'nag-ci-16', 'nag-src-07'),
    ('nag-ic-02', 'nag-ci-16', 'nag-src-07'),
    ('nag-ic-03', 'nag-ci-06', 'nag-src-08'),
    ('nag-ic-03', 'nag-ci-14', 'nag-src-08'),
    ('nag-ic-03', 'nag-ci-18', 'nag-src-08'),
    ('nag-ic-03', 'nag-ci-37', 'nag-src-08'),
    ('nag-ic-03', 'nag-ci-44', 'nag-src-08')
ON CONFLICT DO NOTHING;

-- ==========================================================================
-- 7. Signals (3)
-- ==========================================================================
INSERT INTO signals (id, topic_id, cluster_id, signal_type, description, evidence, status, created_at, updated_at, labels) VALUES
    ('nag-sig-01', 'nag-topic-01', 'nag-cl-01', 'multi_source_convergence',
     'NSCN ceasefire narrative detected across 4 independent sources (Nagaland Tribune, Eastern Mirror, @naga_updates, @kohima_pulse)',
     '{"independent_source_count":4,"severity":"HIGH"}'::jsonb,
     'new', NOW()-INTERVAL '20 days', NOW(), '{"classification":"OPEN","domain":"signal","owner_org":"cyber"}'::jsonb),
    ('nag-sig-02', 'nag-topic-01', NULL, 'identifier_convergence',
     'Phone number +91-98765-43210 found across 3 independent sources linked to drug trafficking content',
     '{"independent_source_count":3,"severity":"HIGH","identifier_type":"PHONE_IN","identifier_value":"9876543210"}'::jsonb,
     'new', NOW()-INTERVAL '15 days', NOW(), '{"classification":"OPEN","domain":"signal","owner_org":"cyber"}'::jsonb),
    ('nag-sig-03', 'nag-topic-01', 'nag-cl-04', 'multi_source_convergence',
     'AFSPA protest narrative detected across 5 independent sources spanning all platforms',
     '{"independent_source_count":5,"severity":"MEDIUM"}'::jsonb,
     'new', NOW()-INTERVAL '8 days', NOW(), '{"classification":"OPEN","domain":"signal","owner_org":"cyber"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 8. Keyword Alert Rules + Triggers
-- ==========================================================================
INSERT INTO keyword_alert_rules (id, topic_id, keywords, match_mode, is_active, notify_websocket, created_by, org_id, created_at, updated_at, labels) VALUES
    ('nag-alert-01', 'nag-topic-01', ARRAY['NSCN', 'ceasefire', 'violation'], 'any', true, true, 'ec-user-cyber', 'org_cyber', NOW()-INTERVAL '25 days', NOW(), '{"classification":"OPEN","domain":"alert","owner_org":"cyber"}'::jsonb),
    ('nag-alert-02', 'nag-topic-01', ARRAY['drugs', 'heroin', 'seizure', 'Moreh'], 'any', true, true, 'ec-user-cyber', 'org_cyber', NOW()-INTERVAL '25 days', NOW(), '{"classification":"OPEN","domain":"alert","owner_org":"cyber"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO keyword_alert_triggers (id, rule_id, content_item_id, matched_keywords, triggered_at, labels) VALUES
    ('nag-trig-01', 'nag-alert-01', 'nag-ci-03', ARRAY['NSCN', 'ceasefire', 'violation'], NOW()-INTERVAL '25 days', '{"classification":"OPEN","domain":"alert","owner_org":"cyber"}'::jsonb),
    ('nag-trig-02', 'nag-alert-01', 'nag-ci-06', ARRAY['NSCN'], NOW()-INTERVAL '22 days', '{"classification":"OPEN","domain":"alert","owner_org":"cyber"}'::jsonb),
    ('nag-trig-03', 'nag-alert-01', 'nag-ci-12', ARRAY['ceasefire'], NOW()-INTERVAL '15 days', '{"classification":"OPEN","domain":"alert","owner_org":"cyber"}'::jsonb),
    ('nag-trig-04', 'nag-alert-02', 'nag-ci-13', ARRAY['seizure', 'Moreh'], NOW()-INTERVAL '26 days', '{"classification":"OPEN","domain":"alert","owner_org":"cyber"}'::jsonb),
    ('nag-trig-05', 'nag-alert-02', 'nag-ci-15', ARRAY['heroin'], NOW()-INTERVAL '22 days', '{"classification":"OPEN","domain":"alert","owner_org":"cyber"}'::jsonb),
    ('nag-trig-06', 'nag-alert-02', 'nag-ci-17', ARRAY['drugs', 'Moreh'], NOW()-INTERVAL '18 days', '{"classification":"OPEN","domain":"alert","owner_org":"cyber"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ==========================================================================
-- 9. Forwarding Chains (for network graph)
-- ==========================================================================
-- @ne_underground_watch forwards FROM @naga_updates
UPDATE content_items SET forwarded_from_channel_name = 'naga_updates' WHERE id IN ('nag-ci-06', 'nag-ci-14', 'nag-ci-18', 'nag-ci-37', 'nag-ci-44');
-- @dimapur_connect forwards FROM @kohima_pulse
UPDATE content_items SET forwarded_from_channel_name = 'kohima_pulse' WHERE id IN ('nag-ci-09', 'nag-ci-16', 'nag-ci-36', 'nag-ci-47');
-- @kohima_pulse forwards FROM @naga_updates
UPDATE content_items SET forwarded_from_channel_name = 'naga_updates' WHERE id IN ('nag-ci-04', 'nag-ci-12', 'nag-ci-49');

-- ==========================================================================
-- Done. Verify counts:
-- ==========================================================================
SELECT 'Topics' AS entity, COUNT(*) FROM topics WHERE id = 'nag-topic-01'
UNION ALL SELECT 'Sources', COUNT(*) FROM sources WHERE id LIKE 'nag-src-%'
UNION ALL SELECT 'Content Items', COUNT(*) FROM content_items WHERE id LIKE 'nag-ci-%'
UNION ALL SELECT 'Clusters', COUNT(*) FROM narrative_clusters WHERE id LIKE 'nag-cl-%'
UNION ALL SELECT 'Entities', COUNT(*) FROM extracted_entities WHERE id LIKE 'nag-ent-%'
UNION ALL SELECT 'ID Clusters', COUNT(*) FROM identifier_clusters WHERE id LIKE 'nag-ic-%'
UNION ALL SELECT 'Signals', COUNT(*) FROM signals WHERE id LIKE 'nag-sig-%'
UNION ALL SELECT 'Alert Rules', COUNT(*) FROM keyword_alert_rules WHERE id LIKE 'nag-alert-%'
UNION ALL SELECT 'Alert Triggers', COUNT(*) FROM keyword_alert_triggers WHERE id LIKE 'nag-trig-%';
