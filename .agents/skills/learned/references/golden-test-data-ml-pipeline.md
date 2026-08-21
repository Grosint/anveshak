# Golden Test Data for ML Pipeline Validation

## Problem

Unit tests mock ML models (NLLB, spaCy, sentence-transformers), so they can't
catch quality issues: bad translations, missing entities, wrong embeddings.
Integration tests use English-only content, so the multilingual pipeline is untested.

## Solution: Golden Test Data with Known Expected Outputs

Write test content in each supported language with **pre-decided expected outputs**.
Run through real models inside the container. Assert key terms survive the chain.

### Pattern

```python
NARRATIVE_A = {
    "en": {
        "text": "China deploys Wing Loong III UAV near Hotan airbase...",
        "lang": "en",
        "expected_entities": ["China", "Hotan", "PLA"],
    },
    "zh": {
        "text": "中国已在新疆和田空军基地附近部署翼龙III无人机...",
        "lang": "zh",
        "translation_keywords": ["China", "UAV", "drone", "PLA", "Xinjiang"],
    },
}
```

### Fuzzy Matching (critical)

NLLB translation is non-deterministic and imperfect. Never assert exact strings.
Use fuzzy keyword matching with a minimum threshold:

```python
def _fuzzy_match(text, keywords, min_matches):
    found = [kw for kw in keywords if kw.lower() in text.lower()]
    return len(found) >= min_matches, found, missing
```

Require 3 out of 5 keywords, not 5/5. Translation may paraphrase "UAV" as
"unmanned aircraft" or miss a proper noun.

### Cross-Language Clustering Validation

Seed 2+ distinct narratives across languages. Assert:
- **Intra-narrative similarity > 0.5** (same story, different languages)
- **Inter-narrative similarity < intra** (different stories separate)

Don't assert exact cluster membership — too brittle. Cosine similarity
thresholds are more robust to model version changes.

### Where Tests Run

Inside the container (`docker compose exec analyst-worker python /tmp/test.py`)
where real models are loaded. NOT on the host (models may not be installed).

## Files
- `scripts/test_multilingual_pipeline.py` — 7-test validation suite
- `scripts/test_analyst_models.py` — existing English-only model tests (same pattern)
