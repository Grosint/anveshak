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
