# Coordinated Amplification Detection — Feature Plan

## Status: PLANNED (not yet implemented)

## Problem Statement

Anveshak currently detects **what** is being said (clustering), **who** is saying it
(source tracking), and **whether it's real** (deepfake detection). What it cannot
detect is **coordinated behaviour** — when multiple accounts or channels share the
same content within a short time window in a pattern that suggests orchestration
rather than organic spread.

This matters because coordinated amplification is a primary tactic in information
warfare. A single fabricated image shared by 12 Telegram channels within 3 hours
is not 12 independent signals — it is one operation. Without detecting the
coordination, Anveshak risks:

- Inflating `independent_source_count` (false signal elevation)
- Boosting credibility of coordinated sources via cross-verification
- Missing the meta-signal: the coordination itself is intelligence

## What Exists Today

| Capability | Status | Limitation |
|------------|--------|------------|
| Content deduplication (SHA-256 `content_hash`) | YES | Detects identical text, but doesn't track *when* or *how many* sources shared it |
| Near-duplicate detection (embedding cosine similarity) | YES | Operates within a single topic; doesn't count sources or time-window the spread |
| pHash reverse image search (Hamming distance) | YES | Manual query only; not run automatically on ingest |
| Credibility auto-downgrade on deepfake sharing | YES | Reacts to deepfake content, but not to coordination patterns |
| Cross-topic convergence (centroid similarity) | YES | Detects narrative overlap across topics, not account-level coordination |

## What We Need to Build

### Core Concept: Amplification Event

An **amplification event** is detected when:

- The same content (by `content_hash`, pHash similarity, or embedding similarity)
  appears from **N+ distinct sources** within a **T-hour time window**
- Default thresholds: N=3 sources, T=6 hours (configurable via settings)

This is distinct from organic multi-source convergence. Organic convergence
involves different sources reporting on the same *topic* with different *content*.
Coordinated amplification involves different sources sharing the *same content*
(or near-identical copies) within a suspiciously short window.

### Detection Methods (Layered)

**Layer 1: Exact Match (content_hash)**

Cheapest check. Group `content_items` by `content_hash` within a time window.
If 3+ distinct `source_id` values share the same hash within 6 hours, flag it.

```sql
SELECT content_hash,
       COUNT(DISTINCT source_id) AS source_count,
       MIN(captured_at) AS first_seen,
       MAX(captured_at) AS last_seen,
       ARRAY_AGG(DISTINCT source_id) AS source_ids
FROM content_items
WHERE captured_at > NOW() - INTERVAL '24 hours'
GROUP BY content_hash
HAVING COUNT(DISTINCT source_id) >= $1  -- amplification_min_sources
   AND MAX(captured_at) - MIN(captured_at) <= $2  -- amplification_window interval
```

**Layer 2: Media Match (pHash Hamming distance)**

For images/videos that are cropped, resized, or re-encoded but visually identical.
Run pHash comparison on media ingested within the time window.

```sql
SELECT ma1.content_item_id AS item_a,
       ma2.content_item_id AS item_b,
       BIT_COUNT(ma1.phash # ma2.phash) AS hamming_distance
FROM media_assets ma1
JOIN media_assets ma2 ON ma1.id < ma2.id
JOIN content_items ci1 ON ma1.content_item_id = ci1.id
JOIN content_items ci2 ON ma2.content_item_id = ci2.id
WHERE ci1.captured_at > NOW() - INTERVAL '24 hours'
  AND ci2.captured_at > NOW() - INTERVAL '24 hours'
  AND ci1.source_id != ci2.source_id
  AND ma1.phash IS NOT NULL
  AND ma2.phash IS NOT NULL
  AND BIT_COUNT(ma1.phash # ma2.phash) <= $1  -- phash_amplification_threshold (default 8)
```

Group results by connected component (Union-Find) to identify amplification clusters.

**Layer 3: Semantic Match (embedding similarity)**

For paraphrased versions of the same content (e.g., machine-translated copies,
light rewrites). Uses existing near-duplicate infrastructure but operates
**cross-source** within a time window, not just within a topic.

```sql
SELECT ci1.id AS item_a, ci2.id AS item_b,
       1 - (ci1.embedding <=> ci2.embedding) AS similarity
FROM content_items ci1
JOIN content_items ci2 ON ci1.id < ci2.id
WHERE ci1.captured_at > NOW() - INTERVAL '24 hours'
  AND ci2.captured_at > NOW() - INTERVAL '24 hours'
  AND ci1.source_id != ci2.source_id
  AND 1 - (ci1.embedding <=> ci2.embedding) >= $1  -- amplification_semantic_threshold (default 0.92)
```

### Architecture

#### New Database Table

```sql
CREATE TABLE amplification_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    detection_method TEXT NOT NULL,  -- 'content_hash' | 'phash' | 'semantic'
    content_hash    TEXT,            -- NULL for phash/semantic matches
    source_count    INTEGER NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL,
    last_seen_at    TIMESTAMPTZ NOT NULL,
    spread_seconds  INTEGER NOT NULL,  -- last_seen - first_seen in seconds
    source_ids      UUID[] NOT NULL,
    content_item_ids UUID[] NOT NULL,
    topic_ids       UUID[] NOT NULL,   -- may span topics
    severity        TEXT NOT NULL DEFAULT 'MEDIUM',  -- HIGH if source_count >= 5
    labels          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_amplification_events_created
    ON amplification_events (created_at DESC);
```

No `updated_at` — amplification events are **immutable snapshots**, like reports.
Once detected, they are never modified.

#### New Async Loop

Add `amplification_loop()` to `services/analyst/anveshak/analyst/main.py`,
following the existing pattern:

```python
async def amplification_loop(pool: asyncpg.Pool, broadcast: Callable) -> None:
    """Detect coordinated amplification patterns. Runs every amplification_check_interval_s."""
    while True:
        try:
            events = await detect_amplification(pool)
            for event in events:
                await persist_amplification_event(pool, event)
                await fire_amplification_signal(pool, event, broadcast)
                await apply_coordination_penalty(pool, event)
        except Exception:
            structlog.get_logger().exception("amplification_loop_error")
        await asyncio.sleep(settings.amplification_check_interval_s)
```

#### Signal Integration

Fire a new signal type: `coordinated_amplification`

```python
signal_type = "coordinated_amplification"
severity = "HIGH" if event.source_count >= 5 else "MEDIUM"
evidence = {
    "amplification_event_id": str(event.id),
    "detection_method": event.detection_method,
    "source_count": event.source_count,
    "spread_seconds": event.spread_seconds,
    "source_ids": [str(s) for s in event.source_ids],
    "content_item_ids": [str(c) for c in event.content_item_ids],
}
```

Uses existing 24h signal dedup — same amplification event won't fire twice.
Delivered via existing WebSocket push to analyst sessions.

#### Credibility Integration

Sources participating in coordinated amplification get a credibility penalty:

```python
reason = (
    f"Source participated in coordinated amplification event: "
    f"{event.source_count} sources shared same content within "
    f"{event.spread_seconds}s ({event.detection_method} match)"
)
new_score = old_score - settings.credibility_amplification_drop  # default 3.0 per event
```

Uses existing `apply_credibility_drop()` + `credibility_audit_log`.
Immutable audit trail preserved.

#### ISC Correction

When computing `independent_source_count` for a narrative cluster, sources
that are part of the same amplification event should count as **one source**,
not N sources:

```python
# In clustering.py, after computing raw ISC:
amplified_groups = await get_amplification_groups(conn, content_item_ids)
adjusted_isc = count_independent_sources_with_amplification(
    platforms, amplified_groups
)
```

This prevents coordinated amplification from inflating signals.

### Configuration (settings.py)

```python
# Coordinated amplification detection
amplification_check_interval_s: int = 600       # run every 10 minutes
amplification_min_sources: int = 3              # minimum distinct sources
amplification_window_hours: float = 6.0         # time window for spread
amplification_semantic_threshold: float = 0.92  # embedding similarity
phash_amplification_threshold: int = 8          # Hamming distance
credibility_amplification_drop: float = 3.0     # credibility penalty per event
```

All from environment variables. No hardcoded values.

### Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| Create | `services/analyst/anveshak/analyst/amplification.py` | Detection logic (3 layers) |
| Create | `services/api/migrations/versions/008_amplification_events.py` | New table |
| Modify | `services/analyst/anveshak/analyst/main.py` | Add `amplification_loop()` |
| Modify | `services/analyst/anveshak/analyst/settings.py` | Add configuration variables |
| Modify | `services/analyst/anveshak/analyst/clustering.py` | ISC correction |
| Modify | `services/analyst/anveshak/analyst/credibility.py` | Coordination penalty |
| Create | `services/api/anveshak/api/routes/amplification.py` | API endpoints |
| Modify | `services/api/anveshak/api/app.py` | Register router |
| Create | `frontend/src/api/amplification.ts` | Frontend API client |
| Create | `frontend/src/components/signals/AmplificationBadge.tsx` | UI badge |
| Create | `tests/unit/test_amplification.py` | Unit tests |
| Create | `tests/integration/test_amplification.py` | Integration tests |

### Frontend Display

In the Signals inbox, `coordinated_amplification` signals show:

- **Badge:** "Coordinated" (red, distinct from multi-source convergence)
- **Source count:** "N sources in T minutes"
- **Source list:** expandable list of participating sources with credibility scores
- **Detection method:** content_hash / pHash / semantic
- **Timeline:** visual spread showing when each source posted

### Implementation Phases

**Phase 1: Layer 1 — Exact content_hash match** (smallest scope, highest confidence)
- Migration, detection loop, signal firing, credibility penalty
- Unit + integration tests
- Estimated: 1-2 days

**Phase 2: Layer 2 — pHash media match**
- Auto-run pHash comparison on recent media (currently manual only)
- Union-Find grouping for connected components
- Estimated: 1 day

**Phase 3: Layer 3 — Semantic match**
- Cross-source embedding similarity within time window
- Bounded by batch size to avoid O(N^2) explosion
- Estimated: 1 day

**Phase 4: ISC correction + frontend**
- Adjust `independent_source_count` to exclude amplified sources
- Frontend amplification badge and timeline
- Estimated: 1 day

### Hardware Considerations

- Layer 1 (content_hash): pure SQL GROUP BY — negligible cost
- Layer 2 (pHash): SQL BIT_COUNT — negligible cost, bounded by 24h window
- Layer 3 (semantic): O(N^2) embedding comparison — bounded by `near_duplicate_batch_size`
- No new ML models required
- No GPU dependency
- All CPU-feasible

### Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| False positives on legitimate syndicated content (AP, Reuters) | MEDIUM | Allow source-level opt-out via `source.labels.syndication_network` |
| O(N^2) on Layer 3 semantic matching | LOW | Bounded by batch size + 24h window |
| Credibility penalty on innocent sources | LOW | Conservative defaults (3+ sources, 6h window); audit log enables reversal |
| Signal spam from large coordination events | LOW | 24h dedup window; one signal per amplification event |

### What This Enables (Brochure-Safe Claims After Implementation)

Once built, we can truthfully claim:

- "Anveshak detects coordinated amplification — when multiple sources share
  the same content within a short time window, flagging it as a single
  operation rather than independent corroboration"
- "Sources participating in coordinated campaigns are automatically
  penalised, with full audit trail"
- "Independent source count is adjusted to exclude coordinated sources,
  preventing false signal elevation"
