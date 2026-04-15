"""Social platform adapter registry."""
from .base import (
    AdapterAuthError,
    AdapterDegradedError,
    AdapterRateLimitError,
    RawItem,
    SourceAdapterBase,
)

__all__ = [
    "SourceAdapterBase",
    "RawItem",
    "AdapterAuthError",
    "AdapterRateLimitError",
    "AdapterDegradedError",
]
