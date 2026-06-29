# ML Model Ops

6 instincts. Model packaging, inference, hardware independence.

## ONNX Hardware Independence

- Device from `settings.vision_device`, never hardcoded. Provider list: `["CUDAExecutionProvider", "CPUExecutionProvider"]` for cuda, `["CPUExecutionProvider"]` for cpu
  ONNX Runtime silently falls back down list — same code on laptop and prod
  GPU-only detectors (DIRE) raise `NotImplementedError` on CPU w/ clear message referencing hardware.md
  Hardware upgrade = env var change only: `VISION_DEVICE`, `YOLO_MODEL_SIZE`, `CLIP_MODEL_NAME`
  See: `learned/onnx-hardware-independence.md`

## Optimum ONNX Export Cleanup

- Partial `.onnx` file on crash passes idempotent `if exists: skip` — corrupt model, garbage predictions
  Wrap export in try/except, `unlink()` partial on failure so next run retries
  `save_pretrained()` always writes `model.onnx` — rename if settings expect different filename
  Dep: `optimum[onnxruntime,exporters]` — base `optimum` alone gives `ModuleNotFoundError`
  See: `learned/optimum-onnx-export-cleanup.md`

## spaCy Labels Are Abbreviated

- FAC not FACILITY, GPE not Country, NORP not Nationality, LOC not Location
  Verify against stored data before writing filters: `SELECT entity_type, COUNT(*) FROM extracted_entities GROUP BY entity_type`
  See: `learned/spacy-entity-type-naming.md`

## spaCy Models — Pip Package, Not Volume

- spaCy models = pip packages w/ dependencies. `spacy.load()` needs sys.path. Cannot use volumes.
  Bake at build time: `RUN python -m spacy download ${SPACY_EN_MODEL}`
  Contrast: YOLO/CLIP/ONNX = weight files → shared volume w/ init container
  Rule: pip package → Docker image. Weight file → volume.
  See: `learned/spacy-pip-models-bake-in-image.md`

## Volume-Mounted Models — Silent Zero Scores

- Volume starts empty on first deploy. Detector catches `FileNotFoundError` → returns 0.0 → stored as real result
  No crash, no user error — frontend shows "0% deepfake" as if legitimate
  Fix: `make download-models` target, health endpoint checks model existence, WARNING log on default score
  Volume persists across rebuilds — even `docker compose build` won't populate it
  See: `learned/volume-mounted-models-silent-failure.md`

## Ollama 500 on Large Prompts (CPU)

- HTTP 500 when prompt exceeds available memory. Large clusters (100+ items) fail consistently
  Mitigations: truncate context proportionally, good fallback labels (topic + template + entities), delay between batch calls
  For 100+ item clusters: sample 10 diverse items, not 10 most recent
  GPU deployment handles larger contexts reliably — update `OLLAMA_NUM_PARALLEL` in compose
  See: `learned/ollama-500-large-prompt-cpu.md`
