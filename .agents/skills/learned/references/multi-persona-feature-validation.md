# Multi-Persona Feature Validation

## Pattern
Before designing a user-facing feature, validate through 8 parallel domain-expert agents.
Each reviews from their operational perspective. Synthesize consensus + divergence.

## When to use
Any new feature that touches analyst workflow, schema, or API contracts.
Backend changes are MORE important to validate (evidence chain, court admissibility).

## How it works
1. Describe the feature in 3-5 sentences
2. Launch 8 agents in parallel (Solution Architect, PM, LEA Cyber, NIA, MEA, SEBI, ED, NCB)
3. Each returns findings independently (~2 min each)
4. Synthesize: what all agree on, where they diverge, what's v1 vs v2

## Why it matters
- Caught naming issue: "Investigation" has legal meaning in Indian LEA context → renamed to "Tracker"
- Caught auto-insert risk: all 8 independently said "never auto-insert, use review queue"
- Caught missing features per agency: geographic tagging (MEA), scrip extraction (SEBI), CIN/DIN (ED)
- PM caught adoption risk: "Concluded" not "Closed" (cultural fit in LEA)
- NIA caught showstopper: classification levels needed for classified annotations

## Implementation
Persona agents saved in `.claude/agents/persona-*.md`. Referenced by `/plan` Phase 0.

## Cost
~8 agent calls × 20K tokens each = ~160K tokens. Takes ~3 min wall clock (parallel).
Worth it for any feature that takes >1 day to build — prevents rework.
