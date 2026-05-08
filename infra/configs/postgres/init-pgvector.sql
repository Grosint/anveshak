-- Anveshak — PostgreSQL initialisation script
-- Executed once by the postgres container on first start.
-- Creates required extensions. Application migrations (Alembic) handle
-- all table DDL — this script only bootstraps extension-level features.

-- pgvector: dense vector storage for embedding similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- uuid-ossp: UUID generation functions (uuid_generate_v4())
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pg_trgm: trigram similarity for fuzzy text search (names, aliases)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- btree_gin: composite GIN indexes on btree types (used by label jsonb indexes)
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Confirm core extensions are active (postgis omitted — not in pgvector/pgvector:pg16 image)
DO $$
BEGIN
  ASSERT (SELECT COUNT(*) FROM pg_extension WHERE extname IN (
    'vector', 'uuid-ossp', 'pg_trgm', 'btree_gin'
  )) = 4,
  'One or more required extensions failed to install';
END $$;

-- ---------------------------------------------------------------------------
-- Test database — used by integration tests (make test-integration).
-- Same extensions, separate namespace. Tests NEVER touch the production DB.
-- ---------------------------------------------------------------------------
CREATE DATABASE anveshak_test OWNER anveshak;

\connect anveshak_test

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

DO $$
BEGIN
  ASSERT (SELECT COUNT(*) FROM pg_extension WHERE extname IN (
    'vector', 'uuid-ossp', 'pg_trgm', 'btree_gin'
  )) = 4,
  'One or more required extensions failed to install in anveshak_test';
END $$;

\connect anveshak
