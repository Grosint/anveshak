"""Social platform adapter registry."""

from .base import (
    AdapterAuthError,
    AdapterDegradedError,
    AdapterRateLimitError,
    RawItem,
    SourceAdapterBase,
)
from .whatsapp import WhatsAppAdapter
from .youtube_adapter import YouTubeAdapter

__all__ = [
    "SourceAdapterBase",
    "RawItem",
    "AdapterAuthError",
    "AdapterRateLimitError",
    "AdapterDegradedError",
    "YouTubeAdapter",
    "WhatsAppAdapter",
]
