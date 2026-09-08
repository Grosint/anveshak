# Narrative detection implementation plan

Epic #21.
Sub-issues #22 to #36.

This document is written once and read at the start of every session that works on this epic.
A session needs three lines: read this plan, state the step, run TDD.

Vocabulary is in [CONTEXT.md](../CONTEXT.md).
Decisions are in [ADR 0001](adr/0001-ranking-by-propagation-not-concern.md) and [ADR 0002](adr/0002-cloud-model-guard.md).
Excluded work is in [deferred_scope.md](deferred_scope.md).

---

## Architecture

### A Watch Space is a Topic

`narrative_clusters.topic_id` is NOT NULL, and clusters inherit organisation scope through it.
Making it nullable would touch cascade deletes, every cluster query, and the organisation isolation model.

So a Watch Space is an ordinary Topic carrying `is_watch_space = TRUE`, with broad keywords and many attached sources.
Its clusters are ordinary clusters and the clustering path does not change.
Promotion creates a child Topic with `parent_topic_id` pointing back at the Watch Space, and the existing backfill job populates it.

Watch Space keywords describe a domain and name no specific organisation, party, or individual.
If a target appears in the keywords, the claim that detection found a narrative unaided is false, and that is the first thing a customer checks.

### Detection reuses the existing propose-then-approve pattern

`services/analyst/anveshak/analyst/discovery.py` already implements it for sources: a background job writes rows with `status = 'pending'`, an analyst approves or rejects, output is model-validated, and no cloud call is involved.
Candidate Topic detection mirrors that pattern rather than introducing a second one.

### Promotion requires four gates, all of which must pass

| Gate | Setting | Reason |
|------|---------|--------|
| Independent source count | `promotion_min_independent_sources` | a narrative nobody else carries is not yet a narrative |
| Cluster size | `promotion_min_item_count` | too small to read |
| Novelty | `promotion_max_similarity_to_existing` | without it the inbox fills with rediscoveries of Topics the analyst already tracks |
| Persistence | `promotion_min_runs` | a single transient spike is not a narrative |

Novelty is the gate most likely to be omitted and the one that matters most.
Persistence is measured as the number of consecutive clustering runs in which the cluster passed the other three gates.

### Stance and hostility run after clustering, not at ingest

Stance requires a target, and the target is the cluster label, which is unknown at ingest time.
Scoring therefore runs in a job chained from clustering, not in the ingest enrichment sequence where the lexicon sentiment score lives.

Stance is direction: supporting, opposing, neutral.
Hostility is intensity.
Neither predicts the other, which is why they are two measures from two models.
A furious post supporting a narrative and a calm post opposing it are opposite in stance and indistinguishable to any single sentiment score.

Stance uses a multilingual zero-shot natural language inference model, which needs no labelled training data and reads Devanagari directly rather than through a translation.
Hostility uses a separate multilingual toxicity model.

Both run only on clusters above `stance_min_cluster_size`, because a timeline is only drawn where there is something to draw.

### Stance and hostility are columns, not label metadata

Enrichment results conventionally live in `content_items.labels`.
These two are columns because the timeline aggregates them per day across the whole content table, and per-row JSONB extraction does not hold up at that scale.
This deviation is reviewed by schema-guard.

### Publication time becomes a first-class field

`captured_at` conflates publication time with collection time.
Adapters populate it with publication time when the platform supplies one and with `now()` when it does not, and afterwards the two cases are indistinguishable.

`published_at` is added as a nullable column, populated by an adapter only when the platform genuinely provides a publication time, and left NULL otherwise.
The timeline plots `published_at` and excludes NULLs rather than stacking them at today.
The change is additive: nothing that reads `captured_at` changes.

### Manufactured Narrative is the inverse of the existing convergence rule

The existing multi-source convergence signal fires when independent source count rises.
This one fires when item count and contributing account count rise while independent source count stays flat.
It reuses metrics already computed.

Its source-count ceiling must sit below the promotion source-count floor, or one cluster qualifies as both at once.
That is an invariant test, not a comment.

### Mobilization is lexicon-first with a bounded model confirmation

A versioned multilingual lexicon of call-to-assemble patterns proposes candidates at ingest volume.
A language model then confirms and extracts date and place on that candidate set only, dispatched as a background job with model-validated output.

The reason is defensibility rather than cost.
A signal citing the phrase that fired it survives scrutiny; one reporting a model's impression does not.
If the local model misses its acceptance bar, the confirmation step ships disabled and the lexicon runs alone, which still produces a defensible signal.
That is a planned outcome, not a failure.

---

## Schema additions

One migration, `006_narrative_detection.py`.

```
content_items:
  published_at   TIMESTAMPTZ NULL     -- publication time, NULL when the platform gave none
  stance         TEXT        NULL     -- supporting | opposing | neutral | unsupported_language
  hostility      REAL        NULL     -- 0.0 to 1.0, NULL on scoring error (never 0.0)

topics:
  is_watch_space  BOOLEAN NOT NULL DEFAULT FALSE
  parent_topic_id TEXT    NULL REFERENCES topics(id) ON DELETE SET NULL

candidate_topics:      -- new table
  id, cluster_id, watch_space_id, org_id, status,
  independent_source_count, item_count, novelty_score, run_count,
  evidence JSONB, labels JSONB, created_at, updated_at
```

`org_id` goes directly on `candidate_topics` because the table is reachable by direct UUID.
Everything else inherits organisation scope through `topic_id`, per the root-tables-only rule.

Two new `signals.signal_type` values: `manufactured_narrative` and `mobilization_call`.

Backfill decision for `published_at` on pre-existing rows: leave NULL.
The pre-existing value of `captured_at` cannot be separated into publication and collection after the fact, so copying it forward would manufacture data.
Recorded in the migration.

---

## Phases

Each phase ends green: `make lint`, `make typecheck`, `make test-unit`, and the review agents named in CLAUDE.md.

### Phase 0 — Decisions of record
Issue: none.
ADR 0001, ADR 0002, this plan, the deferred scope register, and the CONTEXT.md vocabulary additions.

### Phase 1 — Foundations, no dependencies
Issues #22, #23, #24, #25, #28, #31, #35.
Cloud model guard, X collection width, publication time, Watch Space, stance and hostility scoring, severity restyle, Actor View.
Migration 006 lands here.

### Phase 2 — Detection and signals
Issues #26, #30, #32, #33.
Candidate Topic detection and inbox, the sentiment-shift rebase onto hostility, the Manufactured Narrative signal, the Mobilization lexicon signal.

### Phase 3 — Analyst surfaces
Issues #27, #29, #36.
Accept and dismiss, the Sentiment Timeline, the concern taxonomy facet.

### Phase 4 — Model confirmation
Issue #34.
Mobilization model confirmation and the local against cloud benchmark.
Ships disabled if either acceptance bar is missed.

---

## Settings inventory

Every setting below is read from the environment, appears in the compose `environment:` block, and appears in `.env.example`.
No model name, device string, batch size, or threshold is hardcoded in service code.

| Setting | Default | Issue |
|---------|---------|-------|
| `LLM_CLOUD_ENABLED` | `false` | #22 |
| `LLM_CLOUD_PROVIDER` | `""` | #22 |
| `LLM_CLOUD_MODEL` | `""` | #22 |
| `ANVESHAK_ENV` | `development` | #22 |
| `X_MAX_RESULTS` | `100` | #23 |
| `STANCE_MODEL` | `joeddav/xlm-roberta-large-xnli` | #28 |
| `STANCE_DEVICE` | `cpu` | #28 |
| `STANCE_BATCH_SIZE` | `8` | #28 |
| `STANCE_MIN_CLUSTER_SIZE` | `5` | #28 |
| `HOSTILITY_MODEL` | `textdetox/xlmr-large-toxicity-classifier` | #28 |
| `HOSTILITY_DEVICE` | `cpu` | #28 |
| `HOSTILITY_BATCH_SIZE` | `8` | #28 |
| `PROMOTION_MIN_INDEPENDENT_SOURCES` | `3` | #26 |
| `PROMOTION_MIN_ITEM_COUNT` | `10` | #26 |
| `PROMOTION_MAX_SIMILARITY_TO_EXISTING` | `0.80` | #26 |
| `PROMOTION_MIN_RUNS` | `2` | #26 |
| `MANUFACTURED_MAX_INDEPENDENT_SOURCES` | `2` | #32 |
| `MANUFACTURED_MIN_ITEM_COUNT` | `15` | #32 |
| `MANUFACTURED_MIN_ACCOUNT_COUNT` | `5` | #32 |
| `HOSTILITY_SHIFT_THRESHOLD` | `0.15` | #30 |
| `MOBILIZATION_LEXICON_PATH` | `/app/data/mobilization_lexicon.yaml` | #33 |
| `MOBILIZATION_CONFIRM_ENABLED` | `false` | #34 |
| `CONCERN_TAXONOMY_PATH` | `/app/data/concern_taxonomy.yaml` | #36 |

---

## Invariant tests, mandatory

These assert that configuration cannot defeat itself.
They read values from `settings`, never hardcoded numbers, so a configuration change surfaces as a failing invariant rather than a silently passing test.

```python
assert settings.manufactured_max_independent_sources < settings.promotion_min_independent_sources
assert settings.stance_min_cluster_size <= settings.promotion_min_item_count
assert settings.promotion_min_runs >= 2
```

The first: a cluster cannot qualify as both a promotion candidate and a manufactured narrative.
The second: a promoted Topic without stance data renders an empty timeline.
The third: persistence below two runs promotes single spikes.

---

## Test matrix

Three seams, all of which already exist.
No new seam is introduced.

| Seam | Prior art | Covers |
|------|-----------|--------|
| Analyst pipeline | `tests/integration/test_cluster_signal_pipeline.py` | promotion gating, Manufactured Narrative, Mobilization, stance and hostility |
| Database repository | `tests/integration/test_db_*.py`, `test_org_isolation.py`, `test_rls_enforcement.py` | timeline aggregate query, candidate isolation, cross-organisation leak prevention |
| Frontend integration | existing signal-flow and topic-lifecycle tests | Candidate inbox, timeline chart, severity restyle |

Machine learning realism: test embeddings are L2-normalised, cluster fixtures are seeded random noise around base vectors at realistic dispersion, and golden Hindi and English content uses fuzzy keyword matching because translation is not deterministic.

Mocking discipline: a new async database function means grepping every test that mocks that module and adding an `AsyncMock`, since awaiting a plain `MagicMock` raises `TypeError`.
A query gaining a JOIN means expanding the fake row dictionaries in tests that consume it.

Acceptance bars for #34: mobilization detection precision at least 0.85, weighted over recall because a false mobilization alert about a political group is the worst output this system can produce.
Date and place exact-match accuracy at least 0.70, with the matched phrase always displayed so an analyst can correct it.
Measured on a labelled set of 100 to 200 examples drawn from public reporting of past events.

---

## Risk register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Novelty gate omitted | inbox fills with rediscoveries, feature looks broken | gate is a named setting with its own test; #26 acceptance criterion |
| Watch Space keywords name a target | the unaided-detection claim is false and checkable | test asserts no keyword matches a known organisation or person name |
| Stance model too slow on CPU | scoring backs up, timeline stays empty | `stance_min_cluster_size` bounds the work; device and batch size are settings |
| `published_at` NULL for most rows | timeline looks empty | NULL count is a visible footnote, never a silent exclusion |
| Local mobilization model misses its bar | confirmation cannot ship | planned: lexicon runs alone, step ships disabled, reason logged at startup |
| Concern score leaks into an ordering | product becomes a dissent detector | ADR 0001 plus a test that a filter changes membership and not ordering |
| A model returns 0.0 on failure | silent wrong data | hostility returns NULL on error, never 0.0; call sites null-check |
