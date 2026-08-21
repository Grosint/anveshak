# SDK Shared Utility — No DB/ARQ Dependencies

## When to load: adding a shared utility used by multiple services

---

## Pattern

Shared utilities in the SDK must be dependency-free: no asyncpg, no arq, no service-specific imports.
The caller (service code) handles DB persistence and ARQ enqueueing.

```python
# sdk/anveshak-sdk/src/anveshak/media/downloader.py
# ✅ Only stdlib + httpx + structlog — no asyncpg, no arq
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import asyncio, hashlib, httpx, structlog

@dataclass
class MediaDownloadResult:
    storage_path: str
    content_hash: str      # SHA-256 of raw bytes
    asset_type: str        # "image" | "video"
    size_bytes: int

async def download_media_asset(
    url: str,
    topic_id: str,
    storage_root: Path,
    max_size_mb: int = 50,
    timeout_s: int = 30,
) -> Optional[MediaDownloadResult]:
    """Download, deduplicate by hash, write to disk. Returns result or None."""
    ...
    # caller does: INSERT INTO media_assets ... (sdk knows nothing about this)
    # caller does: arq_pool.enqueue_job("run_vision_analysis", row["id"])
```

**Why:** If the SDK imported asyncpg, every service that uses it would need asyncpg installed.
The SDK is also used by the API service which may not have a direct DB connection.
Keeping the SDK dependency-free means it installs in seconds and works anywhere.

---

## Content hash = SHA-256 of raw bytes, not text

```python
content_hash = hashlib.sha256(data).hexdigest()  # data: bytes — raw file bytes
```

NOT: `hashlib.sha256(response.text.encode()).hexdigest()`

**Why:** For binary files (images, video), text encoding is undefined and lossy.
The hash must be computed on the exact bytes stored to disk to be meaningful for dedup.

---

## Storage path pattern

```python
date = datetime.now(UTC)
storage_path = storage_root / "media" / topic_id / f"{date.year}" / f"{date.month:02d}" / f"{date.day:02d}" / f"{content_hash}{ext}"
```

This is the canonical pattern across scraper, social, and vision services.
`topic_id` scopes the namespace. Date segments allow easy pruning of old media.

---

## What the caller is responsible for

After `download_media_asset()` returns:
1. `INSERT INTO media_assets (id, content_item_id, asset_type, storage_path, content_hash, labels) ... ON CONFLICT (content_hash) DO NOTHING`
2. `SELECT id FROM media_assets WHERE content_hash = $1`
3. `arq_pool.enqueue_job("run_vision_analysis", media_asset_id)`

The SDK never does any of these. Separation is intentional.
