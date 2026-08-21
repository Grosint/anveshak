# Stats-First, LLM-Second Feature Design

## Pattern
When building an intelligence feature that combines data aggregation with LLM narrative:
1. Phase 0: deterministic SQL stats returned synchronously (sub-second)
2. Phase 1: optional metadata enrichment via async ARQ job (fail-open)
3. Phase 2: LLM brief as separate on-demand action with its own endpoint

## Why
8/8 persona reviews agreed: deterministic stats cover 70% of value with 0% hallucination risk.
LLM adds narrative but introduces latency (30-90s on CPU), hallucination risk, and
requires per-claim citation validation. Shipping stats first gives immediate demo value
while LLM brief is still being built.

## How to Apply
- Stats endpoint returns 200 synchronously — never enqueue an ARQ job for pure SQL
- LLM brief is a SEPARATE endpoint (POST .../brief) returning 202 + polling
- Frontend shows stats immediately, "Generate Brief" button below for LLM
- `generated_at` stays NULL until LLM brief is stored (immutability contract)
- Use `generation_status: "stats_only" | "queued" | "complete" | "failed"` for frontend state

## Anti-Pattern
Do NOT bundle stats + LLM into a single async job. The analyst waits 60s for data
that could have been returned in 200ms.

## Session Context
Source Assessment feature for Nagaland Police demo (2026-06-22).
