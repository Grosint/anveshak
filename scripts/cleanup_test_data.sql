-- cleanup_test_data.sql — Remove orphaned integration-test rows from the database.
-- Run: make clean-test-data
-- Safe: only deletes rows matching test-data naming patterns.

BEGIN;

-- 1. Collect test topic IDs
CREATE TEMP TABLE _test_topics AS
SELECT id FROM topics WHERE
    name LIKE 'Test Topic %'
    OR name LIKE '%Test Topic'
    OR name LIKE 'Integration Test Topic%'
    OR name LIKE 'Cluster Signal Test Topic%'
    OR name LIKE 'Deepfake Test Topic%'
    OR name LIKE 'Vision Test Topic%'
    OR name LIKE 'Social Test Topic%'
    OR name LIKE 'Signal Test %'
    OR name LIKE 'E2E Validation%';

-- 2. Collect test source IDs
CREATE TEMP TABLE _test_sources AS
SELECT id FROM sources WHERE url_or_handle LIKE '%.example.com';

-- 3. Delete in FK-safe order (deepest children first)

-- vision_results → media_assets → content_items
DELETE FROM vision_results WHERE media_asset_id IN (
    SELECT ma.id FROM media_assets ma
    JOIN content_items ci ON ma.content_item_id = ci.id
    WHERE ci.topic_id IN (SELECT id FROM _test_topics)
);

DELETE FROM media_assets WHERE content_item_id IN (
    SELECT id FROM content_items WHERE topic_id IN (SELECT id FROM _test_topics)
);

-- extracted_entities → content_items
DELETE FROM extracted_entities WHERE content_item_id IN (
    SELECT id FROM content_items WHERE topic_id IN (SELECT id FROM _test_topics)
);

-- report_source_warnings → reports
DELETE FROM report_source_warnings WHERE report_id IN (
    SELECT id FROM reports WHERE topic_id IN (SELECT id FROM _test_topics)
);
DELETE FROM report_source_warnings WHERE source_id IN (
    SELECT id FROM _test_sources
);

-- reports → topics
DELETE FROM reports WHERE topic_id IN (SELECT id FROM _test_topics);

-- near_duplicates → content_items
DELETE FROM near_duplicates WHERE content_item_a_id IN (
    SELECT id FROM content_items WHERE topic_id IN (SELECT id FROM _test_topics)
) OR content_item_b_id IN (
    SELECT id FROM content_items WHERE topic_id IN (SELECT id FROM _test_topics)
);

-- signals → narrative_clusters, topics
DELETE FROM signals WHERE topic_id IN (SELECT id FROM _test_topics);

-- content_items → narrative_clusters (FK: narrative_cluster_id)
-- Must nullify before deleting clusters
UPDATE content_items SET narrative_cluster_id = NULL
WHERE topic_id IN (SELECT id FROM _test_topics) AND narrative_cluster_id IS NOT NULL;

-- narrative_clusters → topics
DELETE FROM narrative_clusters WHERE topic_id IN (SELECT id FROM _test_topics);

-- topic_content_items → content_items, topics
DELETE FROM topic_content_items WHERE topic_id IN (SELECT id FROM _test_topics);

-- content_items → topics, sources
DELETE FROM content_items WHERE topic_id IN (SELECT id FROM _test_topics);

-- topic_sources → topics, sources
DELETE FROM topic_sources WHERE topic_id IN (SELECT id FROM _test_topics);

-- analysis_jobs → topics
DELETE FROM analysis_jobs WHERE topic_id IN (SELECT id FROM _test_topics);

-- credibility_audit_log → sources
DELETE FROM credibility_audit_log WHERE source_id IN (SELECT id FROM _test_sources);

-- Finally: topics and sources
DELETE FROM topics WHERE id IN (SELECT id FROM _test_topics);
DELETE FROM sources WHERE id IN (SELECT id FROM _test_sources);

DROP TABLE _test_topics;
DROP TABLE _test_sources;

COMMIT;
