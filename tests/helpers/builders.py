"""Test data builders — fluent API for creating test objects.

Usage:
    item = ContentItemBuilder().with_text("Breaking news").with_source(sid).build()
    item_id = await ContentItemBuilder().with_text("News").insert(pool, topic_id, source_id)

Eliminates the 10+ line INSERT statements duplicated across integration tests.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


class ContentItemBuilder:
    """Builder for content_items test data."""

    def __init__(self) -> None:
        self._text = "Default test content for integration testing."
        self._language = "en"
        self._url: str | None = None
        self._embedding: list[float] | None = None
        self._cluster_id: str | None = None
        self._credibility: float = 75.0

    def with_text(self, text: str) -> ContentItemBuilder:
        self._text = text
        return self

    def with_language(self, lang: str) -> ContentItemBuilder:
        self._language = lang
        return self

    def with_url(self, url: str) -> ContentItemBuilder:
        self._url = url
        return self

    def with_embedding(self, embedding: list[float]) -> ContentItemBuilder:
        self._embedding = embedding
        return self

    def with_cluster(self, cluster_id: str) -> ContentItemBuilder:
        self._cluster_id = cluster_id
        return self

    def with_credibility(self, score: float) -> ContentItemBuilder:
        self._credibility = score
        return self

    def build(self) -> dict[str, Any]:
        """Return a dict suitable for parameterized tests or direct assertion."""
        item_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(self._text.lower().strip().encode()).hexdigest()
        return {
            "id": item_id,
            "raw_text": self._text,
            "clean_text": self._text,
            "language": self._language,
            "content_hash": content_hash,
            "url": self._url or f"https://example.com/test-{item_id[:8]}",
            "embedding": self._embedding,
            "narrative_cluster_id": self._cluster_id,
            "credibility_score_at_capture": self._credibility,
        }

    async def insert(self, pool, topic_id: str, source_id: str) -> str:
        """Insert into real database. Returns item_id."""
        data = self.build()
        now = datetime.now(UTC)

        async with pool.acquire() as conn:
            embedding_col = ""
            embedding_val = ""
            if data["embedding"] is not None:
                embedding_str = "[" + ",".join(f"{x:.8f}" for x in data["embedding"]) + "]"
                embedding_col = "embedding, "
                embedding_val = f"'{embedding_str}'::vector, "

            await conn.execute(
                f"""
                INSERT INTO content_items (
                    id, topic_id, source_id, raw_text, clean_text, language,
                    content_hash, url, captured_at, credibility_score_at_capture,
                    {embedding_col}narrative_cluster_id,
                    created_at, updated_at, labels
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,{embedding_val}$11,$12,$13,$14)
                ON CONFLICT(content_hash) DO NOTHING
                """,
                data["id"],
                topic_id,
                source_id,
                data["raw_text"],
                data["clean_text"],
                data["language"],
                data["content_hash"],
                data["url"],
                now,
                data["credibility_score_at_capture"],
                data["narrative_cluster_id"],
                now,
                now,
                LABELS_JSON,
            )
        return data["id"]


class SourceBuilder:
    """Builder for sources test data."""

    def __init__(self) -> None:
        self._name = "Test Source"
        self._platform = "web"
        self._url_or_handle: str | None = None
        self._score = 75.0

    def with_name(self, name: str) -> SourceBuilder:
        self._name = name
        return self

    def with_platform(self, platform: str) -> SourceBuilder:
        self._platform = platform
        return self

    def with_url(self, url: str) -> SourceBuilder:
        self._url_or_handle = url
        return self

    def with_score(self, score: float) -> SourceBuilder:
        self._score = score
        return self

    async def insert(self, pool) -> str:
        """Insert into real database. Returns source_id."""
        source_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        handle = self._url_or_handle or f"https://{source_id[:8]}.example.com"
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sources (
                    id, name, url_or_handle, platform, credibility_score,
                    created_at, updated_at, labels
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                source_id,
                self._name,
                handle,
                self._platform,
                self._score,
                now,
                now,
                LABELS_JSON,
            )
        return source_id


class TopicBuilder:
    """Builder for topics test data."""

    def __init__(self) -> None:
        self._name = "Test Topic"
        self._keywords: list[str] = ["test"]
        self._threshold = 2
        self._status = "active"

    def with_name(self, name: str) -> TopicBuilder:
        self._name = name
        return self

    def with_keywords(self, kw: list[str]) -> TopicBuilder:
        self._keywords = kw
        return self

    def with_threshold(self, t: int) -> TopicBuilder:
        self._threshold = t
        return self

    async def insert(self, pool) -> str:
        """Insert into real database. Returns topic_id."""
        topic_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO topics (id, name, keywords, signal_threshold, status,
                                    created_at, updated_at, labels)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                topic_id,
                self._name,
                self._keywords,
                self._threshold,
                self._status,
                now,
                now,
                LABELS_JSON,
            )
        return topic_id
