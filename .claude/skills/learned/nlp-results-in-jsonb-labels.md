# NLP Results in JSONB Labels Column

## When to load: adding lightweight ML features (sentiment, keywords, metadata) without schema migration

---

## Pattern

Store NLP results in the existing `labels` JSONB column instead of adding new columns or tables.

```python
# Compute lightweight NLP features
sentiment = analyse_sentiment(work_text)      # VADER: ~0ms, rule-based
kw_results = extract_keywords(work_text)      # YAKE: ~5ms, statistical

# Pack into labels dict alongside existing metadata
labels_dict = {
    "classification": "OPEN",
    "domain": "osint",
    "owner_org": "anveshak",
    "sentiment": {
        "compound": sentiment.compound,
        "positive": sentiment.positive,
        "negative": sentiment.negative,
        "neutral": sentiment.neutral,
    },
    "keywords": [kw.keyword for kw in kw_results],
}

# Single UPDATE — no migration needed
UPDATE content_items SET labels = $1::jsonb WHERE id = $2
```

**Why:** Zero schema migration. Labels JSONB is already on every row (mandatory per CLAUDE.md). PostgreSQL JSONB supports indexed queries: `WHERE labels->'sentiment'->>'compound' > '0.5'`. Adding a GIN index on labels enables fast filtering.

**When NOT to use:** If you need to JOIN on the field, aggregate across millions of rows, or enforce NOT NULL — use a proper column. JSONB is for flexible, queryable metadata that varies per row.

---

## Companion: lazy singleton for ML models

```python
_analyzer = None

def analyse_sentiment(text: str) -> SentimentResult:
    global _analyzer
    if _analyzer is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _analyzer = SentimentIntensityAnalyzer()  # ~1MB, loads once
    scores = _analyzer.polarity_scores(text)
    return SentimentResult(**scores)
```

VADER and YAKE are pure Python, CPU-only, negligible memory. No GPU upgrade path needed.
