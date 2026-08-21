# LLM Validated Output with Progressive Retry

## When to load: any ARQ job that calls Ollama and must validate output before storage

---

## The Problem

`mistral:7b` (and smaller models) frequently:
- Wraps JSON in markdown code fences (` ```json ... ``` `)
- Adds preamble ("Here is the requested JSON:") before the object
- Returns truncated JSON when the context is large
- Omits required fields on first attempt

Storing raw LLM output violates CLAUDE.md rule 9. Retrying with the same
prompt after a parse failure wastes tokens and usually fails the same way.

---

## The Pattern

### 1. Strict output schema as a Pydantic model

```python
class ReportContent(BaseModel):
    """LLM output validation schema — CLAUDE.md rule 9."""
    model_config = ConfigDict(strict=True)

    executive_summary: str
    key_findings: list[str]
    recommendations: list[str]
    confidence_level: float        # 0.0–1.0
    source_citations: list[str]
    labels: Labels                 # MANDATORY — CLAUDE.md rule 2
```

**Always include `labels: Labels`** on LLM output schemas unless the model is
a transient parse-only DTO (add the exemption comment if so).

### 2. JSON fence stripper

LLMs almost always wrap JSON in code fences. Strip before `json.loads()`:

```python
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```", re.IGNORECASE)

def _extract_json_from_text(text: str) -> str:
    match = _JSON_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    # Fallback: find outermost { ... }
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return text.strip()
```

### 3. Parse function with explicit error types

```python
def parse_llm_response(raw: str) -> ReportContent:
    cleaned = _extract_json_from_text(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc
    return ReportContent(**data)  # raises ValidationError if schema mismatch
```

### 4. Progressive retry — tighten prompt on each failure

```python
async def call_ollama_with_retry(
    prompt: str, settings, max_retries: int
) -> ReportContent | None:
    retry_prompt = prompt
    for attempt in range(1, max_retries + 1):
        try:
            raw = await call_ollama(
                prompt=retry_prompt,
                model=settings.ollama_report_model,
                host=settings.ollama_host,
                timeout=settings.ollama_report_timeout_s,
            )
            return parse_llm_response(raw)
        except Exception as exc:
            log.warning("llm_attempt_failed", attempt=attempt, error=str(exc))
            # Tighten on retry — models respond better to explicit JSON-only demand
            retry_prompt = (
                prompt
                + "\n\nIMPORTANT: Respond with ONLY the JSON object. "
                  "No preamble, no markdown, no explanation."
            )
    log.error("llm_all_retries_failed", max_retries=max_retries)
    return None
```

### 5. Caller treats None as a hard failure — never stores partial output

```python
result = await call_ollama_with_retry(prompt, s, max_retries=s.ollama_retry_max)
if result is None:
    await db.update_job_status(pool, job_id, "failed", "LLM returned no valid output")
    return   # EXIT — do NOT store anything
```

---

## Settings (hardware-controlled)

```python
ollama_report_model: str = "mistral:7b"      # upgrade to llama3.1:70b on GPU
ollama_report_timeout_s: int = 300           # 5min for CPU; can be 30s on GPU
ollama_retry_max: int = 2
```

---

## JSON schema instruction (embed in every prompt)

Always specify the exact schema in the prompt so the model knows the target:

```
You MUST respond with ONLY a JSON object matching this exact schema (no other text):
{
  "executive_summary": "<string: 2-4 sentences>",
  "key_findings": ["<string>", ...],
  "recommendations": ["<string>", ...],
  "confidence_level": <float 0.0-1.0>,
  "source_citations": ["<url>", ...]
}
```

---

## Implementation reference
`services/reporter/src/anveshak/reporter/llm.py`
