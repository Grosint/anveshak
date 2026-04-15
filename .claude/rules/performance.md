---
# Performance

## Model Selection Strategy

**Haiku 4.5** — lightweight agents, frequent invocation, worker agents
**Sonnet 4.6** — main development, orchestration, complex coding
**Opus 4.6** — architectural decisions, maximum reasoning

## Hardware Independence

ALL performance-sensitive configuration comes from environment variables.
See hardware.md for the full upgrade matrix.

Never hardcode: model names, device strings ("cpu"/"cuda"), batch sizes,
keep-alive durations, index types, embedding dimensions.

## LLM Jobs

All LLM inference is async via ARQ.
FastAPI routes enqueue jobs — never call Ollama directly.
Timeout: 300s for report generation, 30s for cluster labelling.
