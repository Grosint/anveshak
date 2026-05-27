# Telethon Peer ID Extraction

## Problem

Telethon's `MessageFwdHeader.from_id` returns a `TypePeer` object (`PeerChannel`,
`PeerUser`, or `PeerChat`), not an integer. Calling `str()` on it produces the
repr string — e.g. `"PeerChannel(channel_id=123456)"` — not the numeric ID.

This silently corrupts any column storing the ID, because:
- The garbage string is a valid `TEXT` value — no error at insert time
- Downstream queries matching on the stored value find nothing
- The feature appears to work but produces zero results

## Where it bit us

Telegram forwarding discovery (Level 2): `forwarded_from_channel_id` was stored
as `"PeerChannel(channel_id=123456)"` instead of `"123456"`. The discovery job
aggregated these IDs but none matched any real channel.

## Solution

Use `telethon.utils.get_peer_id()` to extract the numeric ID:

```python
from telethon import utils as tl_utils

# WRONG — produces "PeerChannel(channel_id=123456)"
fwd_channel_id = str(message.forward.from_id)

# CORRECT — produces "123456"
fwd_channel_id = str(tl_utils.get_peer_id(message.forward.from_id))
```

Alternative: access the type-specific attribute directly:

```python
from telethon.tl.types import PeerChannel, PeerUser, PeerChat

peer = message.forward.from_id
if isinstance(peer, PeerChannel):
    fwd_channel_id = str(peer.channel_id)
elif isinstance(peer, PeerUser):
    fwd_channel_id = str(peer.user_id)
elif isinstance(peer, PeerChat):
    fwd_channel_id = str(peer.chat_id)
```

## General rule

Never call `str()` on a Telethon TL object expecting a plain value. TL objects
are dataclasses whose `__str__` is their constructor repr. Always use the
type-specific attribute or `telethon.utils` helpers.

Applies to: `from_id`, `peer`, `chat_id` fields on messages, dialogs, and events.
