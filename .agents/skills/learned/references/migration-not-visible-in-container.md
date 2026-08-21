# Migration File Not Visible in Running Container

## Problem

Writing a new Alembic migration file on the host does NOT make it visible inside
a running Docker container. `alembic upgrade head` reports "Will assume transactional DDL"
but runs zero migrations — the file simply doesn't exist in the container filesystem.

No error is raised. `alembic current` still shows the old revision as `(head)`.

## Solution

Either:

1. **`docker cp`** the migration file into the container:
   ```bash
   docker cp services/api/migrations/versions/006_foo.py \
     anveshak-api-1:/workspace/services/api/migrations/versions/006_foo.py
   docker compose exec api alembic upgrade head
   ```

2. **Rebuild the image** (preferred for production):
   ```bash
   docker compose build api
   docker compose up -d api
   docker compose exec api alembic upgrade head
   ```

## Why this happens

Anveshak services are built with `COPY` in the Dockerfile, not volume-mounted.
The running container has a snapshot of the code from build time. New files on
the host are invisible until copied in or the image is rebuilt.

## When to apply

Every time you create a new migration file. Don't forget the test database too:
```bash
docker compose exec api bash -c \
  'POSTGRES_URL="postgresql://anveshak:pass@postgres:5432/anveshak_test" alembic upgrade head'
```
