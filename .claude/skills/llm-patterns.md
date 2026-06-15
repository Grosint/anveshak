# LLM Patterns

## When to load: any task involving Ollama, report generation, or LLM inference

> See also: `learned/phase-check-pitfalls.md` — transient LLM-output Pydantic models and the labels rule
> See also: `learned/sql-param-count-caller-mismatch.md` — adding $N to SQL constant requires updating ALL callers; grep for the constant name
> See also: `learned/role-constraint-migration-order.md` — update CHECK constraint BEFORE inserting rows with new role values
> See also: `learned/dual-layer-rls-safety-net.md` — application filtering + PostgreSQL RLS for defence/LEA deployments
> See also: `learned/optional-dep-lazy-import-two-level-log.md` — WeasyPrint/PyMuPDF lazy import with two-level logging
> See also: `learned/path-parents-index-off-by-one.md` — Path.parents[] off-by-one bug (geocoder custom_locations.json)
> See also: `learned/leiden-threshold-per-model.md` — clustering threshold must be calibrated per embedding model; 0.70 for MiniLM, re-calibrate on model change
> See also: `learned/benchmark-100-percent-completion.md` — benchmark must wait for 100% embedding completion; 90% causes non-deterministic recall
> See also: `learned/new-db-func-mock-all-callers.md` — adding new db functions requires updating all test mocks that patch the db module
> See also: `learned/analysis-jobs-db-source-of-truth.md` — analysis_jobs table is authoritative; don't rely on ARQ Redis for completed jobs
> See also: `learned/passlib-bcrypt-incompatibility.md` — replace passlib with direct bcrypt wrapper (passlib 1.7 + bcrypt>=4 broken)
> See also: `learned/asyncpg-repository-pattern.md` — SQL constants + typed db/ functions; why not ORM
> See also: `learned/llm-validated-output-retry.md` — JSON fence stripping, ReportContent schema, progressive retry pattern
> See also: `learned/idempotent-cron-insert.md` — UNIQUE index + ON CONFLICT DO NOTHING for cron jobs that write event/warning rows repeatedly
> See also: `learned/bidirectional-auto-scoring.md` — separate min-threshold settings for score boosts vs drops; mandatory invariant test
> See also: `learned/jsonb-labels-api-surfacing.md` — threading labels through CTE UNION ALL + DISTINCT ON dedup; post-processing to extract sentiment/keywords
> See also: `learned/git-stash-pop-silent-data-loss.md` — stash pop failure silently reverts files; never stash to test hypotheses, use worktrees instead
> See also: `learned/post-embedding-relevance-gate.md` — cosine similarity gate between content and topic query embeddings; threshold calibration from histogram
> See also: `learned/mock-sequential-db-calls.md` — use side_effect for functions making multiple sequential DB fetches; expand fake_row when SQL JOINs change
> See also: `learned/scheduler-worker-split.md` — split monolithic service into lightweight scheduler (124 MiB) + ARQ ML worker (6 GiB); import safety rules
> See also: `learned/orphan-sweep-safety-net.md` — periodic sweep for content_items missed by scraper enqueue; runs in scheduler every 5 min
> See also: `learned/quality-gate-all-consumers.md` — relevance score must filter at display AND clustering; NULL-safe SQL pattern
> See also: `learned/per-topic-relevance-auto-calibration.md` — auto-calibrate relevance threshold per topic; global threshold fails for mixed-breadth topics
> See also: `learned/psql-null-empty-string-pitfall.md` — psql returns '' for NULL, not Python None; use truthiness check in scripts
> See also: `learned/incremental-clustering-centroid-assign.md` — O(new×clusters) instead of O(N²); preserves cluster_id stability
> See also: `learned/entity-minhash-clustering-boost.md` — blend entity Jaccard into HDBSCAN distance; BIGINT[] not INTEGER[]; NULL-safe mask
> See also: `learned/hdbscan-cosine-precomputed.md` — HDBSCAN 0.8.x needs precomputed float64 matrix; metric="cosine" not supported
> See also: `learned/benchmark-arq-dedup-flush.md` — flush arq:job:* Redis keys before benchmark re-runs; production uses unique UUIDs
> See also: `learned/quality-gate-unicode-ranges.md` — word regex must cover Devanagari \u0900-\u097f; silent failure drops Hindi content
> See also: `learned/deepfake-none-error-signal.md` — return None on detection failure instead of default 0.0 score
> See also: `learned/spacy-pip-models-bake-in-image.md` — spaCy models are pip packages; bake into image, not volume
> See also: `learned/credibility-settings-separation.md` — separate penalty magnitude from noise filter threshold
> See also: `learned/detect-language-must-not-gatekeep.md` — detect_language returns real lang; don't filter on downstream model availability
> See also: `learned/golden-test-data-ml-pipeline.md` — pre-written multilingual content with expected outputs; fuzzy keyword matching
> See also: `learned/scope-param-passthrough-invariant.md` — if route accepts topic_id, every code path must pass it through to SQL; silent drop = cross-topic data leak
> See also: `learned/arq-queue-name-all-callers.md` — enqueue_job _queue_name must match target WorkerSettings.queue_name at every call site

---

### All LLM calls are async ARQ jobs — never synchronous in routes

```python
# WRONG — blocks request thread
@router.post("/reports")
async def generate_report(topic_id: str):
    result = await ollama.generate(...)  # NEVER
    return result

# CORRECT — enqueue and return job_id
@router.post("/reports")
async def generate_report(topic_id: str, redis=Depends(get_redis)):
    job_id = await enqueue_job("generate_report", topic_id, redis)
    return {"job_id": job_id, "status": "queued"}
```

### Ollama client (async)
```python
import httpx

async def call_ollama(prompt: str, model: str, max_tokens: int = 2048) -> str:
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{settings.OLLAMA_HOST}/api/generate",
            json={
                "model": model,          # from settings — never hardcoded
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens},
            }
        )
        return resp.json()["response"]
```

### Structured output (mandatory for report generation)
```python
from pydantic import BaseModel

class ReportOutput(BaseModel):
    executive_summary: str
    key_entities: list[str]
    confidence_score: float  # 0.0–1.0
    source_citations: list[dict]  # [{content_item_id, claim}]

async def generate_structured_report(context: str) -> ReportOutput:
    prompt = build_report_prompt(context)  # Jinja2 template
    raw = await call_ollama(prompt, settings.OLLAMA_REPORT_MODEL)
    return ReportOutput.model_validate_json(raw)
```

### Anti-hallucination prompt pattern
```python
REPORT_SYSTEM_PROMPT = """
You are an intelligence analyst.
Rules:
1. Only use facts present in the provided context below.
2. If a fact is not in the context, write "Not confirmed in available sources."
3. Every factual claim must be followed by [Source: {source_name}].
4. Never infer, speculate, or extrapolate beyond the provided context.
5. Confidence score: fraction of claims supported by 2+ independent sources.
"""
```

### LiteLLM for model abstraction
```python
# Use LiteLLM to swap models without code changes
from litellm import acompletion

response = await acompletion(
    model=f"ollama/{settings.OLLAMA_REPORT_MODEL}",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=settings.LLM_MAX_TOKENS,
    api_base=settings.OLLAMA_HOST,
)
```
