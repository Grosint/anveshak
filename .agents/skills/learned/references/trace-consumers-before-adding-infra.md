---
name: trace-consumers-before-adding-infra
description: Before adding infrastructure (MinIO, message queues, caches), trace ALL consumers of the data — if nothing reads it after initial processing, the infra is waste
type: pattern
confidence: high
source: MinIO architecture decision — media files are write-once-read-once, no consumer needs object storage
---

# Trace Consumers Before Adding Infrastructure

Before adding a new infrastructure component (MinIO, Kafka, ElasticSearch, etc.),
enumerate every consumer of the data it would manage. If the data is only consumed
once (at write time), the infrastructure adds cost with no benefit.

## The Checklist

For each data type the new infra would store, answer:

1. **Who writes it?** (scraper, social, API upload)
2. **Who reads it after initial processing?** (API endpoints, reports, frontend, other services)
3. **Is there a serving endpoint?** (can users/analysts fetch it back?)
4. **What's the access pattern?** (write-once-read-once vs frequent reads)
5. **What's the growth rate?** (MB/day, retention needed?)

## The Decision

| Access Pattern | Recommendation |
|---------------|---------------|
| Write-once, read-once | Local volume + retention policy |
| Write-once, read-many (serving) | Consider object storage |
| Write-once, multi-node | Object storage needed |
| Write-many, read-many | Object storage + CDN |

## Example: Anveshak Media

- Written by: scraper, social adapters
- Read by: vision pipeline (once, at processing time)
- Serving endpoint: none
- Access pattern: write-once-read-once
- Decision: Docker volume + 30-day retention, no MinIO

## How to apply

When someone proposes adding infrastructure, ask "who reads this data and how often?"
If the answer is "only once during processing," a local volume with cleanup is sufficient.
Revisit when access patterns change (e.g., adding a media viewer to the frontend).
