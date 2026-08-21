# Pattern: Jinja2 `.get(key, default)` Does NOT Guard Against None

## When to load: writing Jinja2 templates that format numeric values

---

## Problem

Python's `dict.get('key', 0)` returns the default `0` only when the key is
**missing**. If the key exists with value `None`, `.get()` returns `None`.

In Jinja2 templates, this crashes arithmetic operations:

```jinja2
{# CRASHES when confidence is None — returns None, not 0 #}
{{ "%.0f"|format(match.get('confidence', 0) * 100) }}%
```

```
TypeError: unsupported operand type(s) for *: 'NoneType' and 'int'
```

---

## The Fix

Use `or default` instead of `.get(key, default)` for numeric formatting:

```jinja2
{# Safe — handles both missing key AND explicit None #}
{{ "%.0f"|format((match.get('confidence') or 0) * 100) }}%
```

---

## When This Happens

- Database returns NULL for a column → Python dict has `key: None`
- Optional fields on Pydantic models serialized to dict
- JSON with explicit `null` values: `{"confidence": null}`
- Any time upstream code sets a field to None instead of omitting it

---

## Rule

For Jinja2 numeric formatting, ALWAYS use `or default`:

| Pattern | Missing key | Key = None | Key = 0 |
|---------|------------|------------|---------|
| `.get('k', 0)` | ✅ 0 | ❌ None | ✅ 0 |
| `.get('k') or 0` | ✅ 0 | ✅ 0 | ⚠️ 0 (falsy!) |
| `.get('k') or 0` | Safe for % display | Safe | OK — 0% is correct display |

Note: `or 0` also converts `0` → `0` (falsy), but for percentage display
this is correct behavior (0% is a valid display value).

---

## Implementation reference
- `services/reporter/anveshak/reporter/pdf.py` line 139 — confidence `or 0` guard
- Same pattern needed for any Jinja2 numeric formatting on nullable DB fields
