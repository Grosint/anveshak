# YouTube forHandle API Unreliable — Use Channel ID

## Problem
Added YouTube source with `@NagalandJobGK` handle. Adapter used
`channels().list(forHandle="NagalandJobGK")` — returned empty results.
Channel exists but YouTube's `forHandle` API is inconsistent for channels
that don't have a verified custom handle.

## Root Cause
YouTube has 4+ handle formats that don't map consistently:
- `@handle` — custom handle (some channels don't have one)
- `/channel/UCxxxx` — always works, internal ID
- `/c/name` — custom URL (legacy, being deprecated)
- `/user/name` — legacy username

`forHandle` only works for channels with a `@handle` set. Many channels
(especially smaller/regional ones) only have a channel ID.

## Fix
Use `search.list(q="channel name", type="channel")` to resolve the name →
channel ID, then use the channel ID directly. Costs 100 units but only
needed once (cached).

Better: teach users to paste the channel ID (`UCxxxx` format) directly.
The adapter already handles bare channel IDs via `normalize_channel_input()`.

## Prevention
When adding YouTube sources:
1. Prefer channel ID (`UCxxxx`) over handles — always works
2. If using handle, verify it resolves before saving
3. Cache channel_id lookups in Redis to avoid repeat API calls
4. Log `channel_not_found` with the handle so analyst knows to retry with ID
