---
name: docker-compose-build-context
description: compose build context paths are relative to the compose FILE, not the CWD
type: feedback
---

Docker Compose resolves `context:` paths relative to the **compose file's location**, not the
working directory of the `docker compose` command.

**Pitfall:** `infra/compose.yml` with `context: ../..` resolves to the *grandparent* of
`infra/` — i.e. the parent of the project root. This is almost never what you want.

```
anveshak/
  infra/
    compose.yml       ← file is here
      context: ../..  ← resolves to /Users/navitas28/Work/ (WRONG)
      context: ..     ← resolves to /Users/navitas28/Work/anveshak/ (CORRECT)
```

**Fix:** when the compose file is one level deep inside the project (e.g. `infra/`), use
`context: ..` to reach the project root.

**Rule:** `context` depth = number of directories between compose file and project root.
- compose at `infra/compose.yml` → `context: ..`
- compose at `infra/docker/compose.yml` → `context: ../..`

**How to apply:** any time a compose build fails with
`lstat /path/services: no such file or directory` — check the context depth.
