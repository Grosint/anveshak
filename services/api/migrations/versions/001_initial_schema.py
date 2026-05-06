"""001_initial_schema

Consolidated initial schema for Anveshak OSINT platform.
Squashed from 10 development migrations (001–010) into a single
production-ready schema. No production database existed before this.

Revision ID: 001
Revises:
Create Date: 2026-05-06 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enable required extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE users (
            id            TEXT        NOT NULL PRIMARY KEY,
            username      TEXT        NOT NULL UNIQUE,
            password_hash TEXT        NOT NULL,
            role          TEXT        NOT NULL DEFAULT 'analyst',
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels        JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_users_username ON users(username)")

    # ------------------------------------------------------------------
    # topics
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE topics (
            id                        TEXT        NOT NULL PRIMARY KEY,
            name                      TEXT        NOT NULL,
            keywords                  TEXT[]      NOT NULL DEFAULT '{}',
            languages                 TEXT[]      NOT NULL DEFAULT '{en}',
            credibility_min           FLOAT       NOT NULL DEFAULT 30.0,
            signal_threshold          INT         NOT NULL DEFAULT 3,
            status                    TEXT        NOT NULL DEFAULT 'active',
            clip_categories           TEXT[]      NOT NULL DEFAULT '{}',
            scheduled_report_cron     TEXT,
            scheduled_report_type     TEXT,
            topic_relevance_threshold REAL,
            created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels                    JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_topics_status ON topics(status)")
    op.execute("CREATE INDEX idx_topics_created_at ON topics(created_at DESC)")

    # ------------------------------------------------------------------
    # sources
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE sources (
            id                    TEXT        NOT NULL PRIMARY KEY,
            name                  TEXT        NOT NULL,
            url_or_handle         TEXT        NOT NULL,
            platform              TEXT        NOT NULL,
            credibility_score     FLOAT       NOT NULL DEFAULT 50.0,
            auto_score_enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
            last_checked_at       TIMESTAMPTZ,
            is_active             BOOLEAN     NOT NULL DEFAULT TRUE,
            health_status         TEXT        NOT NULL DEFAULT 'unverified',
            consecutive_failures  INT         NOT NULL DEFAULT 0,
            health_error          TEXT,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels                JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_sources_platform ON sources(platform)")
    op.execute("CREATE INDEX idx_sources_credibility ON sources(credibility_score DESC)")
    op.execute("CREATE INDEX idx_sources_is_active ON sources(is_active)")

    # ------------------------------------------------------------------
    # credibility_audit_log  (immutable — no updated_at)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE credibility_audit_log (
            id          TEXT        NOT NULL PRIMARY KEY,
            source_id   TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            old_score   FLOAT       NOT NULL,
            new_score   FLOAT       NOT NULL,
            reason      TEXT        NOT NULL,
            changed_by  TEXT        NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels      JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_credibility_audit_source ON credibility_audit_log(source_id)")
    op.execute("CREATE INDEX idx_credibility_audit_created ON credibility_audit_log(created_at DESC)")

    # ------------------------------------------------------------------
    # narrative_clusters
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE narrative_clusters (
            id                       TEXT        NOT NULL PRIMARY KEY,
            topic_id                 TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            label                    TEXT        NOT NULL,
            item_count               INT         NOT NULL DEFAULT 0,
            independent_source_count INT         NOT NULL DEFAULT 0,
            embedding_centroid       vector(384),
            archived_at              TIMESTAMPTZ,
            label_generated_at       TIMESTAMPTZ,
            label_item_hash          TEXT,
            executive_summary        TEXT,
            created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels                   JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_clusters_topic ON narrative_clusters(topic_id)")
    op.execute("CREATE INDEX idx_clusters_item_count ON narrative_clusters(item_count DESC)")
    op.execute("""
        CREATE INDEX idx_clusters_archived
        ON narrative_clusters(archived_at)
        WHERE archived_at IS NOT NULL
    """)

    # ------------------------------------------------------------------
    # content_items
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE content_items (
            id                           TEXT        NOT NULL PRIMARY KEY,
            topic_id                     TEXT        REFERENCES topics(id) ON DELETE SET NULL,
            source_id                    TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            narrative_cluster_id         TEXT        REFERENCES narrative_clusters(id) ON DELETE SET NULL,
            raw_text                     TEXT        NOT NULL,
            clean_text                   TEXT        NOT NULL,
            language                     TEXT        NOT NULL DEFAULT 'en',
            translated_text              TEXT,
            translation_model            TEXT,
            content_hash                 TEXT        NOT NULL,
            url                          TEXT,
            captured_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            credibility_score_at_capture FLOAT       NOT NULL DEFAULT 50.0,
            embedding                    vector(384),
            content_quality              TEXT        NOT NULL DEFAULT 'good',
            clean_hash                   TEXT,
            title                        TEXT,
            topic_relevance_score        REAL,
            entity_minhash               BIGINT[],
            created_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels                       JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE UNIQUE INDEX idx_content_items_hash ON content_items(content_hash)")
    op.execute("CREATE INDEX idx_content_items_topic ON content_items(topic_id)")
    op.execute("CREATE INDEX idx_content_items_source ON content_items(source_id)")
    op.execute("CREATE INDEX idx_content_items_captured ON content_items(captured_at DESC)")
    op.execute("CREATE INDEX idx_content_items_cluster ON content_items(narrative_cluster_id) WHERE narrative_cluster_id IS NOT NULL")
    op.execute("CREATE INDEX idx_content_items_translated ON content_items(language) WHERE translated_text IS NOT NULL")
    op.execute("CREATE INDEX idx_content_items_clean_hash ON content_items(clean_hash)")
    op.execute("CREATE INDEX idx_content_items_quality ON content_items(content_quality) WHERE content_quality = 'low_quality'")
    op.execute("""
        CREATE INDEX idx_content_items_relevance
        ON content_items (topic_id, topic_relevance_score)
        WHERE embedding IS NOT NULL
    """)
    # HNSW index for approximate nearest-neighbour vector search
    # m=16: max connections per layer, ef_construction=64: build-time search width
    op.execute("""
        CREATE INDEX idx_content_items_embedding
        ON content_items
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # ------------------------------------------------------------------
    # extracted_entities
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE extracted_entities (
            id              TEXT        NOT NULL PRIMARY KEY,
            content_item_id TEXT        NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            entity_type     TEXT        NOT NULL,
            entity_text     TEXT        NOT NULL,
            confidence      FLOAT       NOT NULL DEFAULT 1.0,
            language        TEXT        NOT NULL DEFAULT 'en',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels          JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_entities_content_item ON extracted_entities(content_item_id)")
    op.execute("CREATE INDEX idx_entities_type_text ON extracted_entities(entity_type, entity_text)")
    op.execute("""
        CREATE INDEX idx_entities_text_trgm
        ON extracted_entities
        USING gin (entity_text gin_trgm_ops)
    """)

    # ------------------------------------------------------------------
    # media_assets
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE media_assets (
            id              TEXT        NOT NULL PRIMARY KEY,
            content_item_id TEXT        NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            asset_type      TEXT        NOT NULL,
            storage_path    TEXT        NOT NULL,
            content_hash    TEXT        NOT NULL,
            exif_data       JSONB,
            phash           BIGINT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels          JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE UNIQUE INDEX idx_media_assets_hash ON media_assets(content_hash)")
    op.execute("CREATE INDEX idx_media_assets_content_item ON media_assets(content_item_id)")
    op.execute("CREATE INDEX idx_media_assets_type ON media_assets(asset_type)")

    # ------------------------------------------------------------------
    # vision_results
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE vision_results (
            id                    TEXT        NOT NULL PRIMARY KEY,
            media_asset_id        TEXT        NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
            yolo_detections       JSONB,
            clip_labels           JSONB,
            deepfake_score        FLOAT,
            deepfake_model        TEXT,
            synthetic_probability FLOAT,
            processed_at          TIMESTAMPTZ,
            labels                JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE UNIQUE INDEX idx_vision_results_asset ON vision_results(media_asset_id)")
    op.execute("CREATE INDEX idx_vision_results_deepfake ON vision_results(deepfake_score DESC) WHERE deepfake_score IS NOT NULL")

    # ------------------------------------------------------------------
    # signals
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE signals (
            id           TEXT        NOT NULL PRIMARY KEY,
            topic_id     TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            signal_type  TEXT        NOT NULL,
            description  TEXT        NOT NULL,
            evidence     JSONB       NOT NULL DEFAULT '{}'::jsonb,
            status       TEXT        NOT NULL DEFAULT 'new',
            cluster_id   TEXT        REFERENCES narrative_clusters(id) ON DELETE SET NULL,
            delivered_at TIMESTAMPTZ,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels       JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_signals_topic_status ON signals(topic_id, status)")
    op.execute("CREATE INDEX idx_signals_status ON signals(status)")
    op.execute("CREATE INDEX idx_signals_created ON signals(created_at DESC)")
    op.execute("CREATE INDEX idx_signals_undelivered ON signals(created_at ASC) WHERE delivered_at IS NULL")
    op.execute("""
        CREATE INDEX idx_signals_cross_topic
        ON signals(signal_type)
        WHERE signal_type = 'cross_topic_convergence'
    """)

    # ------------------------------------------------------------------
    # analysis_jobs
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE analysis_jobs (
            id          TEXT        NOT NULL PRIMARY KEY,
            job_type    TEXT        NOT NULL,
            topic_id    TEXT        REFERENCES topics(id) ON DELETE SET NULL,
            status      TEXT        NOT NULL DEFAULT 'queued',
            payload     JSONB       NOT NULL DEFAULT '{}'::jsonb,
            result      JSONB,
            error       TEXT,
            arq_job_id  TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels      JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_jobs_status_type ON analysis_jobs(status, job_type)")
    op.execute("CREATE INDEX idx_jobs_topic ON analysis_jobs(topic_id)")
    op.execute("CREATE INDEX idx_jobs_arq_id ON analysis_jobs(arq_job_id) WHERE arq_job_id IS NOT NULL")

    # ------------------------------------------------------------------
    # reports  (immutable once generated_at is set)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE reports (
            id                     TEXT        NOT NULL PRIMARY KEY,
            topic_id               TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            report_type            TEXT        NOT NULL,
            time_window_start      TIMESTAMPTZ NOT NULL,
            time_window_end        TIMESTAMPTZ NOT NULL,
            credibility_min_filter FLOAT       NOT NULL DEFAULT 30.0,
            content_md             TEXT,
            content_html           TEXT,
            pdf_path               TEXT,
            geojson                JSONB,
            confidence_score       FLOAT,
            generated_at           TIMESTAMPTZ,
            generation_error       TEXT,
            source_snapshot        JSONB       NOT NULL DEFAULT '{}'::jsonb,
            content_item_count     INT         NOT NULL DEFAULT 0,
            created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels                 JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_reports_topic ON reports(topic_id)")
    op.execute("CREATE INDEX idx_reports_type ON reports(report_type)")
    op.execute("CREATE INDEX idx_reports_generated ON reports(generated_at DESC) WHERE generated_at IS NOT NULL")
    op.execute("CREATE INDEX idx_reports_window ON reports(time_window_end DESC)")

    # ------------------------------------------------------------------
    # report_source_warnings
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE report_source_warnings (
            id           TEXT        NOT NULL PRIMARY KEY,
            report_id    TEXT        NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            source_id    TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            source_name  TEXT        NOT NULL,
            warning_type TEXT        NOT NULL DEFAULT 'credibility_downgraded',
            old_score    FLOAT       NOT NULL,
            new_score    FLOAT       NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels       JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_report_warnings_report ON report_source_warnings(report_id)")
    op.execute("CREATE INDEX idx_report_warnings_source ON report_source_warnings(source_id)")
    op.execute("CREATE UNIQUE INDEX uq_report_source_warnings_pair ON report_source_warnings(report_id, source_id)")

    # ------------------------------------------------------------------
    # topic_content_items  (join table)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE topic_content_items (
            topic_id         TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            content_item_id  TEXT        NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            similarity_score FLOAT       NOT NULL DEFAULT 0.0,
            assigned_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (topic_id, content_item_id)
        )
    """)
    op.execute("CREATE INDEX idx_topic_content_items_topic ON topic_content_items(topic_id)")
    op.execute("CREATE INDEX idx_topic_content_items_item ON topic_content_items(content_item_id)")

    # ------------------------------------------------------------------
    # topic_sources  (join table — topics ↔ sources)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE topic_sources (
            topic_id  TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            source_id TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            added_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (topic_id, source_id)
        )
    """)

    # ------------------------------------------------------------------
    # near_duplicates  (semantic dedup)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE near_duplicates (
            content_item_a_id TEXT  NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            content_item_b_id TEXT  NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            similarity_score  FLOAT NOT NULL,
            detected_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels            JSONB NOT NULL DEFAULT
                '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb,
            PRIMARY KEY (content_item_a_id, content_item_b_id),
            CHECK (content_item_a_id < content_item_b_id)
        )
    """)
    op.execute("CREATE INDEX idx_near_dup_a ON near_duplicates(content_item_a_id)")
    op.execute("CREATE INDEX idx_near_dup_b ON near_duplicates(content_item_b_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS near_duplicates CASCADE")
    op.execute("DROP TABLE IF EXISTS topic_sources CASCADE")
    op.execute("DROP TABLE IF EXISTS topic_content_items CASCADE")
    op.execute("DROP TABLE IF EXISTS report_source_warnings CASCADE")
    op.execute("DROP TABLE IF EXISTS reports CASCADE")
    op.execute("DROP TABLE IF EXISTS analysis_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS signals CASCADE")
    op.execute("DROP TABLE IF EXISTS vision_results CASCADE")
    op.execute("DROP TABLE IF EXISTS media_assets CASCADE")
    op.execute("DROP TABLE IF EXISTS extracted_entities CASCADE")
    op.execute("DROP TABLE IF EXISTS content_items CASCADE")
    op.execute("DROP TABLE IF EXISTS narrative_clusters CASCADE")
    op.execute("DROP TABLE IF EXISTS credibility_audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS sources CASCADE")
    op.execute("DROP TABLE IF EXISTS topics CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
