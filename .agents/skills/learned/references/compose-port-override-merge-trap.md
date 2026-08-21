# Docker Compose Port Override Merge Trap

## Confidence: HIGH (burned in production 2026-06-29)

Docker Compose v2 **merges** YAML lists across override files. It does NOT replace them.

```yaml
# base compose.yml
api:
  ports:
    - "8000:8000"

# compose.prod.yml (BROKEN — merges, doesn't replace)
api:
  ports:
    - "127.0.0.1:8000:8000"   # APPENDED to base → both try to bind 8000

# Result: "address already in use" crash
```

`ports: []` also doesn't work — merges empty list, base ports remain.

## Fix

Remove ALL `ports:` entries from compose override files. Use cloud/host firewall for port restriction instead. GCP firewall, AWS Security Groups, or host `ufw` — all block external access without touching Docker port bindings.

## When this applies

Any time you create a compose override file (`compose.prod.yml`, `compose.test.yml`) and want to change port bindings from the base file.

## Related

Same merge behavior applies to: `volumes:`, `dns:`, `tmpfs:`, `devices:`, `expose:`.
Only scalar values (strings, numbers) and maps are replaced by overrides. Lists are always merged.
