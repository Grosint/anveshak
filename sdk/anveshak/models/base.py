"""Base models shared across all Anveshak services."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime, UTC
import uuid


class Labels(BaseModel):
    """Mandatory classification metadata on every Anveshak model.

    Never Optional. Every model must carry this.
    """
    model_config = ConfigDict(strict=True)

    classification: str = "OPEN"          # OPEN | RESTRICTED | CONFIDENTIAL | SECRET
    domain: str = "osint"                  # osint | social | web | vision | report
    owner_org: str = "anveshak"
    source_id: Optional[str] = None       # adapter_id that produced this record
    topic_id: Optional[str] = None        # associated topic UUID


class AuditedModel(BaseModel):
    """Base for all DB-backed models — includes created_at, updated_at, labels."""
    model_config = ConfigDict(strict=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    labels: Labels  # NEVER Optional — enforced by CLAUDE.md rule 2
