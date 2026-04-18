# Docker Nuke — Graduated Cleanup Targets

## When to load: any task involving Docker cleanup, `make purge`, `make nuke`, or simulating fresh clone

> See also: `learned/docker-compose-build-context.md` — context paths relative to compose file
> See also: `learned/compose-project-name-consistency.md` — -p flag for consistent naming

---

### Problem

`docker image prune -f` only removes **dangling** (untagged) images. Tagged images like `anveshak-analyst:latest` (12GB) survive. A developer trying to simulate a fresh clone still has 35GB+ of cached images that mask build failures.

### Pattern: Graduated cleanup levels

```
make clean            → Python caches only (__pycache__, .pytest_cache)     ~instant
make clean-containers → stop + remove containers (keep volumes/data)        ~5s
make clean-volumes    → containers + volumes (DB data lost)                  ~5s
make clean-cache      → Docker build cache prune                            ~5s
make purge            → all of the above + dangling images                  ~10s
make nuke             → purge + tagged images + base images + system prune  ~15s, reclaims 35GB+
```

### `make nuke` — the 5-step sequence

```makefile
nuke:
    # 1. Remove containers + volumes across ALL compose configs
    @$(COMPOSE_BRG) down -v --remove-orphans 2>/dev/null || true
    @$(COMPOSE_VIS) down -v --remove-orphans 2>/dev/null || true
    @$(COMPOSE) down -v --remove-orphans 2>/dev/null || true

    # 2. Remove tagged project images (purge misses these)
    @docker images -q --filter reference='anveshak-*' | xargs docker rmi -f 2>/dev/null || true
    @docker images -q --filter reference='infra-*' | xargs docker rmi -f 2>/dev/null || true

    # 3. Remove third-party base images (for true cold-pull test)
    @docker rmi pgvector/pgvector:pg16 redis:7-alpine ollama/ollama:latest \
        prom/prometheus:latest grafana/grafana:latest ... 2>/dev/null || true

    # 4. Prune build cache + system
    @docker builder prune --all -f 2>/dev/null || true
    @docker system prune -f 2>/dev/null || true

    # 5. Python caches
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
```

### Key rules

1. **Always `2>/dev/null || true`** on removal commands — images/containers may not exist.
2. **Use `--filter reference='anveshak-*'`** not `grep` — safer, handles edge cases.
3. **Include all compose overlay files** (bridge, vision) — orphan containers from overlays survive if only the base compose is taken down.
4. **Always ask for confirmation** on destructive targets — `read confirm` guard.
5. **List what will be destroyed** in the prompt — users need to know they're losing DB data and Ollama models.

### Discovered during

Clean-slate Makefile testing (2026-04-18): `make purge` left 30GB+ of tagged images. Had to manually run `docker rmi` to actually simulate a fresh clone.
