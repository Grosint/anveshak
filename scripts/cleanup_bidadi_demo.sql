-- ==========================================================================
-- Bidadi Demo — Pre-Demo Cleanup
-- ==========================================================================
-- Run this RIGHT BEFORE the demo to clean up garbage from live scraping.
-- The analyst scheduler cron creates duplicate signals and generic clusters
-- from live RSS content. This script removes them.
--
-- Run: docker exec -i anveshak-postgres-1 psql -U anveshak -d anveshak < scripts/cleanup_bidadi_demo.sql
-- ==========================================================================

BEGIN;

-- 1. Delete auto-generated signals (keep only seed signals)
DELETE FROM signals
WHERE id NOT LIKE 'bidadi-sig-%'
  AND topic_id IN ('bidadi-topic-01','bidadi-topic-02','bidadi-topic-03');

-- 2. Unlink content from garbage clusters
UPDATE content_items SET narrative_cluster_id = NULL
WHERE narrative_cluster_id NOT LIKE 'bidadi-cl-%'
  AND topic_id IN ('bidadi-topic-01','bidadi-topic-02','bidadi-topic-03');

-- 3. Delete garbage clusters
DELETE FROM narrative_clusters
WHERE id NOT LIKE 'bidadi-cl-%'
  AND topic_id IN ('bidadi-topic-01','bidadi-topic-02','bidadi-topic-03');

-- 4. Delete garbage entities from live-scraped content
DELETE FROM extracted_entities
WHERE content_item_id IN (
    SELECT ci.id FROM content_items ci
    WHERE ci.topic_id IN ('bidadi-topic-01','bidadi-topic-02','bidadi-topic-03')
)
AND id NOT LIKE 'bidadi-ent-%';

-- 5. Update some content items to recent timestamps so narratives show "open"
UPDATE content_items SET captured_at = NOW() - INTERVAL '4 hours', updated_at = NOW()
WHERE id IN ('bidadi-ci-06','bidadi-ci-11','bidadi-ci-16','bidadi-ci-20',
             'bidadi-ci-25','bidadi-ci-30','bidadi-ci-35','bidadi-ci-40',
             'bidadi-ci-45','bidadi-ci-49','bidadi-ci-52','bidadi-ci-55');

-- 6. Update cluster updated_at so they look fresh
UPDATE narrative_clusters SET updated_at = NOW()
WHERE id LIKE 'bidadi-cl-%';

COMMIT;

-- Verify
SELECT 'Signals' AS entity, COUNT(*) FROM signals WHERE topic_id IN ('bidadi-topic-01','bidadi-topic-02','bidadi-topic-03')
UNION ALL SELECT 'Clusters', COUNT(*) FROM narrative_clusters WHERE topic_id IN ('bidadi-topic-01','bidadi-topic-02','bidadi-topic-03')
UNION ALL SELECT 'Seed Entities', COUNT(*) FROM extracted_entities WHERE id LIKE 'bidadi-ent-%';

DO $$
BEGIN
    RAISE NOTICE '═══════════════════════════════════════════════════════';
    RAISE NOTICE 'Bidadi Demo Cleanup Complete — ready for demo';
    RAISE NOTICE '═══════════════════════════════════════════════════════';
END $$;
