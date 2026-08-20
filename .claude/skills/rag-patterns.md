# RAG Patterns

## When to load: any task involving report generation, content retrieval, or pgvector

> See also: `.claude/skills/learned/sovereign-geocoder.md` — offline geonamescache geocoding (no network)
> See also: `.claude/skills/learned/immutable-write-idempotency.md` — WHERE generated_at IS NULL guard for one-time writes

---

### pgvector setup
```python
# In migration — create extension and index
await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
await conn.execute("""
    CREATE TABLE IF NOT EXISTS content_items (
        ...
        embedding vector(384)  -- all-MiniLM-L6-v2 dimensions
    )
""")
# IVFFlat for prototype (upgrade to HNSW when 32GB RAM available — see hardware.md)
await conn.execute("""
    CREATE INDEX IF NOT EXISTS content_items_embedding_idx
    ON content_items USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100)
""")
```

### Embedding model (hardware-independent)
```python
from sentence_transformers import SentenceTransformer

def load_embedder(model_name: str) -> SentenceTransformer:
    # model_name from settings.EMBEDDING_MODEL — never hardcoded
    return SentenceTransformer(model_name)

def embed_text(model: SentenceTransformer, text: str) -> list[float]:
    return model.encode(text, normalize_embeddings=True).tolist()
```

### Retrieval for RAG
```python
# Use <-> operator (cosine distance via asyncpg — NOT <=> which is for psycopg2)
# credibility filter uses credibility_score_at_capture (snapshot), not live score
SQL_FETCH_RAG_CHUNKS = """
    SELECT id, clean_text, credibility_score_at_capture, url, source_id
    FROM content_items
    WHERE topic_id = $1
      AND embedding IS NOT NULL
      AND credibility_score_at_capture >= $2
    ORDER BY embedding <-> $3
    LIMIT $4
"""

async def retrieve_context(
    conn, topic_id: str, query_embedding: list[float],
    credibility_min: float, top_k: int
) -> list[dict]:
    rows = await conn.fetch(
        SQL_FETCH_RAG_CHUNKS, topic_id, credibility_min, query_embedding, top_k
    )
    return [dict(r) for r in rows]
```

### Historical backfill (new topic → search existing corpus)
```python
async def backfill_topic(
    conn, topic_id: str, keywords: list[str], embedder: SentenceTransformer
) -> int:
    query_text = " ".join(keywords)
    embedding = embed_text(embedder, query_text)

    # Find existing content matching topic keywords
    rows = await conn.fetch("""
        SELECT id FROM content_items
        WHERE topic_id IS NULL
          AND embedding <=> $1::vector < 0.3  -- cosine distance threshold
        LIMIT 100
    """, embedding)

    # Associate with topic
    await conn.executemany(
        "UPDATE content_items SET topic_id=$1 WHERE id=$2",
        [(topic_id, r["id"]) for r in rows]
    )
    return len(rows)
```

### Context assembly for report prompt
```python
# Token estimate: len(text) // 4  (1 token ≈ 4 chars — faster than split())
# Chunks are pre-sorted by similarity from the DB query — include in order
def assemble_context(chunks: list[dict], max_tokens: int) -> str:
    if not chunks or max_tokens <= 0:
        return ""
    parts: list[str] = []
    token_count = 0
    for chunk in chunks:
        formatted = f"[Source: {chunk.get('url', 'unknown')}]\n{chunk.get('clean_text', '')}\n\n"
        chunk_tokens = len(formatted) // 4
        if token_count + chunk_tokens > max_tokens:
            break
        parts.append(formatted)
        token_count += chunk_tokens
    return "".join(parts)
```

### Embedding model — lazy-loaded module-level cache

```python
_MODEL_CACHE: dict[str, SentenceTransformer] = {}

def get_embedding_model(model_name: str) -> SentenceTransformer:
    """Cached model — loaded once per process, never per-request."""
    if model_name not in _MODEL_CACHE:
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]

def generate_query_embedding(topic_name: str, keywords: list[str], model_name: str) -> list[float]:
    query_text = " ".join([topic_name] + keywords)
    return [float(v) for v in get_embedding_model(model_name).encode(query_text)]
```

Pre-warm in FastAPI lifespan to avoid cold-start on first report request:
```python
@asynccontextmanager
async def lifespan(app):
    get_embedding_model(settings.embedding_model)  # warm up
    yield
```
