"""Seed a Watch Space and its sources from a YAML definition.

Idempotent: reruns match on Topic name and source url_or_handle, so the
script can be run against a database that already has some of the rows.

    uv run python scripts/seed_watch_space.py \
        infra/configs/watch_spaces/internal_security_tension.yaml

Sources are global entities linked to an organisation through org_sources
and to the Watch Space through topic_sources, matching the existing source
visibility model. A source another organisation already registered is
reused rather than duplicated.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import yaml


def _labels_json(org_id: str) -> str:
    """Classification labels for a seeded row.

    owner_org tracks the org_id the row is actually written with. Pinning it
    to a constant made the label disagree with the row for every org except
    the default, so a classification-based check attributed the Watch Space
    to the wrong organisation.
    """
    return json.dumps({"classification": "OPEN", "domain": "osint", "owner_org": org_id})


SQL_FIND_TOPIC = "SELECT id FROM topics WHERE name = $1 AND org_id = $2"

SQL_INSERT_TOPIC = """
    INSERT INTO topics (
        id, name, keywords, languages, credibility_min, signal_threshold,
        status, org_id, is_watch_space, created_at, updated_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE, $9, $9, $10::jsonb)
"""

SQL_UPDATE_TOPIC = """
    UPDATE topics
    SET keywords = $2, languages = $3, credibility_min = $4,
        signal_threshold = $5, status = $6, is_watch_space = TRUE,
        updated_at = $7
    WHERE id = $1 AND org_id = $8
"""

SQL_FIND_SOURCE = "SELECT id FROM sources WHERE url_or_handle = $1 AND platform = $2"

SQL_INSERT_SOURCE = """
    INSERT INTO sources (
        id, name, url_or_handle, platform, credibility_score,
        auto_score_enabled, is_active, org_id, created_at, updated_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, TRUE, TRUE, $6, $7, $7, $8::jsonb)
"""

SQL_LINK_ORG_SOURCE = """
    INSERT INTO org_sources (org_id, source_id)
    VALUES ($1, $2)
    ON CONFLICT DO NOTHING
"""

SQL_LINK_TOPIC_SOURCE = """
    INSERT INTO topic_sources (topic_id, source_id)
    VALUES ($1, $2)
    ON CONFLICT DO NOTHING
"""


async def _upsert_topic(conn: asyncpg.Connection, spec: dict[str, Any], org_id: str) -> str:
    now = datetime.now(UTC)
    existing = await conn.fetchrow(SQL_FIND_TOPIC, spec["name"], org_id)

    if existing:
        await conn.execute(
            SQL_UPDATE_TOPIC,
            existing["id"],
            spec["keywords"],
            spec.get("languages", ["en"]),
            float(spec.get("credibility_min", 30.0)),
            int(spec.get("signal_threshold", 3)),
            spec.get("status", "active"),
            now,
            org_id,
        )
        print(f"  [=] Watch Space already present, refreshed: {spec['name']}")
        return existing["id"]

    topic_id = str(uuid.uuid4())
    await conn.execute(
        SQL_INSERT_TOPIC,
        topic_id,
        spec["name"],
        spec["keywords"],
        spec.get("languages", ["en"]),
        float(spec.get("credibility_min", 30.0)),
        int(spec.get("signal_threshold", 3)),
        spec.get("status", "active"),
        org_id,
        now,
        _labels_json(org_id),
    )
    print(f"  [+] Watch Space created: {spec['name']}")
    return topic_id


async def _upsert_source(conn: asyncpg.Connection, source: dict[str, Any], org_id: str) -> str:
    """Return the source id, creating the global source row if needed."""
    existing = await conn.fetchrow(SQL_FIND_SOURCE, source["url_or_handle"], source["platform"])
    if existing:
        return existing["id"]

    source_id = str(uuid.uuid4())
    await conn.execute(
        SQL_INSERT_SOURCE,
        source_id,
        source["name"],
        source["url_or_handle"],
        source["platform"],
        float(source.get("credibility_score", 50.0)),
        org_id,
        datetime.now(UTC),
        _labels_json(org_id),
    )
    return source_id


async def seed(spec_path: Path, postgres_url: str, org_id: str) -> None:
    spec = yaml.safe_load(spec_path.read_text())

    if not spec.get("is_watch_space"):
        raise SystemExit(f"{spec_path} is not marked is_watch_space: true")

    conn = await asyncpg.connect(postgres_url)
    try:
        async with conn.transaction():
            topic_id = await _upsert_topic(conn, spec, org_id)

            linked = 0
            for source in spec.get("sources", []):
                source_id = await _upsert_source(conn, source, org_id)
                await conn.execute(SQL_LINK_ORG_SOURCE, org_id, source_id)
                await conn.execute(SQL_LINK_TOPIC_SOURCE, topic_id, source_id)
                linked += 1

        print(f"  [+] {linked} sources linked to the Watch Space")
        print(f"  [+] topic_id={topic_id}")
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Watch Space YAML definition")
    parser.add_argument(
        "--org-id",
        default=os.getenv("SEED_ORG_ID", "org-default"),
        help="Organisation that owns the Watch Space",
    )
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("POSTGRES_URL", ""),
        help="Defaults to POSTGRES_URL. No credential default is built in.",
    )
    args = parser.parse_args()

    if not args.spec.exists():
        print(f"No such spec: {args.spec}", file=sys.stderr)
        return 1

    if not args.postgres_url:
        print(
            "Set POSTGRES_URL or pass --postgres-url. This script ships no "
            "credential default, so it cannot silently target a database "
            "nobody named.",
            file=sys.stderr,
        )
        return 1

    asyncio.run(seed(args.spec, args.postgres_url, args.org_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
