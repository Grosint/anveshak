-- =============================================================================
-- ANVESHAK — Demo Seed Data
-- Scenario: "Operation Kargil Watch" — IAF OSINT monitoring scenario
-- =============================================================================
-- Usage:
--   make seed-demo
--   # or: psql -U anveshak -d anveshak < scripts/seed_demo.sql
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Demo user account
-- Password: AnveshakDemo2024! (bcrypt hash, rounds=12)
-- Regenerate: uv run python scripts/gen_demo_password.py
-- -----------------------------------------------------------------------------

INSERT INTO users (id, username, password_hash, role, created_at, updated_at, labels)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'demo@anveshak.local',
    '$2b$12$exK0vBQZHOMCPjg37GTJZ.AtYqz1NI5SXwMLrWjnPvP2IqZMZKaei',
    'analyst',
    NOW(),
    NOW(),
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb
)
ON CONFLICT (username) DO NOTHING;

-- Admin user account
-- Password: AnveshakAdmin2024! (bcrypt hash, rounds=12)

INSERT INTO users (id, username, password_hash, role, created_at, updated_at, labels)
VALUES (
    'a0000000-0000-0000-0000-000000000002',
    'admin@anveshak.local',
    '$2b$12$S12K1p/iLSVP3VohoNnP1uxB493/aJIMt6lf/xmUWjJjvTJZHmSt.',
    'admin',
    NOW(),
    NOW(),
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb
)
ON CONFLICT (username) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Topics — OSINT monitoring areas
-- -----------------------------------------------------------------------------

INSERT INTO topics (id, name, keywords, signal_threshold, status, labels, created_at, updated_at)
VALUES
(
    'b0000000-0000-0000-0000-000000000001',
    'China-Pakistan Military Cooperation',
    ARRAY['CPEC', 'PLA', 'PAF', 'Karakoram Highway', 'JF-17', 'Gwadar', 'LAC'],
    3,
    'active',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '7 days',
    NOW()
),
(
    'b0000000-0000-0000-0000-000000000002',
    'UAV Activity Near Northern Borders',
    ARRAY['UAV', 'drone', 'UCAV', 'Wing Loong', 'CH-4', 'Bayraktar', 'unmanned aerial'],
    2,
    'active',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '5 days',
    NOW()
),
(
    'b0000000-0000-0000-0000-000000000003',
    'Disinformation: IAF Operations',
    ARRAY['IAF', 'Indian Air Force', 'Rafale', 'deepfake', 'propaganda', 'disinformation'],
    2,
    'active',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '3 days',
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Sources — credibility-scored OSINT sources
-- -----------------------------------------------------------------------------

INSERT INTO sources (id, name, url_or_handle, platform, credibility_score, is_active, labels, created_at, updated_at)
VALUES
(
    'c0000000-0000-0000-0000-000000000001',
    'Global Security (globalsecurity.org)',
    'https://www.globalsecurity.org',
    'web',
    82.0,
    true,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "source_id": "globalsecurity"}'::jsonb,
    NOW() - INTERVAL '7 days',
    NOW()
),
(
    'c0000000-0000-0000-0000-000000000002',
    'South China Morning Post',
    'https://www.scmp.com',
    'web',
    74.0,
    true,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "source_id": "scmp"}'::jsonb,
    NOW() - INTERVAL '7 days',
    NOW()
),
(
    'c0000000-0000-0000-0000-000000000003',
    'Pakistani Defence Forum (PDF)',
    'https://www.defence.pk',
    'web',
    45.0,
    true,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "source_id": "defence-pk"}'::jsonb,
    NOW() - INTERVAL '7 days',
    NOW()
),
(
    'c0000000-0000-0000-0000-000000000004',
    'Jane''s Defence Weekly',
    'https://www.janes.com',
    'web',
    91.0,
    true,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "source_id": "janes"}'::jsonb,
    NOW() - INTERVAL '7 days',
    NOW()
),
(
    'c0000000-0000-0000-0000-000000000005',
    'Telegram: Defence Updates',
    '@defence_updates',
    'telegram',
    38.0,
    true,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "source_id": "telegram-defence-updates"}'::jsonb,
    NOW() - INTERVAL '4 days',
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Credibility audit log — initial entries
-- -----------------------------------------------------------------------------

INSERT INTO credibility_audit_log (id, source_id, old_score, new_score, reason, changed_by, created_at)
VALUES
(
    'd0000000-0000-0000-0000-000000000001',
    'c0000000-0000-0000-0000-000000000005',
    55.0,
    38.0,
    'Source shared unverified deepfake content 3 times in 30 days — auto-downgrade',
    'system:credibility-auto-update',
    NOW() - INTERVAL '2 days'
)
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Narrative clusters — grouped related content (insert before content_items
-- so content_items.narrative_cluster_id FK can reference them)
-- -----------------------------------------------------------------------------

INSERT INTO narrative_clusters (
    id, topic_id, label, item_count, independent_source_count,
    embedding_centroid, labels, created_at, updated_at
)
VALUES
(
    '00000001-0000-0000-0000-000000000001',
    'b0000000-0000-0000-0000-000000000002',
    'UCAV deployment Hotan Airbase / northern approach vectors',
    1,
    2,
    NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "b0000000-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '3 days',
    NOW() - INTERVAL '3 days'
),
(
    '00000001-0000-0000-0000-000000000002',
    'b0000000-0000-0000-0000-000000000003',
    'Coordinated deepfake campaign targeting IAF Rafale narrative',
    1,
    3,
    NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "b0000000-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '1 day',
    NOW() - INTERVAL '1 day'
)
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Content items — sampled OSINT content
-- -----------------------------------------------------------------------------

INSERT INTO content_items (
    id, topic_id, source_id, url, raw_text, clean_text, content_hash,
    language, captured_at, credibility_score_at_capture, labels, created_at, updated_at,
    narrative_cluster_id
)
VALUES
(
    'e0000000-0000-0000-0000-000000000001',
    'b0000000-0000-0000-0000-000000000001',
    'c0000000-0000-0000-0000-000000000004',
    'https://www.janes.com/defence-news/cpec-security-corridor-2024',
    'China expands CPEC security infrastructure near Gilgit-Baltistan. Chinese engineers have completed new surveillance infrastructure along the China-Pakistan Economic Corridor (CPEC) in Gilgit-Baltistan. The installations include radar arrays and communication relays at altitudes above 4,500m. Pakistani security forces have been trained on Chinese-supplied C4ISR systems.',
    'Chinese engineers have completed new surveillance infrastructure along the China-Pakistan Economic Corridor (CPEC) in Gilgit-Baltistan. The installations include radar arrays and communication relays at altitudes above 4,500m. Pakistani security forces have been trained on Chinese-supplied C4ISR systems.',
    'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f601',
    'en',
    NOW() - INTERVAL '6 days',
    91.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "b0000000-0000-0000-0000-000000000001"}'::jsonb,
    NOW() - INTERVAL '6 days',
    NOW() - INTERVAL '6 days',
    NULL
),
(
    'e0000000-0000-0000-0000-000000000002',
    'b0000000-0000-0000-0000-000000000002',
    'c0000000-0000-0000-0000-000000000001',
    'https://www.globalsecurity.org/wing-loong-iii-deployment',
    'Wing Loong III UCAV spotted at Hotan Airbase — OSINT analysis. Satellite imagery analysis confirms deployment of Wing Loong III unmanned combat aerial vehicles at Hotan Airbase, Xinjiang. The aircraft are assessed to have operational range reaching northern Ladakh. Three sorties observed over 72-hour window.',
    'Satellite imagery analysis confirms deployment of Wing Loong III unmanned combat aerial vehicles at Hotan Airbase, Xinjiang. The aircraft are assessed to have operational range reaching northern Ladakh. Three sorties observed over 72-hour window.',
    'b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6b202',
    'en',
    NOW() - INTERVAL '4 days',
    82.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "b0000000-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '4 days',
    NOW() - INTERVAL '4 days',
    '00000001-0000-0000-0000-000000000001'
),
(
    'e0000000-0000-0000-0000-000000000003',
    'b0000000-0000-0000-0000-000000000003',
    'c0000000-0000-0000-0000-000000000005',
    NULL,
    'Fabricated video: IAF Rafale shot down — DEEPFAKE CONFIRMED. A video circulating on Telegram claims to show an IAF Rafale aircraft being shot down over disputed territory. Vision analysis confirms deepfake probability 0.94. Original source aircraft footage is from a 2019 French Air Force training exercise. Coordinated amplification detected across 12 Telegram channels within 3 hours.',
    'A video circulating on Telegram claims to show an IAF Rafale aircraft being shot down over disputed territory. Vision analysis confirms deepfake probability 0.94. Original source aircraft footage is from a 2019 French Air Force training exercise. Coordinated amplification detected across 12 Telegram channels within 3 hours.',
    'c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6c303',
    'en',
    NOW() - INTERVAL '2 days',
    38.0,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "b0000000-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '2 days',
    NOW() - INTERVAL '2 days',
    '00000001-0000-0000-0000-000000000002'
)
ON CONFLICT (content_hash) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Vision analysis job result
-- -----------------------------------------------------------------------------

INSERT INTO analysis_jobs (
    id, job_type, topic_id, status,
    payload, result, error, labels, created_at, updated_at
)
VALUES
(
    'f0000000-0000-0000-0000-000000000001',
    'vision_analysis',
    'b0000000-0000-0000-0000-000000000003',
    'completed',
    '{"content_item_id": "e0000000-0000-0000-0000-000000000003"}'::jsonb,
    '{
        "deepfake_score": 0.94,
        "deepfake_model": "facetorch",
        "objects_detected": ["aircraft", "explosion"],
        "yolo_model": "yolov8n",
        "exif_anomalies": ["GPS stripped", "software: DALL-E 3"],
        "phash": "deadbeef12345678"
    }'::jsonb,
    NULL,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'::jsonb,
    NOW() - INTERVAL '2 days',
    NOW() - INTERVAL '2 days'
)
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Signals — threshold-based notifications
-- -----------------------------------------------------------------------------

INSERT INTO signals (
    id, topic_id, cluster_id, signal_type,
    description, evidence, status, labels, created_at, updated_at
)
VALUES
(
    '11000000-0000-0000-0000-000000000001',
    'b0000000-0000-0000-0000-000000000003',
    '00000001-0000-0000-0000-000000000002',
    'threshold_breach',
    'Coordinated deepfake campaign detected — 3 independent platforms',
    '{
        "cluster_id": "00000001-0000-0000-0000-000000000002",
        "independent_source_count": 3,
        "deepfake_score": 0.94,
        "platforms": ["telegram", "reddit", "web"]
    }'::jsonb,
    'new',
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "b0000000-0000-0000-0000-000000000003"}'::jsonb,
    NOW() - INTERVAL '1 day',
    NOW() - INTERVAL '1 day'
)
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Sample report (intelligence brief)
-- -----------------------------------------------------------------------------

INSERT INTO reports (
    id, topic_id, report_type,
    time_window_start, time_window_end, credibility_min_filter,
    content_md, generated_at, source_snapshot, content_item_count,
    labels, created_at, updated_at
)
VALUES
(
    '22000000-0000-0000-0000-000000000001',
    'b0000000-0000-0000-0000-000000000002',
    'intelligence_brief',
    NOW() - INTERVAL '7 days',
    NOW(),
    30.0,
    E'## Executive Summary\n\nOpen-source intelligence collected over the past 7 days indicates sustained unmanned aerial vehicle (UAV) activity at Chinese military installations proximate to the Line of Actual Control (LAC). Two independent sources have reported Wing Loong III UCAV deployment at Hotan Airbase.\n\n## Key Findings\n\n1. **Hotan Airbase (Xinjiang)**: OSINT analysis of publicly available satellite imagery confirms presence of what is assessed to be Wing Loong III platforms. These aircraft have a published combat radius of approximately 2,000 km, placing northern Ladakh within operational range.\n\n2. **Operational Pattern**: Three sorties assessed over a 72-hour observation window. Sortie timing correlates with periods of reduced civilian air traffic, suggesting deliberate airspace management.\n\n3. **Supply Chain Indicators**: Open procurement records indicate increased orders for Wing Loong III ground control station components, suggesting expansion beyond current deployment.\n\n## Source Assessment\n\nPrimary source (Jane''s Defence Weekly, credibility: 91%) provides highest-confidence reporting. Secondary corroboration from Global Security (credibility: 82%). No contradicting sources identified in monitoring window.\n\n## Confidence Level\n\nMEDIUM-HIGH. Assessment rests on open-source imagery analysis and procurement record correlation. Direct confirmation of operational sorties would upgrade to HIGH.\n\n*This brief was generated automatically by Anveshak. Analyst review recommended before dissemination.*',
    NOW() - INTERVAL '1 day',
    '{
        "c0000000-0000-0000-0000-000000000004": {"name": "Janes Defence Weekly", "credibility_score": 91.0},
        "c0000000-0000-0000-0000-000000000001": {"name": "Global Security", "credibility_score": 82.0}
    }'::jsonb,
    1,
    '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak", "topic_id": "b0000000-0000-0000-0000-000000000002"}'::jsonb,
    NOW() - INTERVAL '1 day',
    NOW() - INTERVAL '1 day'
)
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- Summary
DO $$
BEGIN
    RAISE NOTICE 'Demo seed complete:';
    RAISE NOTICE '  Users:     2 (demo@anveshak.local / AnveshakDemo2024!, admin@anveshak.local / AnveshakAdmin2024!)';
    RAISE NOTICE '  Topics:    3';
    RAISE NOTICE '  Sources:   5 (credibility-scored)';
    RAISE NOTICE '  Content:   3 items';
    RAISE NOTICE '  Clusters:  2 narrative clusters';
    RAISE NOTICE '  Signals:   1 (HIGH severity — deepfake campaign)';
    RAISE NOTICE '  Reports:   1 (intelligence brief)';
    RAISE NOTICE '';
    RAISE NOTICE 'Login: http://localhost:3000';
    RAISE NOTICE 'Username: demo@anveshak.local';
    RAISE NOTICE 'Password: AnveshakDemo2024!';
END $$;
