---
name: infrastructure-pitfalls
description: "Non-obvious Docker, auth, and nginx failures. Covers Alembic migration files invisible inside running containers, passlib failing with bcrypt 4 and returning HTTP 500 on login, and nginx caching upstream DNS until a container restart yields 502. Use when debugging container, migration, login, or 502 errors."
---

# Infrastructure Pitfalls

3 instincts. Non-obvious failures in Docker, auth, nginx.

## Migration Files Invisible in Running Containers

Alembic migrations on host NOT visible in running containers.
`alembic upgrade head` runs zero migrations, no error — file missing in container filesystem. Services use `COPY` in Dockerfile, not volume mounts.

Fix: rebuild image (`docker compose build api`) then run migration in container.
Or `docker cp` for quick iteration.
See: `.agents/skills/learned/references/migration-not-visible-in-container.md`

## passlib + bcrypt>=4.0 Incompatibility

passlib 1.7.x breaks w/ bcrypt>=4.0. bcrypt 4.0 removed `__about__`, changed internal API. `CryptContext(schemes=["bcrypt"])` raises ValueError — all login endpoints HTTP 500.

Fix: replace passlib w/ direct bcrypt wrapper:
```python
import bcrypt as _bcrypt
class _BcryptContext:
    def verify(self, secret: str, hashed: str) -> bool:
        return _bcrypt.checkpw(secret.encode(), hashed.encode())
    def hash(self, secret: str) -> str:
        return _bcrypt.hashpw(secret.encode(), _bcrypt.gensalt(rounds=12)).decode()
pwd_context = _BcryptContext()
```
See: `.agents/skills/learned/references/passlib-bcrypt-incompatibility.md`

## Nginx Dynamic DNS for Docker Services

Nginx resolves upstream hostnames once at startup, caches forever. Backend container restarts (new IP) → nginx sends to old IP → 502.

Fix: `resolver` + `set $upstream` pattern:
```nginx
resolver 127.0.0.11 valid=10s ipv6=off;
location /api/ {
    set $upstream_api http://api:8000;
    proxy_pass $upstream_api;
}
```
Both needed: `resolver` for DNS TTL, `set $upstream` forces per-request resolution.
Apply to WebSocket locations too.
See: `.agents/skills/learned/references/nginx-dynamic-dns-resolver.md`