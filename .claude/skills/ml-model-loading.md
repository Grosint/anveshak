# ML Model Loading

## When to load: any task involving ML model initialization, Dockerfile changes, or vision/analyst service code

Consolidated from 4 learned instincts.

---

### pip packages vs weight files

| Model type | Install method | Where | Example |
|------------|---------------|-------|---------|
| spaCy | pip package | Bake into Docker image | `RUN python -m spacy download en_core_web_md` |
| YOLO | .pt weight file | Volume via init container | `urllib.request.urlretrieve(url, target)` |
| CLIP | HuggingFace | Volume via HF_HOME | `CLIPModel.from_pretrained(name)` |
| ONNX | exported file | Volume via init container | `torch.onnx.export(model, ...)` |

**Rule:** If it's a pip package with dependencies → bake into image.
If it's a weight file → download to shared volume via init container.
See: `learned/spacy-pip-models-bake-in-image.md`

### Singleton pattern for ARQ workers

Load models ONCE per worker process at startup, never per-request:

```python
_encoder = None

def load_encoder() -> None:
    global _encoder
    _encoder = SentenceTransformer(settings.embedding_model)

def encode_text(text: str) -> list[float]:
    if _encoder is None:
        raise RuntimeError("call load_encoder() at startup")
    return _encoder.encode(text).tolist()
```

See: `learned/arq-worker-ml-singleton.md`

### Hardware independence via ONNX providers

```python
def onnx_providers(self) -> list[str]:
    if self.device == "cuda":
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]
```

Zero code changes when upgrading CPU → GPU. See: `learned/onnx-hardware-independence.md`

### Health checks for volume-mounted models

Empty volume = silent 0.0 scores. Always:
1. Init container downloads models before worker starts
2. Worker validates models at startup (fail-fast)
3. Health endpoint reports model status

See: `learned/volume-mounted-models-silent-failure.md`
