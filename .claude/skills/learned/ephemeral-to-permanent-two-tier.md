# Ephemeral-to-Permanent Two-Tier Model

## Pattern
When algorithm output is inherently unstable (clustering, ranking, classification),
don't fight the instability. Accept it as a discovery layer and give users a
promotion mechanism to a permanent layer they control.

## Architecture
```
Tier 1: Discovery (ephemeral)     Tier 2: Analyst-owned (permanent)
┌──────────────────────┐          ┌──────────────────────┐
│ Leiden clusters       │   →→→   │ Trackers              │
│ Re-computed every     │  "Open  │ Survive re-clustering │
│ cycle. IDs change.    │ Tracker"│ Content seeded +      │
│ Analyst continuity    │         │ auto-matched (review  │
│ breaks.               │         │ queue). Never deleted. │
└──────────────────────┘          └──────────────────────┘
```

## Key design decisions (validated by 8 personas)
1. Auto-matching goes to REVIEW QUEUE, never auto-inserts (unanimous)
2. Tracker keeps a centroid snapshot — anchor, not drifting average
3. Rejected items go to exclusion list — never re-suggested
4. Every content link has provenance: seed / auto-matched / manual
5. Notes are append-only, immutable (court evidence requirement)
6. Closing summary is mandatory (handover requirement)

## When to apply
Any feature where ML/algorithm output is consumed by humans who need continuity:
- Clustering → Trackers (done)
- Entity resolution → Dossiers (future)
- Anomaly detection → Alerts → Investigations
- Recommendation → Curated lists

## Anti-pattern
Trying to make the algorithm stable (incremental-only clustering, frozen IDs).
This delays the problem but doesn't solve it — eventually a full re-run
scrambles everything. Better to accept instability and build permanence above it.
