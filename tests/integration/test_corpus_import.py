"""Dated Backfill importer at the database seam - issue #45.

The importer's whole claim is that imported content is indistinguishable from
collected content, so the assertions are on the rows themselves: the content
hash, the labels, the organisation, Capture Time and Publication Time. A test
that only counted rows would pass against an importer that wrote its own SQL
and drifted from the ingest path.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from scripts.import_corpus import (
    CORPUS_ADAPTER_ID,
    SourceStateError,
    TopicAccessError,
    import_corpus,
    load_corpus,
)
from tests.conftest import TEST_ORG_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

FOUNDED = datetime(2026, 5, 16, 9, 30, tzinfo=UTC)
REACTION = datetime(2026, 5, 18, 4, 15, tzinfo=UTC)


@pytest.fixture
def corpus(tmp_path) -> tuple[Path, str]:
    """A three item corpus, unique per run so its hashes cannot pre-exist."""
    token = uuid.uuid4().hex[:8]
    outlet_a = f"https://outlet-a-{token}.example/feed"
    outlet_b = f"https://outlet-b-{token}.example/feed"
    lines = [
        {
            "url": f"https://outlet-a-{token}.example/2026/05/16/founded",
            "text": f"The movement was founded today at a public meeting. {token}",
            "language": "en",
            "published_at": "2026-05-16T09:30:00+00:00",
            "published_at_signal": "jsonld_date_published",
            "discovery": "archive_sitemap",
            "body_source": "publisher",
            "source": {"handle": outlet_a, "name": "Outlet A", "platform": "web"},
        },
        {
            "url": f"https://outlet-b-{token}.example/2026/05/18/reaction",
            "text": f"Opposition leaders reacted to the founding. {token}",
            "language": "en",
            "published_at": "2026-05-18T04:15:00+00:00",
            "published_at_signal": "url_path_date",
            "source": {"handle": outlet_b, "name": "Outlet B", "platform": "web"},
        },
        {
            "url": f"https://outlet-b-{token}.example/opinion/undated",
            "text": f"An undated opinion column about the movement. {token}",
            "source": {"handle": outlet_b, "name": "Outlet B", "platform": "web"},
        },
    ]
    path = tmp_path / "corpus.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path, token


@pytest.fixture
async def imported(db_pool, make_topic, corpus):
    """Import the corpus once, then remove the Sources it created."""
    path, token = corpus
    topic_id = await make_topic(name=f"Corpus Import {token}")
    arq_pool = AsyncMock()

    summary = await import_corpus(
        load_corpus(path),
        topic_id=topic_id,
        org_id=TEST_ORG_ID,
        pool=db_pool,
        arq_pool=arq_pool,
    )

    yield topic_id, summary, arq_pool, path, token

    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM org_sources WHERE source_id IN "
            "(SELECT id FROM sources WHERE url_or_handle LIKE $1)",
            f"%{token}%",
        )
        await conn.execute(
            "DELETE FROM topic_sources WHERE source_id IN "
            "(SELECT id FROM sources WHERE url_or_handle LIKE $1)",
            f"%{token}%",
        )
        await conn.execute("DELETE FROM content_items WHERE topic_id = $1", topic_id)
        await conn.execute("DELETE FROM sources WHERE url_or_handle LIKE $1", f"%{token}%")


async def _rows(db_pool, topic_id) -> list:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM content_items WHERE topic_id = $1 ORDER BY url", topic_id
        )


class TestImportedRows:
    async def test_every_item_is_stored(self, db_pool, imported):
        topic_id, summary, _, _, _ = imported

        rows = await _rows(db_pool, topic_id)

        assert len(rows) == 3
        assert summary.imported == 3
        assert summary.duplicates == 0

    async def test_publication_time_is_the_corpus_value(self, db_pool, imported):
        topic_id, _, _, _, _ = imported

        rows = await _rows(db_pool, topic_id)
        published = {r["url"].rsplit("/", 1)[-1]: r["published_at"] for r in rows}

        assert published["founded"] == FOUNDED
        assert published["reaction"] == REACTION

    async def test_an_item_with_no_publication_time_is_stored_null(self, db_pool, imported):
        """Null, never a substitute: an unknown date stays unknown."""
        topic_id, summary, _, _, _ = imported

        rows = await _rows(db_pool, topic_id)
        undated = [r for r in rows if r["url"].endswith("undated")]

        assert len(undated) == 1
        assert undated[0]["published_at"] is None
        assert undated[0]["captured_at"] is not None
        assert summary.undated == 1

    async def test_capture_time_is_the_import_run(self, db_pool, imported):
        """Capture Time is when we loaded it, and says nothing about the story."""
        topic_id, _, _, _, _ = imported
        started = datetime.now(UTC)

        rows = await _rows(db_pool, topic_id)

        for row in rows:
            assert abs((started - row["captured_at"]).total_seconds()) < 300
            if row["published_at"] is not None:
                assert row["captured_at"] != row["published_at"]

    async def test_content_hash_is_the_normalised_text_hash(self, db_pool, imported):
        """Architectural rule 3, through the same path an adapter takes."""
        topic_id, _, _, _, _ = imported

        rows = await _rows(db_pool, topic_id)

        for row in rows:
            normalised = " ".join(row["raw_text"].lower().split())
            assert row["content_hash"] == hashlib.sha256(normalised.encode()).hexdigest()

    async def test_rows_carry_the_organisation(self, db_pool, imported):
        topic_id, _, _, _, _ = imported

        rows = await _rows(db_pool, topic_id)

        assert {r["org_id"] for r in rows} == {TEST_ORG_ID}

    async def test_labels_record_where_the_date_came_from(self, db_pool, imported):
        topic_id, _, _, _, _ = imported

        rows = await _rows(db_pool, topic_id)
        labels = {r["url"].rsplit("/", 1)[-1]: json.loads(r["labels"]) for r in rows}

        assert labels["founded"]["publication_time_signal"] == "jsonld_date_published"
        assert labels["reaction"]["publication_time_signal"] == "url_path_date"
        assert "publication_time_signal" not in labels["undated"]
        assert labels["founded"]["classification"] == "OPEN"
        assert labels["founded"]["source_id"] == CORPUS_ADAPTER_ID

    async def test_labels_record_how_the_item_was_found(self, db_pool, imported):
        """A sitemap date and a feed's assertion are not the same claim."""
        topic_id, _, _, _, _ = imported

        rows = await _rows(db_pool, topic_id)
        labels = {r["url"].rsplit("/", 1)[-1]: json.loads(r["labels"]) for r in rows}

        assert labels["founded"]["discovery"] == "archive_sitemap"
        assert labels["founded"]["body_source"] == "publisher"
        assert "discovery" not in labels["undated"]

    async def test_downstream_analysis_is_dispatched(self, db_pool, imported):
        """Same job, same queue as adapter-collected content."""
        topic_id, _, arq_pool, _, _ = imported

        rows = await _rows(db_pool, topic_id)
        enqueued = [c for c in arq_pool.enqueue_job.await_args_list]

        assert len(enqueued) == len(rows)
        assert {c.args[0] for c in enqueued} == {"analyse_content"}
        assert {c.kwargs["_queue_name"] for c in enqueued} == {"arq:analyst"}


class TestSources:
    async def test_each_outlet_becomes_one_source(self, db_pool, imported):
        _, summary, _, _, token = imported

        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM sources WHERE url_or_handle LIKE $1", f"%{token}%"
            )

        assert count == 2
        assert summary.sources_created == 2

    async def test_sources_are_linked_to_the_topic_and_the_organisation(self, db_pool, imported):
        topic_id, _, _, _, token = imported

        async with db_pool.acquire() as conn:
            linked = await conn.fetchval(
                """
                SELECT COUNT(*) FROM sources s
                JOIN topic_sources ts ON ts.source_id = s.id AND ts.topic_id = $1
                JOIN org_sources os ON os.source_id = s.id AND os.org_id = $2
                WHERE s.url_or_handle LIKE $3
                """,
                topic_id,
                TEST_ORG_ID,
                f"%{token}%",
            )

        assert linked == 2

    async def test_an_undated_item_still_counts_as_a_source(self, db_pool, imported):
        """It cannot sit on a timeline, but it still contributes a Source."""
        topic_id, _, _, _, _ = imported

        async with db_pool.acquire() as conn:
            sources = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT source_id) FROM content_items
                WHERE topic_id = $1 AND published_at IS NULL
                """,
                topic_id,
            )

        assert sources == 1


class TestRerun:
    async def test_a_second_run_inserts_nothing(self, db_pool, imported):
        """Idempotent by the existing content hash rule, not by a flag."""
        topic_id, _, _, path, _ = imported

        before = await _rows(db_pool, topic_id)
        summary = await import_corpus(
            load_corpus(path),
            topic_id=topic_id,
            org_id=TEST_ORG_ID,
            pool=db_pool,
            arq_pool=AsyncMock(),
        )
        after = await _rows(db_pool, topic_id)

        assert len(after) == len(before)
        assert summary.imported == 0
        assert summary.duplicates == 3

    async def test_a_second_run_creates_no_extra_sources(self, db_pool, imported):
        topic_id, _, _, path, token = imported

        summary = await import_corpus(
            load_corpus(path),
            topic_id=topic_id,
            org_id=TEST_ORG_ID,
            pool=db_pool,
            arq_pool=AsyncMock(),
        )

        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM sources WHERE url_or_handle LIKE $1", f"%{token}%"
            )

        assert count == 2
        assert summary.sources_created == 0

    async def test_a_second_run_dispatches_no_jobs(self, db_pool, imported):
        """A duplicate is not re-analysed, so a Replay does not multiply work."""
        topic_id, _, _, path, _ = imported
        arq_pool = AsyncMock()

        await import_corpus(
            load_corpus(path),
            topic_id=topic_id,
            org_id=TEST_ORG_ID,
            pool=db_pool,
            arq_pool=arq_pool,
        )

        assert arq_pool.enqueue_job.await_count == 0


class TestOrganisationScoping:
    async def test_it_refuses_a_topic_another_organisation_owns(self, db_pool, make_topic, corpus):
        """A wrong pair here writes rows one organisation reads inside another's Topic."""
        path, _ = corpus
        topic_id = await make_topic(name="Corpus Import Foreign Topic")

        with pytest.raises(TopicAccessError):
            await import_corpus(
                load_corpus(path),
                topic_id=topic_id,
                org_id="org-somebody-else",
                pool=db_pool,
                arq_pool=AsyncMock(),
            )

        async with db_pool.acquire() as conn:
            rows = await conn.fetchval(
                "SELECT COUNT(*) FROM content_items WHERE topic_id = $1", topic_id
            )
        assert rows == 0


class TestLossIsNotReportedAsDedup:
    async def test_a_deactivated_source_stops_the_run(self, db_pool, make_topic, corpus):
        """The ingest path skips a deactivated Source, so every item would
        report as already present and nothing would be imported."""
        path, token = corpus
        topic_id = await make_topic(name=f"Corpus Import Inactive {token}")
        items = load_corpus(path)

        async with db_pool.acquire() as conn:
            source_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO sources (
                    id, name, url_or_handle, platform, credibility_score,
                    is_active, org_id, created_at, updated_at, labels
                ) VALUES ($1, $2, $3, 'web', 50.0, FALSE, $4, NOW(), NOW(),
                          '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}')
                """,
                source_id,
                "Outlet A",
                items[0].source.handle,
                TEST_ORG_ID,
            )

        try:
            with pytest.raises(SourceStateError):
                await import_corpus(
                    items,
                    topic_id=topic_id,
                    org_id=TEST_ORG_ID,
                    pool=db_pool,
                    arq_pool=AsyncMock(),
                )
        finally:
            async with db_pool.acquire() as conn:
                await conn.execute("DELETE FROM org_sources WHERE source_id = $1", source_id)
                await conn.execute("DELETE FROM topic_sources WHERE source_id = $1", source_id)
                await conn.execute("DELETE FROM sources WHERE id = $1", source_id)

    async def test_an_item_held_by_another_topic_counts_as_missing(
        self, db_pool, make_topic, imported
    ):
        """The dedup key is global, so a second Topic gets no row for it.

        Counting it as a duplicate would tell the operator the content is there
        when the Topic they imported into holds none of it.
        """
        _, _, _, path, token = imported
        second_topic = await make_topic(name=f"Corpus Import Second {token}")

        summary = await import_corpus(
            load_corpus(path),
            topic_id=second_topic,
            org_id=TEST_ORG_ID,
            pool=db_pool,
            arq_pool=AsyncMock(),
        )

        assert summary.imported == 0
        assert summary.duplicates == 0
        assert summary.missing == 3
