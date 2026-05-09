# Optional Dependency: Lazy Import with Two-Level Logging

## Pattern
Import heavy/optional dependencies in a try/except at module level. Log at INFO
when missing (feature disabled). Log at WARNING when the feature is actually invoked
without the dependency.

## Why
- Import-time crash kills the service on systems without the optional dep (e.g.,
  macOS dev without libpango for WeasyPrint, or scraper without PyMuPDF)
- Two-level logging: INFO at startup (operator sees which features are off),
  WARNING at runtime (if code path reaches the missing feature)
- `None` sentinel makes feature checks trivial: `if fitz is None: return None`

## Implementation
```python
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    log.info("pymupdf_not_installed", hint="pip install pymupdf to enable PDF extraction")

def extract_pdf_text(pdf_bytes: bytes) -> Optional[str]:
    if fitz is None:
        log.warning("pdf_extract_unavailable")  # level 2: runtime attempt
        return None
    # ... use fitz
```

## Pitfall
WeasyPrint's `HTML` class was already using this pattern (`pdf.py` line 17) but
the import was inside `generate_pdf()`. Both approaches work, but module-level
try/except is cleaner because the log message appears once at startup.

## Files
- `services/scraper/anveshak/scraper/pdf_extract.py` — PyMuPDF
- `services/reporter/anveshak/reporter/pdf.py` — WeasyPrint (lazy inside function)
