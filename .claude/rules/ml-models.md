# ML Models & Inference

Consolidated from 8 learned instincts. These apply to all ML model loading, inference, and testing.

## Model Packaging

- spaCy models are pip packages — bake into Docker image at build time
  (`python -m spacy download`). They need sys.path and have pip dependencies.
  Cannot use volumes.
  See: `learned/spacy-pip-models-bake-in-image.md`

- Vision models (YOLO, CLIP, ONNX weights) are binary files — use shared volumes
  with init containers. Downloaded at runtime, not baked into images.
  See: hardware.md for the full upgrade matrix

- Rule: if model is a pip package → bake into Docker image.
  If model is a weight file → use shared volume with init container.

## Hardware Independence

- Use ONNX Runtime's provider list for transparent CPU/CUDA support
  Device is determined from config (`settings.vision_device`), never hardcoded
  ONNX Runtime silently falls back down the provider list if CUDA isn't available
  GPU-only detectors raise `NotImplementedError` on CPU with clear error messages
  Hardware upgrades require only environment variable changes, no code modifications
  See: `learned/onnx-hardware-independence.md`

## HuggingFace Model Swaps

- Always verify `id2label` from the model's `config.json` before writing inference code
  Different models use different label orderings — index 0 can mean "fake" or "real"
  Use a named `FAKE_INDEX` constant, never bare `probs[1]`
  See: `learned/hf-model-label-order-verification.md`

- When exporting HF models to ONNX via `optimum`, clean up partial files on failure
  A partial `.onnx` file passes the idempotent `if exists: skip` check silently
  `optimum` needs `[onnxruntime,exporters]` extras — base package alone gives `ModuleNotFoundError`
  See: `learned/optimum-onnx-export-cleanup.md`

## LLM Output Validation

- All LLM responses are validated through Pydantic `strict=True` models (CLAUDE.md rule 9)
  Always include `labels: Labels` on LLM output schemas
  See: `learned/llm-validated-output-retry.md`

- Strip JSON markdown fences before parsing (LLMs almost always wrap JSON in ```json```)
  Parse with explicit error types to distinguish JSON errors from schema validation errors

- Progressive retry: tighten prompt on each failure by demanding "JSON only, no preamble"
  Caller treats `None` as hard failure — never stores partial output
  Embed exact JSON schema in every prompt so the model knows the target structure

## Clustering Algorithms

- Use Leiden community detection instead of HDBSCAN for narrative clustering
  HDBSCAN fails when all articles form a single narrative (no density gaps)
  Leiden has one parameter (threshold ~0.75), is deterministic, handles single-narrative case
  Dependencies: `leidenalg>=0.10`, `igraph>=0.11`
  See: `learned/leiden-graph-narrative-clustering.md`

- Incremental clustering: load only unclustered items, assign to existing centroids
  if similarity >= 0.75, run full Leiden only on unmatched items
  Update centroids with weighted average, then normalize
  See: `learned/incremental-clustering-centroid-assign.md`

- Entity MinHash blending: `(1 - weight) * cosine_sim + weight * entity_jaccard_sim`
  Default weight: 0.3 (70% embedding, 30% entity)
  Store MinHash as `BIGINT[]` in PostgreSQL, not `INTEGER[]` (values overflow int32)
  NULL-safe: only blend where BOTH items have minhash
  See: `learned/entity-minhash-clustering-boost.md`

## Testing ML Pipelines

- Test embeddings must be L2-normalized (sentence-transformers outputs unit vectors)
  Use seeded RNG, perturb base vectors with controlled noise
  Calibration: 0.02 noise (tight clusters), 0.03 (realistic), 0.05 (broad topics)
  See: `learned/test-embedding-realism.md`

- Golden test data: write content in supported languages with pre-decided expected outputs
  Use fuzzy keyword matching (3 out of 5, not 5/5) — NLLB translation is non-deterministic
  Run tests inside container where real models are loaded, not on host
  See: `learned/golden-test-data-ml-pipeline.md`
