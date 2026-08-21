# HuggingFace Model Label Order Verification

## When to load: swapping or adding any HuggingFace image classification model

---

## Pattern: verify id2label before writing inference code

When using a HuggingFace image classification model, the `config.json` defines
which output index maps to which label. **Different models use different orderings:**

```
prithivMLmods/Deep-Fake-Detector-v2-Model:
  id2label: {0: "Realism", 1: "Deepfake"}  → FAKE_INDEX = 1

umm-maybe/AI-image-detector:
  id2label: {0: "artificial", 1: "human"}   → FAKE_INDEX = 0
```

**If you assume index 1 = fake for both, the second model scores real images as
fake and vice versa — with NO error message.** The scores look plausible (0.0–1.0
floats) but are inverted.

### Verification step (do this BEFORE writing detector code):

```bash
curl -sL https://huggingface.co/{org}/{model}/resolve/main/config.json | python3 -m json.tool | grep -A2 id2label
```

### Enforcement pattern:

```python
# In the detector module — document the verified label order
# Label ordering from HF model config.json: {0: "artificial", 1: "human"}
# Verified against umm-maybe/AI-image-detector config.
FAKE_INDEX = 0
```

Always use a named constant (`FAKE_INDEX`) — never a bare `probs[1]` or `probs[0]`.

**Why:** Two models that both accept `[1, 3, 224, 224]` and output `[1, 2]` logits
can have completely opposite label semantics. This is invisible at the interface
level — the ONNX contract is identical. Only `config.json` tells you which index
means what. Getting this wrong produces confident-looking but inverted predictions.

---

## Pitfall: gated/private HuggingFace repos

Some HF repos return 401 even though they appear public. We hit this with
`dima806/deepfake_vs_real_faces`. Always test download access inside the Docker
container (which has no HF token) before committing the model name to settings:

```bash
docker compose run --rm vision-init  # will fail if repo is gated
```

If a model is gated, find an alternative or set `HF_TOKEN` in compose environment.
