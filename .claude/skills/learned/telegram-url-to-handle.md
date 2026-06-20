# Telegram URLs Must Extract as Handle, Not Domain

## Pattern
`https://t.me/username` URLs must be extracted as TELEGRAM_HANDLE (`username`),
not URL_DOMAIN (`t.me`). Every Telegram message contains t.me links, so extracting
the domain creates one giant hub node that dominates any graph visualization and
pollutes identifier clustering.

## Context
Intelligence Graph showed a massive purple "t.me" circle connected to everything.
61 content items linked to a single `t.me` identifier cluster. Root cause: URL
extraction regex matched `https://t.me/defencenews`, `urlparse` normalized to
domain `t.me`, and every Telegram link collapsed to the same entity.

## Rule
In URL_DOMAIN extraction, check domain before adding:
- `t.me` → extract path segment as TELEGRAM_HANDLE, skip URL_DOMAIN
- Skip noise paths: `s`, `share`, `joinchat`, `addstickers`

```python
if domain == "t.me":
    path = urlparse(raw).path.strip("/").split("/")[0]
    if path and path.lower() not in {"s", "share", "joinchat", "addstickers"}:
        _add("TELEGRAM_HANDLE", raw, path.lower(), 0.9)
    continue
```

## Broader principle
Social media URL domains (t.me, instagram.com, twitter.com) are not useful as
URL_DOMAIN entities — they appear everywhere. Extract the username/handle from
the path instead. Apply same pattern for other social platforms if needed.
