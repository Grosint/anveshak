# Seed Data Masks Real Pipeline Failures

## Problem

Pipeline health check reported 84 CRITICALs. 83 were stale seed sources (fake
Reddit handles, fake Telegram channels, paused RSS feeds). The 1 real issue
(social-worker missing) was buried in noise.

Same pattern earlier: seed Telegram content in `ec-topic-cyber` made it look like
social scraping was working. It wasn't — social-worker container didn't exist.

## Rule

Seed data must be visually distinguishable from real data at every layer:
1. **Sources**: seed source IDs use `ec-src-*` prefix — deactivate when not demoing
2. **Content**: seed content has fabricated timestamps — check `captured_at` spread
3. **Health checks**: filter `is_active = true` sources only (done now)
4. **Topics**: name convention "Demo X" vs "Live X" (adopted this session)

After any real pipeline work, deactivate seed sources to reduce health noise:
```sql
UPDATE sources SET is_active = false WHERE id LIKE 'ec-src-%';
```

## Detection heuristic

If health check shows > 20 CRITICALs and all are staleness issues → likely
seed data flooding. Verify with:
```sql
SELECT COUNT(*) FROM sources WHERE is_active = true AND id LIKE 'ec-src-%';
```

## See also

- `seed-sql-must-match-migration.md` — seed SQL schema drift
- `compose-worker-for-every-arq-scheduler.md` — the real failure seed data masked
