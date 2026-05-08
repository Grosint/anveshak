"""ContentItem model — a scraped/ingested piece of open-source content."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime, UTC
import uuid
from .base import Labels, AuditedModel


class ExtractedEntity(BaseModel):
    """An NLP-extracted entity from a content item."""
    model_config = ConfigDict(strict=True)

    entity_type: str                       # PERSON|ORG|LOCATION|FACILITY|DATE|EVENT
    entity_text: str
    confidence: float = 1.0
    language: str = "en"


class ContentItem(AuditedModel):
    """A single piece of ingested open-source content.

    content_hash is the deduplication key — SHA-256 of normalised clean_text.
    Inserts use ON CONFLICT(content_hash) DO NOTHING.
    """
    topic_id: Optional[str] = None        # associated topic (set after backfill)
    source_id: str
    raw_text: str
    clean_text: str                        # trafilatura-extracted clean text
    language: str = "en"                  # detected language code
    content_hash: str                     # SHA-256 of normalised clean_text — MANDATORY
    url: Optional[str] = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    credibility_score_at_capture: float = 50.0
    extracted_entities: list[ExtractedEntity] = Field(default_factory=list)
    # Translation — populated by analyst service for non-English content
    translated_text: Optional[str] = None       # English translation of clean_text (None if original is English)
    translation_model: Optional[str] = None     # model used for translation (audit trail)
    # embedding stored in PostgreSQL directly as vector — not in this model
