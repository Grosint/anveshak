# LLM Patterns

## When to load: any task involving Ollama, report generation, or LLM inference

> See also: `learned/phase-check-pitfalls.md` — transient LLM-output Pydantic models and the labels rule
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
