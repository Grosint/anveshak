"""001_initial_schema

Consolidated initial schema for Anveshak OSINT platform.
Squashed from 13 development migrations (001–013) into a single
production-ready schema. No production database existed before this.

Tables: 35 (including join tables)
Extensions: vector, pg_trgm, btree_gin, uuid-ossp
RLS: content_items, topics, users, credibility_audit_log
Worker role: anveshak_worker (BYPASSRLS)

Revision ID: 001
Revises:
Create Date: 2026-06-25 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==================================================================
    # Extensions
    # ==================================================================
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gin")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ==================================================================
    # Root tables (no FK dependencies)
    # ==================================================================

    # -- organizations
    op.execute("""
        CREATE TABLE organizations (
            id         TEXT        NOT NULL PRIMARY KEY,
            name       TEXT        NOT NULL UNIQUE,
            slug       TEXT        NOT NULL UNIQUE,
            is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels     JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)

    # -- users
    op.execute("""
        CREATE TABLE users (
            id            TEXT        NOT NULL PRIMARY KEY,
            username      TEXT        NOT NULL UNIQUE,
            password_hash TEXT        NOT NULL,
            role          TEXT        NOT NULL DEFAULT 'analyst',
            org_id        TEXT        REFERENCES organizations(id),
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels        JSONB       NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT chk_users_role CHECK (
                role IN ('super-admin', 'admin', 'analyst', 'viewer')
            )
        )
    """)
    op.execute("CREATE INDEX idx_users_username ON users(username)")
    op.execute("CREATE INDEX idx_users_org ON users(org_id)")

    # -- topics
    op.execute("""
        CREATE TABLE topics (
            id                          TEXT        NOT NULL PRIMARY KEY,
            name                        TEXT        NOT NULL,
            keywords                    TEXT[]      NOT NULL DEFAULT '{}',
            languages                   TEXT[]      NOT NULL DEFAULT '{en}',
            credibility_min             FLOAT8      NOT NULL DEFAULT 30.0,
            signal_threshold            INTEGER     NOT NULL DEFAULT 3,
            status                      TEXT        NOT NULL DEFAULT 'active',
            clip_categories             TEXT[]      NOT NULL DEFAULT '{}',
            scheduled_report_cron       TEXT,
            scheduled_report_type       TEXT,
            topic_relevance_threshold   REAL,
            identifier_signal_threshold INTEGER     NOT NULL DEFAULT 2,
            org_id                      TEXT        NOT NULL REFERENCES organizations(id),
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels                      JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_topics_status ON topics(status)")
    op.execute("CREATE INDEX idx_topics_created_at ON topics(created_at DESC)")
    op.execute("CREATE INDEX idx_topics_org ON topics(org_id)")

    # -- sources
    op.execute("""
        CREATE TABLE sources (
            id                    TEXT        NOT NULL PRIMARY KEY,
            name                  TEXT        NOT NULL,
            url_or_handle         TEXT        NOT NULL,
            platform              TEXT        NOT NULL,
            credibility_score     FLOAT8      NOT NULL DEFAULT 50.0,
            auto_score_enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
            last_checked_at       TIMESTAMPTZ,
            is_active             BOOLEAN     NOT NULL DEFAULT TRUE,
            health_status         TEXT        NOT NULL DEFAULT 'unverified',
            consecutive_failures  INTEGER     NOT NULL DEFAULT 0,
            health_error          TEXT,
            org_id                TEXT        NOT NULL,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels                JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_sources_platform ON sources(platform)")
    op.execute("CREATE INDEX idx_sources_credibility ON sources(credibility_score DESC)")
    op.execute("CREATE INDEX idx_sources_is_active ON sources(is_active)")
    op.execute("CREATE INDEX idx_sources_org ON sources(org_id)")

    # -- source_catalog
    op.execute("""
        CREATE TABLE source_catalog (
            id                        TEXT        NOT NULL PRIMARY KEY,
            name                      TEXT        NOT NULL,
            url_or_handle             TEXT        NOT NULL,
            platform                  TEXT        NOT NULL,
            domain_tags               TEXT[]      DEFAULT '{}',
            reliability_tier          TEXT        DEFAULT 'C',
            bias_indicator            TEXT        DEFAULT 'unknown',
            risk_level                TEXT        DEFAULT 'low',
            language                  TEXT        DEFAULT 'en',
            category                  TEXT        DEFAULT 'news',
            description               TEXT        DEFAULT '',
            subscriber_count          INTEGER,
            activity_frequency        TEXT        DEFAULT 'unknown',
            signal_contribution_count INTEGER     DEFAULT 0,
            relevance_hit_rate        REAL,
            cluster_participation_rate REAL,
            topics_approved_count     INTEGER     DEFAULT 0,
            recommendation_rank       TEXT        DEFAULT 'curated',
            created_at                TIMESTAMPTZ DEFAULT NOW(),
            updated_at                TIMESTAMPTZ DEFAULT NOW(),
            labels                    JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX idx_source_catalog_handle ON source_catalog(platform, url_or_handle)"
    )
    op.execute(
        "CREATE INDEX idx_source_catalog_domain_tags ON source_catalog USING gin(domain_tags)"
    )
    op.execute("CREATE INDEX idx_source_catalog_rank ON source_catalog(recommendation_rank)")

    # -- scam_templates
    op.execute("""
        CREATE TABLE scam_templates (
            id                    TEXT        NOT NULL PRIMARY KEY,
            org_id                TEXT        REFERENCES organizations(id),
            name                  TEXT        NOT NULL,
            display               TEXT        NOT NULL,
            category              TEXT        NOT NULL,
            keywords              TEXT[]      NOT NULL DEFAULT '{}',
            min_keyword_hits      INTEGER     NOT NULL DEFAULT 3,
            expected_identifiers  TEXT[]      DEFAULT '{}',
            severity              TEXT        NOT NULL DEFAULT 'MEDIUM',
            reference_embedding   vector(384),
            legal_sections        TEXT[]      DEFAULT '{}',
            is_builtin            BOOLEAN     DEFAULT FALSE,
            is_active             BOOLEAN     DEFAULT TRUE,
            created_at            TIMESTAMPTZ DEFAULT NOW(),
            updated_at            TIMESTAMPTZ DEFAULT NOW(),
            labels                JSONB       NOT NULL DEFAULT '{"domain":"osint","owner_org":"anveshak","classification":"OPEN"}'::jsonb,
            CONSTRAINT scam_templates_category_check CHECK (
                category IN ('fraud', 'info_op', 'narco', 'custom')
            ),
            CONSTRAINT scam_templates_severity_check CHECK (
                severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
            )
        )
    """)

    # ==================================================================
    # Tables with FK to root tables
    # ==================================================================

    # -- narrative_clusters (FK → topics)
    op.execute("""
        CREATE TABLE narrative_clusters (
            id                       TEXT        NOT NULL PRIMARY KEY,
            topic_id                 TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            label                    TEXT        NOT NULL,
            item_count               INTEGER     NOT NULL DEFAULT 0,
            independent_source_count INTEGER     NOT NULL DEFAULT 0,
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
    op.execute(
        "CREATE INDEX idx_clusters_archived ON narrative_clusters(archived_at) "
        "WHERE archived_at IS NOT NULL"
    )

    # -- content_items (FK → topics, sources, narrative_clusters, organizations)
    op.execute("""
        CREATE TABLE content_items (
            id                          TEXT        NOT NULL PRIMARY KEY,
            topic_id                    TEXT        REFERENCES topics(id) ON DELETE SET NULL,
            source_id                   TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            narrative_cluster_id        TEXT        REFERENCES narrative_clusters(id) ON DELETE SET NULL,
            org_id                      TEXT        NOT NULL REFERENCES organizations(id),
            raw_text                    TEXT        NOT NULL,
            clean_text                  TEXT        NOT NULL,
            language                    TEXT        NOT NULL DEFAULT 'en',
            translated_text             TEXT,
            translation_model           TEXT,
            content_hash                TEXT        NOT NULL,
            url                         TEXT,
            captured_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            credibility_score_at_capture FLOAT8     NOT NULL DEFAULT 50.0,
            embedding                   vector(384),
            content_quality             TEXT        NOT NULL DEFAULT 'good',
            clean_hash                  TEXT,
            title                       TEXT,
            topic_relevance_score       REAL,
            entity_minhash              BIGINT[],
            forwarded_from_channel_id   TEXT,
            forwarded_from_channel_name TEXT,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels                      JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE UNIQUE INDEX idx_content_items_hash ON content_items(content_hash)")
    op.execute("CREATE INDEX idx_content_items_topic ON content_items(topic_id)")
    op.execute("CREATE INDEX idx_content_items_source ON content_items(source_id)")
    op.execute("CREATE INDEX idx_content_items_captured ON content_items(captured_at DESC)")
    op.execute(
        "CREATE INDEX idx_content_items_topic_captured ON content_items(topic_id, captured_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_content_items_cluster ON content_items(narrative_cluster_id) "
        "WHERE narrative_cluster_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_content_items_embedding ON content_items "
        "USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"
    )
    op.execute(
        "CREATE INDEX idx_content_items_quality ON content_items(content_quality) "
        "WHERE content_quality = 'low_quality'"
    )
    op.execute("CREATE INDEX idx_content_items_clean_hash ON content_items(clean_hash)")
    op.execute(
        "CREATE INDEX idx_content_items_relevance "
        "ON content_items(topic_id, topic_relevance_score) WHERE embedding IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_content_items_translated ON content_items(language) "
        "WHERE translated_text IS NOT NULL"
    )
    op.execute("CREATE INDEX idx_content_items_org ON content_items(org_id)")

    # -- signals (FK → topics, narrative_clusters)
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
    op.execute(
        "CREATE INDEX idx_signals_undelivered ON signals(created_at) WHERE delivered_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_signals_cross_topic ON signals(signal_type) "
        "WHERE signal_type = 'cross_topic_convergence'"
    )

    # -- trackers (FK → topics, narrative_clusters)
    op.execute("""
        CREATE TABLE trackers (
            id                TEXT        NOT NULL PRIMARY KEY,
            case_number       TEXT        NOT NULL,
            org_id            TEXT        REFERENCES organizations(id),
            topic_id          TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            origin_cluster_id TEXT        REFERENCES narrative_clusters(id) ON DELETE SET NULL,
            title             TEXT        NOT NULL,
            external_case_ref TEXT,
            centroid          vector(384),
            centroid_threshold FLOAT8     NOT NULL DEFAULT 0.70,
            status            TEXT        NOT NULL DEFAULT 'watching',
            priority          TEXT        NOT NULL DEFAULT 'medium',
            assigned_to       TEXT,
            created_by        TEXT        NOT NULL,
            concluded_by      TEXT,
            concluded_at      TIMESTAMPTZ,
            closing_summary   TEXT,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels            JSONB       NOT NULL DEFAULT '{"domain":"osint","owner_org":"anveshak","classification":"OPEN"}'::jsonb,
            CONSTRAINT trackers_status_check CHECK (
                status IN ('watching', 'active', 'concluded')
            ),
            CONSTRAINT trackers_priority_check CHECK (
                priority IN ('low', 'medium', 'high', 'critical')
            )
        )
    """)
    op.execute("CREATE UNIQUE INDEX idx_trackers_case_number ON trackers(case_number)")
    op.execute("CREATE INDEX idx_trackers_topic ON trackers(topic_id)")
    op.execute("CREATE INDEX idx_trackers_status ON trackers(status)")
    op.execute("CREATE INDEX idx_trackers_org ON trackers(org_id)")
    op.execute("CREATE INDEX idx_trackers_assigned ON trackers(assigned_to)")
    op.execute("CREATE SEQUENCE tracker_case_seq START WITH 1 INCREMENT BY 1")

    # -- reports (FK → topics, trackers)
    op.execute("""
        CREATE TABLE reports (
            id                    TEXT        NOT NULL PRIMARY KEY,
            topic_id              TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            tracker_id            TEXT        REFERENCES trackers(id) ON DELETE SET NULL,
            report_type           TEXT        NOT NULL,
            time_window_start     TIMESTAMPTZ NOT NULL,
            time_window_end       TIMESTAMPTZ NOT NULL,
            credibility_min_filter FLOAT8     NOT NULL DEFAULT 30.0,
            content_md            TEXT,
            content_html          TEXT,
            pdf_path              TEXT,
            geojson               JSONB,
            confidence_score      FLOAT8,
            generated_at          TIMESTAMPTZ,
            generation_error      TEXT,
            source_snapshot       JSONB       NOT NULL DEFAULT '{}'::jsonb,
            content_item_count    INTEGER     NOT NULL DEFAULT 0,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels                JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_reports_topic ON reports(topic_id)")
    op.execute("CREATE INDEX idx_reports_type ON reports(report_type)")
    op.execute("CREATE INDEX idx_reports_window ON reports(time_window_end DESC)")
    op.execute(
        "CREATE INDEX idx_reports_generated ON reports(generated_at DESC) "
        "WHERE generated_at IS NOT NULL"
    )

    # -- media_assets (FK → content_items)
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

    # -- vision_results (FK → media_assets)
    op.execute("""
        CREATE TABLE vision_results (
            id                    TEXT NOT NULL PRIMARY KEY,
            media_asset_id        TEXT NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
            yolo_detections       JSONB,
            clip_labels           JSONB,
            deepfake_score        FLOAT8,
            deepfake_model        TEXT,
            synthetic_probability FLOAT8,
            processed_at          TIMESTAMPTZ,
            labels                JSONB NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE UNIQUE INDEX idx_vision_results_asset ON vision_results(media_asset_id)")
    op.execute(
        "CREATE INDEX idx_vision_results_deepfake ON vision_results(deepfake_score DESC) "
        "WHERE deepfake_score IS NOT NULL"
    )

    # -- extracted_entities (FK → content_items)
    op.execute("""
        CREATE TABLE extracted_entities (
            id              TEXT        NOT NULL PRIMARY KEY,
            content_item_id TEXT        NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            entity_type     TEXT        NOT NULL,
            entity_text     TEXT        NOT NULL,
            confidence      FLOAT8      NOT NULL DEFAULT 1.0,
            language        TEXT        NOT NULL DEFAULT 'en',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels          JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_entities_content_item ON extracted_entities(content_item_id)")
    op.execute(
        "CREATE INDEX idx_entities_type_text ON extracted_entities(entity_type, entity_text)"
    )
    op.execute(
        "CREATE INDEX idx_entities_text_trgm ON extracted_entities "
        "USING gin(entity_text gin_trgm_ops)"
    )
    op.execute("""
        CREATE INDEX idx_entities_identifier_types ON extracted_entities(entity_type, entity_text)
        WHERE entity_type IN (
            'PHONE_IN', 'PHONE_INTL', 'UPI', 'EMAIL',
            'CRYPTO_BTC', 'CRYPTO_ETH', 'CRYPTO_TRC20',
            'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE', 'URL_DOMAIN',
            'GSTIN', 'UDYAM', 'PAN', 'IFSC', 'BANK_ACCOUNT', 'SEBI_REG'
        )
    """)

    # -- credibility_audit_log (FK → sources, organizations)
    op.execute("""
        CREATE TABLE credibility_audit_log (
            id         TEXT        NOT NULL PRIMARY KEY,
            source_id  TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            org_id     TEXT        NOT NULL REFERENCES organizations(id),
            old_score  FLOAT8      NOT NULL,
            new_score  FLOAT8      NOT NULL,
            reason     TEXT        NOT NULL,
            changed_by TEXT        NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels     JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_credibility_audit_source ON credibility_audit_log(source_id)")
    op.execute(
        "CREATE INDEX idx_credibility_audit_created ON credibility_audit_log(created_at DESC)"
    )
    op.execute("CREATE INDEX idx_credibility_audit_org ON credibility_audit_log(org_id)")

    # -- report_source_warnings (FK → reports, sources)
    op.execute("""
        CREATE TABLE report_source_warnings (
            id           TEXT        NOT NULL PRIMARY KEY,
            report_id    TEXT        NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            source_id    TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            source_name  TEXT        NOT NULL,
            warning_type TEXT        NOT NULL DEFAULT 'credibility_downgraded',
            old_score    FLOAT8      NOT NULL,
            new_score    FLOAT8      NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels       JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_report_warnings_report ON report_source_warnings(report_id)")
    op.execute("CREATE INDEX idx_report_warnings_source ON report_source_warnings(source_id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_report_source_warnings_pair "
        "ON report_source_warnings(report_id, source_id)"
    )

    # -- near_duplicates (FK → content_items)
    op.execute("""
        CREATE TABLE near_duplicates (
            content_item_a_id TEXT        NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            content_item_b_id TEXT        NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            similarity_score  FLOAT8      NOT NULL,
            detected_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels            JSONB       NOT NULL DEFAULT '{"domain":"osint","owner_org":"anveshak","classification":"OPEN"}'::jsonb,
            PRIMARY KEY (content_item_a_id, content_item_b_id),
            CONSTRAINT near_duplicates_check CHECK (content_item_a_id < content_item_b_id)
        )
    """)
    op.execute("CREATE INDEX idx_near_dup_a ON near_duplicates(content_item_a_id)")
    op.execute("CREATE INDEX idx_near_dup_b ON near_duplicates(content_item_b_id)")

    # -- analysis_jobs (FK → topics)
    op.execute("""
        CREATE TABLE analysis_jobs (
            id         TEXT        NOT NULL PRIMARY KEY,
            job_type   TEXT        NOT NULL,
            topic_id   TEXT        REFERENCES topics(id) ON DELETE SET NULL,
            status     TEXT        NOT NULL DEFAULT 'queued',
            payload    JSONB       NOT NULL DEFAULT '{}'::jsonb,
            result     JSONB,
            error      TEXT,
            arq_job_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels     JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_jobs_status_type ON analysis_jobs(status, job_type)")
    op.execute("CREATE INDEX idx_jobs_topic ON analysis_jobs(topic_id)")
    op.execute(
        "CREATE INDEX idx_jobs_arq_id ON analysis_jobs(arq_job_id) WHERE arq_job_id IS NOT NULL"
    )

    # -- discovered_sources (FK → topics, sources)
    op.execute("""
        CREATE TABLE discovered_sources (
            id               TEXT        NOT NULL PRIMARY KEY,
            topic_id         TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            domain_or_handle TEXT        NOT NULL,
            platform         TEXT        DEFAULT 'web',
            discovery_method TEXT        NOT NULL,
            citation_count   INTEGER     DEFAULT 1,
            confidence_score REAL,
            evidence         JSONB       DEFAULT '{}'::jsonb,
            status           TEXT        DEFAULT 'pending',
            source_id        TEXT        REFERENCES sources(id),
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            updated_at       TIMESTAMPTZ DEFAULT NOW(),
            labels           JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_discovered_topic_status ON discovered_sources(topic_id, status)")
    op.execute(
        "CREATE UNIQUE INDEX idx_discovered_unique "
        "ON discovered_sources(topic_id, domain_or_handle, discovery_method)"
    )

    # -- identifier_clusters (FK → topics)
    op.execute("""
        CREATE TABLE identifier_clusters (
            id                 TEXT        NOT NULL PRIMARY KEY,
            topic_id           TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            identifier_type    TEXT        NOT NULL,
            identifier_value   TEXT        NOT NULL,
            source_count       INTEGER     NOT NULL DEFAULT 0,
            content_item_count INTEGER     NOT NULL DEFAULT 0,
            first_seen_at      TIMESTAMPTZ,
            last_seen_at       TIMESTAMPTZ,
            created_at         TIMESTAMPTZ DEFAULT NOW(),
            updated_at         TIMESTAMPTZ DEFAULT NOW(),
            labels             JSONB       NOT NULL DEFAULT '{"domain":"osint","owner_org":"anveshak","classification":"OPEN"}'::jsonb
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX idx_ic_topic_type_value "
        "ON identifier_clusters(topic_id, identifier_type, identifier_value)"
    )
    op.execute(
        "CREATE INDEX idx_ic_source_count ON identifier_clusters(topic_id, source_count DESC)"
    )

    # -- keyword_alert_rules (FK → topics)
    op.execute("""
        CREATE TABLE keyword_alert_rules (
            id               TEXT        NOT NULL PRIMARY KEY,
            topic_id         TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            keywords         TEXT[]      NOT NULL,
            match_mode       TEXT        NOT NULL DEFAULT 'any',
            is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
            notify_websocket BOOLEAN     NOT NULL DEFAULT TRUE,
            created_by       TEXT,
            org_id           TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels           JSONB       NOT NULL DEFAULT '{"domain":"alert","owner_org":"anveshak","classification":"OPEN"}'::jsonb,
            CONSTRAINT keyword_alert_rules_match_mode_check CHECK (
                match_mode IN ('any', 'all')
            )
        )
    """)
    op.execute(
        "CREATE INDEX idx_keyword_alerts_topic_active "
        "ON keyword_alert_rules(topic_id) WHERE is_active = TRUE"
    )

    # -- source_assessments (FK → topics, sources)
    op.execute("""
        CREATE TABLE source_assessments (
            id                 TEXT        NOT NULL PRIMARY KEY,
            topic_id           TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            source_id          TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            org_id             TEXT        NOT NULL,
            time_window_start  TIMESTAMPTZ NOT NULL,
            time_window_end    TIMESTAMPTZ NOT NULL,
            stats              JSONB       NOT NULL DEFAULT '{}'::jsonb,
            platform_metadata  JSONB,
            brief_md           TEXT,
            confidence_score   FLOAT8,
            source_snapshot    JSONB       NOT NULL DEFAULT '{}'::jsonb,
            content_item_count INTEGER     NOT NULL DEFAULT 0,
            generated_at       TIMESTAMPTZ,
            generation_error   TEXT,
            arq_job_id         TEXT,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels             JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX ix_assessment_dedup "
        "ON source_assessments(topic_id, source_id, time_window_start, time_window_end)"
    )
    op.execute(
        "CREATE INDEX ix_assessment_list "
        "ON source_assessments(topic_id, source_id, created_at DESC)"
    )
    op.execute("CREATE INDEX ix_assessment_org ON source_assessments(org_id)")

    # ==================================================================
    # Standalone tables (no FK to other app tables)
    # ==================================================================

    # -- token_blocklist
    op.execute("""
        CREATE TABLE token_blocklist (
            jti        TEXT        NOT NULL PRIMARY KEY,
            user_id    TEXT        NOT NULL,
            revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            labels     JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_token_blocklist_expires ON token_blocklist(expires_at)")

    # -- audit_trail
    op.execute("""
        CREATE TABLE audit_trail (
            id            TEXT        NOT NULL PRIMARY KEY,
            user_id       TEXT        NOT NULL,
            action        TEXT        NOT NULL,
            resource_type TEXT        NOT NULL,
            resource_id   TEXT        NOT NULL,
            details       JSONB       NOT NULL DEFAULT '{}'::jsonb,
            ip_address    TEXT        NOT NULL DEFAULT '',
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels        JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_audit_trail_user ON audit_trail(user_id, created_at DESC)")
    op.execute(
        "CREATE INDEX idx_audit_trail_resource "
        "ON audit_trail(resource_type, resource_id, created_at DESC)"
    )
    op.execute("CREATE INDEX idx_audit_trail_created ON audit_trail(created_at DESC)")

    # -- failed_jobs
    op.execute("""
        CREATE TABLE failed_jobs (
            id            TEXT        NOT NULL PRIMARY KEY,
            job_id        TEXT        NOT NULL UNIQUE,
            function_name TEXT        NOT NULL,
            args          TEXT        NOT NULL DEFAULT '',
            error         TEXT        NOT NULL DEFAULT '',
            queue_name    TEXT        NOT NULL DEFAULT '',
            failed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels        JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX idx_failed_jobs_queue ON failed_jobs(queue_name, failed_at DESC)")

    # -- content_archives (FK → topics)
    op.execute("""
        CREATE TABLE content_archives (
            id         TEXT        DEFAULT gen_random_uuid()::text NOT NULL PRIMARY KEY,
            topic_id   TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            month      TEXT        NOT NULL,
            file_path  TEXT        NOT NULL,
            item_count INTEGER     NOT NULL DEFAULT 0,
            file_size  BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels     JSONB       NOT NULL DEFAULT '{}'::jsonb,
            UNIQUE (topic_id, month)
        )
    """)
    op.execute("CREATE INDEX idx_content_archives_topic ON content_archives(topic_id)")

    # ==================================================================
    # Join tables
    # ==================================================================

    # -- topic_sources
    op.execute("""
        CREATE TABLE topic_sources (
            topic_id  TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            source_id TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            added_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (topic_id, source_id)
        )
    """)

    # -- topic_content_items
    op.execute("""
        CREATE TABLE topic_content_items (
            topic_id         TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            content_item_id  TEXT        NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            similarity_score FLOAT8      NOT NULL DEFAULT 0.0,
            assigned_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (topic_id, content_item_id)
        )
    """)
    op.execute("CREATE INDEX idx_topic_content_items_topic ON topic_content_items(topic_id)")
    op.execute("CREATE INDEX idx_topic_content_items_item ON topic_content_items(content_item_id)")

    # -- topic_templates
    op.execute("""
        CREATE TABLE topic_templates (
            topic_id    TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            template_id TEXT NOT NULL REFERENCES scam_templates(id) ON DELETE CASCADE,
            PRIMARY KEY (topic_id, template_id)
        )
    """)

    # -- org_sources
    op.execute("""
        CREATE TABLE org_sources (
            org_id    TEXT NOT NULL REFERENCES organizations(id),
            source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            PRIMARY KEY (org_id, source_id)
        )
    """)
    op.execute("CREATE INDEX idx_org_sources_org ON org_sources(org_id)")

    # -- catalog_approvals
    op.execute("""
        CREATE TABLE catalog_approvals (
            catalog_entry_id TEXT        NOT NULL REFERENCES source_catalog(id) ON DELETE CASCADE,
            topic_id         TEXT        NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            source_id        TEXT        NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            approved_by      TEXT        NOT NULL,
            approved_at      TIMESTAMPTZ DEFAULT NOW(),
            labels           JSONB       NOT NULL DEFAULT '{}'::jsonb,
            PRIMARY KEY (catalog_entry_id, topic_id)
        )
    """)

    # -- identifier_cluster_items
    op.execute("""
        CREATE TABLE identifier_cluster_items (
            identifier_cluster_id TEXT NOT NULL REFERENCES identifier_clusters(id) ON DELETE CASCADE,
            content_item_id       TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            source_id             TEXT NOT NULL,
            PRIMARY KEY (identifier_cluster_id, content_item_id)
        )
    """)

    # -- keyword_alert_triggers
    op.execute("""
        CREATE TABLE keyword_alert_triggers (
            id               TEXT        NOT NULL PRIMARY KEY,
            rule_id          TEXT        NOT NULL REFERENCES keyword_alert_rules(id) ON DELETE CASCADE,
            content_item_id  TEXT        NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            matched_keywords TEXT[]      NOT NULL,
            triggered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels           JSONB       NOT NULL DEFAULT '{"domain":"alert","owner_org":"anveshak","classification":"OPEN"}'::jsonb
        )
    """)
    op.execute(
        "CREATE INDEX idx_keyword_triggers_rule_time "
        "ON keyword_alert_triggers(rule_id, triggered_at DESC)"
    )

    # -- tracker child tables
    op.execute("""
        CREATE TABLE tracker_content_items (
            tracker_id       TEXT        NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            content_item_id  TEXT        NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            attached_by      TEXT        NOT NULL,
            status           TEXT        NOT NULL DEFAULT 'confirmed',
            similarity_score FLOAT8,
            confirmed_by     TEXT,
            confirmed_at     TIMESTAMPTZ,
            attached_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (tracker_id, content_item_id),
            CONSTRAINT tracker_content_items_attached_by_check CHECK (
                attached_by IN ('seed', 'auto', 'manual')
            ),
            CONSTRAINT tracker_content_items_status_check CHECK (
                status IN ('pending', 'confirmed')
            )
        )
    """)
    op.execute(
        "CREATE INDEX idx_tracker_content_tracker "
        "ON tracker_content_items(tracker_id, attached_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_tracker_content_status ON tracker_content_items(tracker_id, status)"
    )

    op.execute("""
        CREATE TABLE tracker_content_exclusions (
            tracker_id      TEXT        NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            content_item_id TEXT        NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            excluded_by     TEXT        NOT NULL,
            excluded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (tracker_id, content_item_id)
        )
    """)

    op.execute("""
        CREATE TABLE tracker_notes (
            id         TEXT        NOT NULL PRIMARY KEY,
            tracker_id TEXT        NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            user_id    TEXT        NOT NULL,
            body       TEXT        NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            labels     JSONB       NOT NULL DEFAULT '{"domain":"osint","owner_org":"anveshak","classification":"OPEN"}'::jsonb
        )
    """)
    op.execute(
        "CREATE INDEX idx_tracker_notes_tracker ON tracker_notes(tracker_id, created_at DESC)"
    )

    op.execute("""
        CREATE TABLE tracker_signals (
            tracker_id TEXT        NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            signal_id  TEXT        NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
            linked_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            linked_by  TEXT,
            PRIMARY KEY (tracker_id, signal_id)
        )
    """)

    op.execute("""
        CREATE TABLE tracker_audit_log (
            id         TEXT        NOT NULL PRIMARY KEY,
            tracker_id TEXT        NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            action     TEXT        NOT NULL,
            actor_id   TEXT        NOT NULL,
            detail     JSONB       NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX idx_tracker_audit_tracker ON tracker_audit_log(tracker_id, created_at DESC)"
    )

    # ==================================================================
    # Row-Level Security
    # ==================================================================

    # Create worker role (BYPASSRLS for background services)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anveshak_worker') THEN
                CREATE ROLE anveshak_worker WITH LOGIN BYPASSRLS;
            END IF;
        END
        $$
    """)

    # Enable RLS on org-scoped tables
    op.execute("ALTER TABLE content_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE topics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE credibility_audit_log ENABLE ROW LEVEL SECURITY")

    # RLS policies — pass-through when app.current_org is empty
    op.execute("""
        CREATE POLICY org_isolation_content_items ON content_items
        USING (
            current_setting('app.current_org', true) = ''
            OR org_id = current_setting('app.current_org', true)
        )
    """)
    op.execute("""
        CREATE POLICY org_isolation_topics ON topics
        USING (
            current_setting('app.current_org', true) = ''
            OR org_id = current_setting('app.current_org', true)
        )
    """)
    op.execute("""
        CREATE POLICY org_isolation_users ON users
        USING (
            current_setting('app.current_org', true) = ''
            OR org_id = current_setting('app.current_org', true)
            OR org_id IS NULL
        )
    """)
    op.execute("""
        CREATE POLICY org_isolation_credibility_audit ON credibility_audit_log
        USING (
            current_setting('app.current_org', true) = ''
            OR org_id = current_setting('app.current_org', true)
        )
    """)

    # Grant worker access to all tables and sequences
    op.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO anveshak_worker")
    op.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anveshak_worker")

    # ==================================================================
    # Seed data: built-in scam templates
    # ==================================================================
    # These 11 templates are the built-in library Engine C matches content
    # against. They were seeded by migration 009 and amended by 013, both now
    # archived, so the squashed baseline created scam_templates empty. A fresh
    # deployment then matched nothing at all, with no error: the template
    # signal query inner-joins scam_templates, so an empty table silently
    # yields zero signals. Kept verbatim from 009 + 013 so the final state
    # matches an already-migrated database exactly.
    op.execute("""
        INSERT INTO scam_templates
            (id, org_id, name, display, category, keywords, min_keyword_hits,
             expected_identifiers, severity, legal_sections, is_builtin, is_active, labels)
        VALUES
            ('tpl-investment-fraud', NULL, 'investment_fraud',
             'Investment Fraud', 'fraud',
             ARRAY['guaranteed returns', 'double your money', 'investment opportunity',
                   'high returns', 'risk free', 'fixed income', 'monthly returns',
                   'trading platform', 'forex', 'binary options'],
             3, ARRAY['UPI', 'CRYPTO_BTC', 'CRYPTO_ETH', 'PHONE_IN', 'BANK_ACCOUNT'],
             'CRITICAL',
             ARRAY['IPC 420', 'SEBI (PFUTP) Regulations', 'PMLA Section 3'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-mule-recruitment', NULL, 'mule_recruitment',
             'Mule Account Recruitment', 'fraud',
             ARRAY['bank account', 'commission', 'per transaction', 'easy money',
                   'rent your account', 'lend account', 'account for sale',
                   'daily income', 'no risk', 'passive income'],
             3, ARRAY['PHONE_IN', 'UPI', 'TELEGRAM_HANDLE', 'BANK_ACCOUNT'],
             'CRITICAL',
             ARRAY['PMLA Section 3', 'PMLA Section 4', 'IPC 420', 'IT Act 66D'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-maas', NULL, 'maas',
             'Mule-as-a-Service', 'fraud',
             ARRAY['mule service', 'account provider', 'clean account', 'fresh account',
                   'bulk accounts', 'verified account', 'KYC done', 'ready to use',
                   'account supply', 'wholesale accounts'],
             3, ARRAY['PHONE_IN', 'UPI', 'TELEGRAM_HANDLE', 'BANK_ACCOUNT'],
             'CRITICAL',
             ARRAY['PMLA Section 3', 'PMLA Section 4', 'IT Act 66D'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-digital-arrest', NULL, 'digital_arrest',
             'Digital Arrest Scam', 'fraud',
             ARRAY['police', 'arrest warrant', 'CBI', 'narcotics', 'money laundering',
                   'Aadhaar linked', 'court order', 'video call verification',
                   'stay on the line', 'do not tell anyone'],
             3, ARRAY['PHONE_IN', 'UPI', 'BANK_ACCOUNT'],
             'HIGH',
             ARRAY['IPC 419', 'IPC 420', 'IT Act 66C', 'IT Act 66D'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-job-fraud', NULL, 'job_fraud',
             'Job Fraud', 'fraud',
             ARRAY['work from home', 'data entry job', 'part time job', 'registration fee',
                   'guaranteed placement', 'earn daily', 'typing job',
                   'no experience needed', 'immediate joining', 'refundable deposit'],
             3, ARRAY['PHONE_IN', 'UPI', 'EMAIL', 'TELEGRAM_HANDLE'],
             'HIGH',
             ARRAY['IPC 420', 'IT Act 66D'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-pump-and-dump', NULL, 'pump_and_dump',
             'Pump and Dump', 'fraud',
             ARRAY['multibagger', 'target price', 'buy now', 'insider tip',
                   'guaranteed profit', 'small cap gem', 'operator stock',
                   'breaking out', 'SEBI registered', 'free tips'],
             3, ARRAY['PHONE_IN', 'TELEGRAM_HANDLE', 'SEBI_REG'],
             'CRITICAL',
             ARRAY['SEBI (PFUTP) Regulations 2003', 'SEBI Act Section 12A',
                   'IPC 420', 'Companies Act Section 447'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-fake-research-report', NULL, 'fake_research_report',
             'Fake Research Report', 'fraud',
             ARRAY['research report', 'analyst recommendation', 'strong buy',
                   'price target', 'institutional pick', 'confidential report',
                   'leaked report', 'brokerage recommendation', 'fundamental analysis'],
             3, ARRAY['TELEGRAM_HANDLE', 'EMAIL', 'PHONE_IN'],
             'HIGH',
             ARRAY['SEBI (Research Analysts) Regulations 2014',
                   'SEBI (PFUTP) Regulations 2003', 'IPC 468'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-drug-sale', NULL, 'drug_sale',
             'Drug Sale', 'narco',
             ARRAY['stuff', 'maal', 'product available', 'best quality',
                   'delivery available', 'discreet shipping', 'bulk order',
                   'sample available', 'wickr', 'drop location'],
             3, ARRAY['PHONE_IN', 'TELEGRAM_HANDLE', 'CRYPTO_BTC', 'CRYPTO_TRC20'],
             'HIGH',
             ARRAY['NDPS Act Section 20', 'NDPS Act Section 22',
                   'NDPS Act Section 25', 'NDPS Act Section 29'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-drug-delivery-recruitment', NULL, 'drug_delivery_recruitment',
             'Drug Delivery Recruitment', 'narco',
             ARRAY['delivery boy', 'courier needed', 'parcel delivery', 'good pay',
                   'no questions asked', 'cash on delivery', 'pickup and drop',
                   'night shift', 'own vehicle', 'local delivery'],
             3, ARRAY['PHONE_IN', 'TELEGRAM_HANDLE'],
             'HIGH',
             ARRAY['NDPS Act Section 25', 'NDPS Act Section 27A',
                   'NDPS Act Section 29'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-fake-sim-sale', NULL, 'fake_sim_sale',
             'Fake SIM Card Sale', 'fraud',
             ARRAY['SIM card', 'pre-activated', 'no KYC', 'anonymous SIM',
                   'bulk SIM', 'ready to use SIM', 'Jio SIM', 'Airtel SIM',
                   'document not required', 'instant activation'],
             3, ARRAY['PHONE_IN', 'TELEGRAM_HANDLE', 'UPI'],
             'MEDIUM',
             ARRAY['Indian Telegraph Act Section 20', 'IT Act 66C',
                   'IPC 420', 'IPC 468'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb),

            ('tpl-crypto-cashout', NULL, 'crypto_cashout',
             'Crypto Cashout Service', 'fraud',
             ARRAY['crypto to cash', 'USDT to INR', 'BTC to bank', 'cash out',
                   'no KYC exchange', 'P2P transfer', 'instant withdrawal',
                   'best rate', 'OTC deal', 'hawala crypto'],
             3, ARRAY['CRYPTO_BTC', 'CRYPTO_ETH', 'CRYPTO_TRC20', 'UPI',
                      'BANK_ACCOUNT', 'PHONE_IN'],
             'HIGH',
             ARRAY['PMLA Section 3', 'FEMA Section 3', 'IT Act 66D'],
             TRUE, TRUE,
             '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)

        ON CONFLICT (id) DO NOTHING
    """)

    # From archived migration 013: international phone numbers became a
    # relevant identifier for these four templates.
    op.execute("""
        UPDATE scam_templates
        SET expected_identifiers = array_append(expected_identifiers, 'PHONE_INTL')
        WHERE name IN ('mule_recruitment', 'maas', 'drug_sale', 'crypto_cashout')
          AND NOT ('PHONE_INTL' = ANY(expected_identifiers))
    """)


def downgrade() -> None:
    # Drop all tables in reverse dependency order
    join_tables = [
        "tracker_audit_log",
        "tracker_signals",
        "tracker_notes",
        "tracker_content_exclusions",
        "tracker_content_items",
        "keyword_alert_triggers",
        "identifier_cluster_items",
        "catalog_approvals",
        "org_sources",
        "topic_templates",
        "topic_content_items",
        "topic_sources",
    ]
    child_tables = [
        "source_assessments",
        "content_archives",
        "failed_jobs",
        "audit_trail",
        "token_blocklist",
        "near_duplicates",
        "report_source_warnings",
        "discovered_sources",
        "keyword_alert_rules",
        "identifier_clusters",
        "extracted_entities",
        "vision_results",
        "media_assets",
        "analysis_jobs",
        "credibility_audit_log",
    ]
    core_tables = [
        "reports",
        "trackers",
        "signals",
        "content_items",
        "narrative_clusters",
        "scam_templates",
        "source_catalog",
        "sources",
        "topics",
        "users",
        "organizations",
    ]

    # Drop RLS policies first
    op.execute("DROP POLICY IF EXISTS org_isolation_content_items ON content_items")
    op.execute("DROP POLICY IF EXISTS org_isolation_topics ON topics")
    op.execute("DROP POLICY IF EXISTS org_isolation_users ON users")
    op.execute("DROP POLICY IF EXISTS org_isolation_credibility_audit ON credibility_audit_log")

    for table in join_tables + child_tables + core_tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    op.execute("DROP SEQUENCE IF EXISTS tracker_case_seq")
    op.execute("DROP ROLE IF EXISTS anveshak_worker")
