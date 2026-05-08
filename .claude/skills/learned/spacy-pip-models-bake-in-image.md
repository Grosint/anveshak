---
title: spaCy models are pip packages — bake into Docker image, not volume
created: 2026-05-08
---

## Problem

spaCy models (`en_core_web_md`, etc.) are Python packages with dependencies (pymorphy3 for Russian,
spacy-pkuseg for Chinese). They must be on `sys.path` to be loaded by `spacy.load()`.

Attempting `pip install --target /app/models/spacy/` creates nested directories and breaks
dependency resolution. The model installs but `spacy.load()` can't find it.

## Pattern

```dockerfile
# Dockerfile — bake spaCy models at build time
ARG SPACY_EN_MODEL=en_core_web_md
RUN python -m spacy download ${SPACY_EN_MODEL}
```

```python
# nlp.py — fail fast at startup
def load_models() -> None:
    import spacy
    try:
        _MODELS["en"] = spacy.load(settings.spacy_en_model)
    except OSError as exc:
        raise RuntimeError(f"spaCy model '{settings.spacy_en_model}' failed to load: {exc}")
```

## Contrast with vision models

| Model type | Install method | Can use volume? | Why |
|------------|---------------|-----------------|-----|
| spaCy | pip package | No | Needs sys.path, has pip dependencies |
| YOLO | .pt weight file | Yes | Just a binary file, any path works |
| CLIP | HF from_pretrained | Yes | Caches to HF_HOME directory |
| ONNX | exported file | Yes | Just a binary file, any path works |

## Key rule

If the model is a **pip package** → bake into Docker image.
If the model is a **weight file** → download to shared volume via init container.
