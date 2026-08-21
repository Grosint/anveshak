"""Drishti bridge emitter — emits extracted entities as source.envelopes.v1."""

import hashlib
import json
import os
from datetime import UTC, datetime

import structlog

log = structlog.get_logger(__name__)


class BridgeDisabledError(Exception):
    pass


class DrishtiBridgeEmitter:
    """Emits Anveshak-extracted entities into Drishti's ingestion pipeline.

    Only active when ANVESHAK_DRISHTI_BRIDGE=true AND DRISHTI_REDPANDA_BOOTSTRAP is set.
    Conforms to Drishti's RawRecord + source.envelopes.v1 contract.
    """

    SOURCE_ID = "anveshak-v1"
    TOPIC = "source.envelopes.v1"

    def __init__(self) -> None:
        self._enabled = os.getenv("ANVESHAK_DRISHTI_BRIDGE", "false").lower() == "true"
        self._bootstrap = os.getenv("DRISHTI_REDPANDA_BOOTSTRAP", "")
        self._producer = None

        if self._enabled and not self._bootstrap:
            raise ValueError(
                "ANVESHAK_DRISHTI_BRIDGE=true but DRISHTI_REDPANDA_BOOTSTRAP is not set"
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def start(self) -> None:
        if not self._enabled:
            return
        try:
            # aiokafka is a container-only dependency, absent from the host venv.
            from aiokafka import (  # pyright: ignore[reportMissingImports]
                AIOKafkaProducer,
            )

            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap,
                value_serializer=lambda v: json.dumps(v).encode(),
            )
            await self._producer.start()
            log.info("drishti_bridge.started", bootstrap=self._bootstrap)
        except Exception as e:
            log.error("drishti_bridge.start_failed", error=str(e))
            raise

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()

    async def emit_entity(
        self, entity_text: str, entity_type: str, topic_name: str, source_url: str
    ) -> None:
        """Emit an extracted entity as a Drishti-compatible RawRecord envelope."""
        if not self._enabled:
            raise BridgeDisabledError("Drishti bridge is disabled")

        payload = {
            "entity_text": entity_text,
            "entity_type": entity_type,
            "topic_name": topic_name,
            "source_url": source_url,
            "extracted_at": datetime.now(UTC).isoformat(),
        }
        raw_bytes = json.dumps(payload).encode()
        content_hash = hashlib.sha256(raw_bytes).hexdigest()

        envelope = {
            "source_id": self.SOURCE_ID,
            "schema_hint": "osint.entity.v1",
            "content_hash": content_hash,
            "raw_evidence_ref": f"evidence/anveshak-v1/{content_hash}.json",
            "capture_ts": datetime.now(UTC).isoformat(),
            "raw_payload": raw_bytes.hex(),
            "labels": {
                "classification": "OPEN",
                "domain": "osint",
                "owner_org": "anveshak",
                "source_id": self.SOURCE_ID,
            },
        }
        if self._producer is None:
            raise BridgeDisabledError("Drishti bridge producer not started - call start() first")
        await self._producer.send_and_wait(self.TOPIC, envelope)
        log.info(
            "drishti_bridge.emitted",
            entity=entity_text,
            entity_type=entity_type,
            content_hash=content_hash,
        )
