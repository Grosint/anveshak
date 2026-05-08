# Gitignore Blanket Pattern vs Python Package Collision

## Problem

A blanket `.gitignore` pattern like `models/` or `media/` matches **every** directory
with that name in the tree — including Python source packages like `sdk/anveshak/models/`.

This is invisible on the developer's machine (files exist in the working tree) but
breaks every fresh clone, Docker build, and production deployment with `ImportError`.

The `sdk/pyproject.toml` had an `ignore-vcs = true` workaround for hatchling wheel
builds, but that only fixed pip installs — not git tracking.

## Detection

```bash
# Find source files git is silently ignoring
git ls-files --others --ignored --exclude-standard sdk/
```

If this shows `.py` files — you have a collision.

## Fix

Use **negation patterns** — keep the blanket block, whitelist the Python package:

```gitignore
# Block ML weight dirs everywhere (safety net)
models/
!sdk/anveshak/models/

# Block scraped media everywhere
media/
!sdk/anveshak/media/
```

Also apply the same fix in `.dockerignore`.

## Why NOT use root-only patterns (`/models/`)

Root-only (`/models/`) fails if someone creates `experiments/models/weights.pt` —
the whole point of the blanket pattern is to catch ML weights anywhere in the tree.

## Invariant Test

```bash
# After any .gitignore change, verify SDK packages are not ignored
git check-ignore sdk/anveshak/models/base.py && echo "BROKEN" || echo "OK"
git check-ignore sdk/anveshak/media/downloader.py && echo "BROKEN" || echo "OK"
```

## Lesson

When `.gitignore` uses directory-name patterns, always check if any Python package
shares that name. The collision is silent — it only explodes on fresh clone.
