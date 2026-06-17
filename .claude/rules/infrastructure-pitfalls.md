# Infrastructure Pitfalls

Consolidated from 3 learned instincts. Non-obvious failure modes in Docker, auth, and nginx.

## Migration Files Invisible in Running Containers

Alembic migration files written on host are NOT visible inside running containers.
`alembic upgrade head` runs zero migrations with no error — file doesn't exist in
container filesystem. Services use `COPY` in Dockerfile, not volume mounts.

Fix: rebuild image (`docker compose build api`) then run migration inside container.
Or use `docker cp` for quick iteration.
See: `learned/migration-not-visible-in-container.md`

## passlib + bcrypt>=4.0 Incompatibility

passlib 1.7.x breaks with bcrypt>=4.0. bcrypt 4.0 removed `__about__` and changed
internal API. `CryptContext(schemes=["bcrypt"])` raises ValueError on first use —
all login endpoints return HTTP 500.

Fix: replace passlib entirely with direct bcrypt wrapper:
```python
import bcrypt as _bcrypt
class _BcryptContext:
    def verify(self, secret: str, hashed: str) -> bool:
        return _bcrypt.checkpw(secret.encode(), hashed.encode())
    def hash(self, secret: str) -> str:
        return _bcrypt.hashpw(secret.encode(), _bcrypt.gensalt(rounds=12)).decode()
pwd_context = _BcryptContext()
```
See: `learned/passlib-bcrypt-incompatibility.md`

## Nginx Dynamic DNS for Docker Services

Nginx resolves upstream hostnames once at startup and caches forever. When a backend
container restarts (new IP), nginx sends to old IP → 502 Bad Gateway.

Fix: `resolver` + `set $upstream` pattern:
```nginx
resolver 127.0.0.11 valid=10s ipv6=off;
location /api/ {
    set $upstream_api http://api:8000;
    proxy_pass $upstream_api;
}
```
Both parts needed: `resolver` for DNS TTL, `set $upstream` to force per-request resolution.
Apply to WebSocket locations too.
See: `learned/nginx-dynamic-dns-resolver.md`
