Restate requirements, assess risks, and create step-by-step implementation plan.

## Phase 0: Multi-Persona Review (MANDATORY for features, SKIP for bugfixes)

Before designing implementation, validate the feature through 8 stakeholder lenses.
Launch parallel agents — each reviews the proposal from their perspective.

### Personas (reusable agents in `.claude/agents/`):

Launch as parallel Agent tool calls. Each agent file has the full prompt.
Prepend the feature description to each agent's system prompt.

1. **persona-solution-architect** — Schema, performance, edge cases, migration, multi-tenancy
2. **persona-product-manager** — User value, naming, adoption, demo-ability, competitive positioning
3. **persona-lea-cyber** — Daily workflow, FIR integration, evidence, search-first UX, Hindi
4. **persona-nia** — Evidence integrity, classification, cross-topic, court readiness
5. **persona-mea** — Geographic dimension, narrative lifecycle, multi-language, provenance
6. **persona-sebi** — Speed, coordination detection, trading data, volume, Chinese wall
7. **persona-ed** — Money trail + OSINT, shell companies, PMLA evidence, attachment orders
8. **persona-ncb** — Identity persistence, drug detection, NDPS court, OPSEC

### How to launch:
For each persona, use the Agent tool with this prompt structure:
```
[Read .claude/agents/persona-{name}.md for the full system prompt]

## Feature Being Proposed:
[DESCRIBE THE FEATURE IN 3-5 SENTENCES]

## Your Task:
Read the proposal 20 times. Provide your review from your perspective.
Be brutally honest. No praise.
```

Launch all 8 (or selected subset) as parallel background agents.

### When to run all 8 vs fewer:
- **New user-facing feature** (trackers, reports, dashboards) → all 8
- **Backend-only change** (schema, API, worker) → all 8 (backend is MORE critical — schema affects evidence chain, court admissibility, multi-tenancy, audit trail; every persona has backend opinions)
- **Frontend-only change** → PM + LEA Cyber Crime + MEA (UX matters for adoption)
- **Bugfix / refactor** → SKIP Phase 0, go directly to Phase 1

### Output:
Synthesize into a table: what all agree on, where they diverge, what's v1 vs v2.

---

## Phase 1: Requirements

1. Restate the requirements clearly
2. List what's in scope vs explicitly out of scope
3. Reference persona feedback that shaped the design

## Phase 2: Risk Assessment

Identify risks (HIGH/MEDIUM/LOW) and mitigations.
Include risks surfaced by personas (evidence integrity, OPSEC, legal naming, etc.)

## Phase 3: Implementation Plan

1. Break into phases with specific deliverables
2. Identify dependencies between phases
3. List files that will be created or modified
4. Include wiring check items (per /tdd CONNECT step)

## Phase 4: Verification

1. TDD test plan
2. Container rebuild + manual verification steps
3. Demo walkthrough for user

WAIT for user confirmation before touching any code.

Reminder: check hardware.md before adding any ML component — document the hardware upgrade path.
