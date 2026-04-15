---
name: npm-lockfile-docker-ci
description: npm ci in Docker requires a complete, clean lockfile — how to regenerate
type: feedback
---

`npm ci` in Docker has two common failure modes that look identical (both exit code 1):

**Mode 1 — No lockfile found** (usage help printed, no packages listed):
Cause: `COPY package-lock.json*` glob in Dockerfile — Docker silently skips files that
don't match, leaving no lockfile for `npm ci`.
Fix: `COPY frontend/package.json frontend/package-lock.json ./` (no glob).

**Mode 2 — Lockfile missing packages** (long list of "Missing: X from lock file"):
Cause: lockfile was generated with a different npm version or from a partial `node_modules`.
Running `npm install` on top of stale `node_modules` doesn't fix it — it just says "up to date".
Fix: delete both `node_modules` AND `package-lock.json`, then reinstall from scratch:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install --no-audit
# now the lockfile is complete and Docker's npm ci will succeed
```

**Rule:** `--prefer-offline` is useless in Docker (no cache exists in the build context) —
remove it. `npm ci --no-audit` is the correct form.

**Why `--prefer-offline` breaks things:** it makes npm skip packages not in the local cache.
Docker build has no cache → packages silently fail to resolve → `npm ci` errors.

**How to apply:** any time `npm ci` fails in Docker — first check if lockfile is present and
complete. If "Missing:" entries appear, wipe both node_modules and lockfile and reinstall.
