---
name: uv-workspace-restructure
description: Safe sequence for moving/renaming packages in a uv workspace without breaking installs or imports
type: feedback
---

# uv Workspace Restructure

## When to load: moving, renaming, or flattening service/SDK directories in this repo

---

## Safe sequence (always follow this order)

```
1. Move files on disk  (cp -r / mv)
2. Delete old directory
3. Update pyproject.toml  packages = ["new/path"]
4. Update all Dockerfiles  COPY ... src/
5. uv sync               ← verify before touching anything else
6. Run tests             ← confirm imports resolve
```

**Why this order:** `uv sync` will fail fast if the package declaration is wrong.
Catching it at step 5 is cheap. Catching it at step 6 (tests) or later (Docker build) is expensive.

---

## pyproject.toml packages declaration

```toml
# BEFORE (src layout)
[tool.hatch.build.targets.wheel]
packages = ["src/anveshak"]

# AFTER (flattened)
[tool.hatch.build.targets.wheel]
packages = ["anveshak"]
```

The `packages` value is the **directory path** relative to pyproject.toml,
not the Python import name. The Python import name comes from the directory
name itself (`anveshak/` → `import anveshak`).

---

## Namespace package flattening limit

You CAN remove `src/`:
```
services/api/src/anveshak/api/  →  services/api/anveshak/api/
```

You CANNOT remove `anveshak/<service>/` because:
- The test suite installs multiple services simultaneously
- `from anveshak.api.db.signals import` and `from anveshak.analyst.signal_engine import`
  must be unambiguous
- Without the namespace, `settings.py` from api and `settings.py` from analyst
  would collide

---

## Dockerfile COPY patterns

```dockerfile
# SDK (after flattening sdk/src/ → sdk/)
COPY sdk/ /workspace/sdk/
RUN uv pip install --system /workspace/sdk/

# Service (after flattening src/)
COPY services/api/anveshak/ anveshak/
RUN uv pip install --system .
```

The `COPY ... src/` line must match the actual directory structure on disk.
If pyproject.toml says `packages = ["anveshak"]`, the Dockerfile must COPY into `anveshak/`.

---

## Stale artifact detection

Before any structural work, check for ghost directories from template expansion failures:
```bash
ls -la infra/docker/       # look for {configs, init-pgvector.sql/ (dir not file)
find . -name "{*" -o -name "*}" | grep -v .git
```

These appear when a scaffold/template tool fails mid-execution and leaves partial paths.
They are always empty. Safe to `rm -rf`.

---

## Pitfall: Edit tool requires prior Read in same session

When bulk-updating many files after a restructure, the Edit tool will reject writes
to files not yet read in the current session. Use Python inline scripts instead:

```python
# ✅ Works for bulk updates without prior Read
python3 -c "
content = open('path/to/file').read()
new = content.replace('old', 'new')
open('path/to/file', 'w').write(new)
"
```

Reserve Edit tool for targeted, surgical changes to files already read.

---

## Pitfall: test imports using filesystem paths instead of installed package

Vision tests were broken before this refactor:
```python
# ❌ Wrong — ties tests to directory structure
from services.vision.src.anveshak.vision.media_store import compute_phash

# ✅ Correct — uses installed package
from anveshak.vision.media_store import compute_phash
```

Always import from the installed package name, not the filesystem path.
If a test can't import this way, the package declaration in pyproject.toml is wrong.
