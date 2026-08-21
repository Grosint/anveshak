---
name: performance-hardware
description: "Model selection and hardware independence. Covers which model tier suits agents versus orchestration versus architecture, reading all performance-sensitive config from env vars rather than hardcoding device strings or batch sizes, and routing LLM inference through ARQ with set timeouts. Use when choosing a model, tuning performance, or making hardware-sensitive config decisions."
---

# Performance

## Model Selection Strategy

**Haiku 4.5** — lightweight agents, frequent invocation, workers
**Sonnet 4.6** — main dev, orchestration, complex coding
**Opus 4.6** — architecture decisions, max reasoning

## Hardware Independence

ALL perf-sensitive config from env vars.
See hardware.md for upgrade matrix.

Never hardcode: model names, device strings ("cpu"/"cuda"), batch sizes, keep-alive durations, index types, embedding dimensions.

## LLM Jobs

All LLM inference async via ARQ.
FastAPI routes enqueue jobs — never call Ollama directly.
Timeout: 300s report gen, 30s cluster labelling.