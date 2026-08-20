---
name: social-platforms
description: "Social platform adapters and sidecars. Covers Baileys version override for WhatsApp, Redis-buffered sidecar bridges for non-Python SDKs, Telethon peer ID extraction, social URLs resolved to handles, source page as link discovery, and YouTube API key param limits. Use when working on Telegram, WhatsApp, YouTube, X, Bluesky, or Reddit collection."
---

# Social Platform Patterns

7 instincts. Platform adapters, sidecars, and social URL extraction.

## Baileys 405 — Version Override

- WhatsApp rejects Baileys 6.x handshake (Oct 2025+). Override version array:
  `version: [2, 3000, 1033893291], browser: ["Anveshak OSINT", "Chrome", "145.0.0"]`
  Temporary workaround — WhatsApp may rotate accepted versions
- Baileys 6.6.0 better than 6.7.x for initial pairing. Pairing code fallback when QR fails
  See: `.claude/skills/learned/baileys-405-version-override.md`

## Sidecar Bridge + Redis Buffer

- Platform SDK in different language → sidecar: `Platform API → Sidecar (Node.js) → RPUSH Redis → Python LPOP`
  Python adapter implements `SourceAdapterBase.collect()`, drains buffer instead of calling API
- RPUSH + LTRIM caps buffer. Logout sentinel `{"_type": "logout"}` → AdapterAuthError → circuit breaker
  Pre-collect `/health` check prevents silently draining empty buffer
  Pydantic-validate every LPOP'd JSON before yielding RawItem
- Pitfalls: flush stale sentinels after re-pairing (`DEL anveshak:whatsapp:buffer`);
  sequential adapter loop hangs block other adapters; volume permissions (root vs non-root)
  See: `.claude/skills/learned/sidecar-bridge-redis-buffer.md`

## Telethon Peer ID Extraction

- `message.forward.from_id` returns `TypePeer` object, not int. `str()` produces repr:
  `"PeerChannel(channel_id=123456)"` — silently corrupts stored IDs, downstream matches nothing
  Use `telethon.utils.get_peer_id()` or type-specific attribute (`peer.channel_id`)
  Never `str()` on Telethon TL objects expecting plain values
  See: `.claude/skills/learned/telethon-peer-id-extraction.md`

## Social URLs → Handles, Not Domains

- `t.me/username` → TELEGRAM_HANDLE, not URL_DOMAIN. Domain-level = noise hub nodes in graphs
  Dict routing table: domain → (identifier_type, noise_paths frozenset)
  Skip functional paths per platform (share, joinchat, login, explore, reels)
  Non-social URLs: full domain+path via `_normalize_url_path()`, not bare domain
  See: `.claude/skills/learned/telegram-url-to-handle.md`

## Source Page Is Discovery, Not Content

- When `scraper_follow_links=True`, source URL fetched for link discovery ONLY — never stored as content_item
  Homepage always passes quality gates (has text, reasonable ratio) — only architectural knowledge distinguishes it
  When `scraper_follow_links=False`, source URL IS direct article — preserve store behavior
  See: `.claude/skills/learned/scraper-source-page-not-content.md`

## YouTube API Key vs OAuth

- API key = read-only, no user context. `mine` and `forMine` params INVALID — returns 400
  Only use `id` (channel ID) or `forHandle` with API key auth
  `search.list` works but costs 100 units — avoid
  See: `.claude/skills/learned/youtube-api-key-vs-oauth-params.md`

## YouTube Channel ID Over Handle

- `forHandle` API unreliable for channels without verified custom `@handle` (especially smaller/regional)
  Prefer channel ID (`UCxxxx`) — always works. Resolve name → ID via `search.list` once, cache in Redis
  Log `channel_not_found` so analyst knows to retry with ID
  See: `.claude/skills/learned/youtube-channel-id-not-handle.md`