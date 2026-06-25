"""Social platform adapter registry."""
from .base import (
    AdapterAuthError,
    AdapterDegradedError,
    AdapterRateLimitError,
    RawItem,
    SourceAdapterBase,
)

from .youtube_adapter import YouTubeAdapter
from .whatsapp import WhatsAppAdapter

__all__ = [
    "SourceAdapterBase",
    "RawItem",
    "AdapterAuthError",
    "AdapterRateLimitError",
    "AdapterDegradedError",
    "YouTubeAdapter",
    "WhatsAppAdapter",
]
