Review code changes for quality, correctness, and architectural compliance.

Check for:
FAIL (must fix):
- LLM call made synchronously in FastAPI request handler (must be ARQ async job)
- ContentItem written without content_hash
- Report generated_at field updated after creation
- Credibility score changed without credibility_audit_log entry
- Hardcoded model names, device strings, or ML parameters (must come from settings)
- Missing labels field on any Pydantic model
- Deepfake result presented as binary bool (must be float probability)

WARN (should fix):
- Missing type annotations
- Bare except clause
- TODO/FIXME in production code
- Missing OpenTelemetry span in pipeline stage function
- No max_tokens set on LLM call

Report each finding with file:line and severity.
