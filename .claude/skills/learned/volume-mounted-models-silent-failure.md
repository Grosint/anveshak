# Volume-Mounted ML Models — Silent Failure Pattern

## When to load: any task involving ML model files, ONNX inference, or debugging zero/default ML scores

---

### Problem

When ML model files are volume-mounted (not baked into the Docker image), the **volume starts empty** on first deploy. If the detector's error handling catches `FileNotFoundError` and returns a default score (0.0), the system appears to work but **always returns zero** — a silent failure that looks like a real result.

### Symptoms

- Deepfake score always 0.0 or 0%
- `deepfake_model=error` in logs (if you think to check)
- Vision worker logs show: `model file not found at /app/models/...`
- No crash, no user-facing error — frontend displays "0% deepfake" as if it's a real finding

### Why this happens

1. Dockerfile creates empty model directories: `mkdir -p /app/models/facetorch`
2. Docker volume is mounted over them: `- vision_models:/app/models`
3. Volume persists across rebuilds — so even rebuilding doesn't populate it
4. Detector `score()` catches the exception → returns `0.0, "error"` → stored in DB as real result
5. Comment in Dockerfile says "too large for image — volume-mounted" but no download mechanism exists

### Fix pattern

1. **Create a `make download-models` target** that runs inside the container to populate the volume
2. **Wire it into `make setup`** so first-run provisioning is automatic
3. **Check model existence in health endpoint** — don't report healthy if models are missing
4. **Log at WARNING level** when returning default score due to missing model (already done here, but easy to miss)

### Anti-pattern: swallowing model-load errors

```python
# BAD — returns 0.0 silently, looks like a real result
except Exception as exc:
    log.warning("model.failed", error=str(exc))
    return 0.0, "error"
```

The warning log exists but nobody reads it in production. The fix is making the health endpoint report degraded status when models are missing — then monitoring catches it.

### Checklist for volume-mounted models

- [ ] `make download-models` target exists and works
- [ ] `make setup` calls it automatically
- [ ] Health endpoint checks model files exist
- [ ] Model download script is idempotent (safe to re-run)
- [ ] Volume permissions match the container's non-root user
