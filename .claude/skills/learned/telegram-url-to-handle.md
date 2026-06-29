# Social Platform URLs Must Extract as Handle, Not Domain

## Pattern
Social media URLs must extract as platform-specific handle types, not URL_DOMAIN.
`facebook.com/scammerpage` → FACEBOOK_HANDLE, not URL_DOMAIN `facebook.com`.
Every post links to the same domain — extracting it creates noise hub nodes in graphs
and meaningless convergence signals.

## Implementation
Dict-based routing table maps domain → (identifier_type, noise_paths):

```python
_SOCIAL_URL_DOMAINS: dict[str, tuple[str, frozenset[str]]] = {
    "t.me": ("TELEGRAM_HANDLE", frozenset({"s", "share", "joinchat", "addstickers"})),
    "facebook.com": ("FACEBOOK_HANDLE", frozenset({"share", "sharer", "login", ...})),
    "fb.com": ("FACEBOOK_HANDLE", frozenset({...})),
    "twitter.com": ("X_HANDLE", frozenset({"intent", "login", "explore", ...})),
    "x.com": ("X_HANDLE", frozenset({...})),
    "instagram.com": ("INSTAGRAM_HANDLE", frozenset({"explore", "reels", "p", ...})),
}

# In URL extraction loop:
social = _SOCIAL_URL_DOMAINS.get(domain)
if social is not None:
    id_type, noise_paths = social
    path = urlparse(raw).path.strip("/").split("/")[0]
    if path and path.lower() not in noise_paths:
        _add(id_type, raw, path.lower(), 0.9)
    continue
```

## Adding a new social platform
1. Add entry to `_SOCIAL_URL_DOMAINS` dict in `identifiers.py`
2. Follow the identifier type wiring checklist (see `identifier-type-wiring-checklist.md`)

## Generic URLs: full path, not bare domain
Non-social URLs use `_normalize_url_path()` which returns domain+path (strips protocol, www, query, fragment).
`cybercrime.gov.in/reporting/12345` is meaningful; bare `cybercrime.gov.in` is not.

## Noise paths
Each platform has functional/utility paths that are not handles:
- Facebook: share, sharer, login, marketplace, groups, profile.php
- X/Twitter: intent, explore, search, hashtag, settings
- Instagram: explore, reels, stories, p (post shortlink)
- Telegram: s, share, joinchat, addstickers
