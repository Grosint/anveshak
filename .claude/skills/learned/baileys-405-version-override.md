# Baileys 405 Connection Failure — Version Override

## Problem
WhatsApp changed server-side handshake validation (Oct 2025+). Baileys sends a
`version` array and `browser` fingerprint that WhatsApp now rejects at the
noise-handler `decodeFrame` level. Error: status 405 "Connection Failure".

Affects ALL Baileys 6.x versions (6.6.0, 6.7.9, 6.7.16, 6.7.21).
Not IP-related, not auth-state related.

## Fix
Override the WhatsApp Web version array to a known-accepted value:
```javascript
const sock = makeWASocket({
  version: [2, 3000, 1033893291],
  browser: ["Anveshak OSINT", "Chrome", "145.0.0"],
  auth: authState,
});
```

## Important notes
- This is a **temporary workaround** — WhatsApp may rotate accepted versions
- Baileys 6.6.0 works better than 6.7.x for initial pairing (6.7.x has additional
  noise-handler regressions)
- Pairing code method (`sock.requestPairingCode(phoneNumber)`) works as fallback
  when QR doesn't render
- If version override stops working, try updating the version array from
  WhatsApp Web source or Baileys GitHub issues

## Source
- https://github.com/WhiskeySockets/Baileys/issues/2370
- https://github.com/WhiskeySockets/Baileys/issues/1985
