# YouTube API Key vs OAuth — Parameter Restrictions

## Problem
YouTube adapter auth test call used `mine=False` parameter:
```python
self._youtube.channels().list(part="id", mine=False, id="UC_x5XG...")
```
API returned `400: The request's use of the mine parameter is not supported.`

## Why
YouTube Data API v3 has two auth modes:
- **API Key**: read-only, no user context. `mine` parameter is INVALID.
- **OAuth 2.0**: user context. `mine=True` returns the authenticated user's channel.

`mine=False` is not a valid value in either mode — it's a boolean that only
makes sense as `True` with OAuth.

## Fix
Remove `mine` parameter entirely for API key auth:
```python
self._youtube.channels().list(part="id", id="UC_x5XG1OV2P6uZZ5FSM9Ttw").execute()
```

## Prevention
When using YouTube Data API with API key (not OAuth):
- Never use `mine` parameter
- Never use `forMine` parameter
- `forHandle` works with API key (channel lookup)
- `id` works with API key (direct channel ID)
- `search.list` works but costs 100 units (avoid)
