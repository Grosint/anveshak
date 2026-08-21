"""One-time: Generate executive summaries for all clusters via OpenAI.

For development/demo only — production uses local Ollama (qwen2:72b).
Public news content only — no classified data sent to cloud.

Usage:
    OPENAI_API_KEY=sk-... uv run python scripts/regen_summaries_openai.py
"""

from __future__ import annotations

import asyncio
import json
import os

import asyncpg
import structlog
from openai import AsyncOpenAI

log = structlog.get_logger(__name__)

SQL_ALL_CLUSTERS = """
    SELECT nc.id, nc.label, nc.item_count, nc.executive_summary
    FROM narrative_clusters nc
    ORDER BY nc.item_count DESC
"""

SQL_CLUSTER_TEXTS = """
    SELECT LEFT(ci.clean_text, 500) AS clean_text
    FROM content_items ci
    WHERE ci.narrative_cluster_id = $1
      AND COALESCE(ci.content_quality, 'good') != 'low_quality'
      AND ci.clean_text IS NOT NULL
      AND LENGTH(ci.clean_text) > 50
    ORDER BY ci.captured_at DESC
    LIMIT 8
"""

SQL_UPDATE = """
    UPDATE narrative_clusters
    SET label = $1,
        executive_summary = $2,
        label_generated_at = NOW(),
        label_item_hash = 'openai-generated',
        updated_at = NOW()
    WHERE id = $3
"""

SYSTEM_PROMPT = (
    "You are an intelligence analyst writing for military and law enforcement decision-makers. "
    "You will receive excerpts from news articles and social media posts that belong to "
    "a single narrative cluster (they discuss a related theme).\n\n"
    "Produce a JSON response with:\n"
    '1. "label": A concise headline (5-12 words) capturing the narrative theme.\n'
    '2. "summary": An executive summary (2-4 sentences) for a security briefing. '
    "State: what is happening, which countries/organisations/actors are involved, "
    "and why it matters for defence/security. Be specific — name entities.\n"
    '3. "confidence": float 0.0-1.0 indicating how well the excerpts support a coherent narrative.\n\n'
    "Rules:\n"
    "- Only use facts present in the provided excerpts.\n"
    "- If excerpts are mostly navigation garbage or boilerplate, set confidence < 0.3 "
    "and write a brief label from whatever real content exists.\n"
    "- Do not speculate or infer beyond what the text says.\n\n"
    'Respond with valid JSON only: {"label": "...", "summary": "...", "confidence": 0.0}'
)

BOUNDARY = "===CONTEXT==="


async def generate_summary(client: AsyncOpenAI, texts: list[str]) -> dict:
    excerpts = "\n\n---\n\n".join(t[:400] for t in texts)[:4000]
    user_msg = f"{BOUNDARY}\n{excerpts}\n{BOUNDARY}"

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=300,
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content
    return json.loads(raw)


async def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: Set OPENAI_API_KEY environment variable")
        return

    postgres_url = os.environ.get(
        "POSTGRES_URL",
        "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak",
    )

    client = AsyncOpenAI(api_key=api_key)
    pool = await asyncpg.create_pool(postgres_url, min_size=2, max_size=5)

    async with pool.acquire() as conn:
        clusters = await conn.fetch(SQL_ALL_CLUSTERS)

    log.info("regen.start", total_clusters=len(clusters))

    generated = 0
    skipped = 0
    failed = 0

    for row in clusters:
        cluster_id = row["id"]

        # Fetch sample texts
        async with pool.acquire() as conn:
            text_rows = await conn.fetch(SQL_CLUSTER_TEXTS, cluster_id)

        texts = [r["clean_text"] for r in text_rows if r["clean_text"]]

        if not texts:
            skipped += 1
            log.info("regen.no_texts", cluster_id=cluster_id, label=row["label"])
            continue

        try:
            result = generate_summary(client, texts)
            result = await result

            label = result.get("label", row["label"])
            summary = result.get("summary", "")
            confidence = result.get("confidence", 0.0)

            if confidence < 0.3:
                log.info(
                    "regen.low_confidence",
                    cluster_id=cluster_id,
                    label=label,
                    confidence=confidence,
                )

            async with pool.acquire() as conn:
                await conn.execute(SQL_UPDATE, label, summary, cluster_id)

            generated += 1
            log.info(
                "regen.success",
                cluster_id=cluster_id,
                label=label,
                summary=summary[:80],
                confidence=confidence,
                items=len(texts),
            )

        except Exception as exc:
            failed += 1
            log.warning("regen.failed", cluster_id=cluster_id, error=str(exc))

    await pool.close()
    log.info("regen.done", generated=generated, skipped=skipped, failed=failed)


if __name__ == "__main__":
    asyncio.run(main())
