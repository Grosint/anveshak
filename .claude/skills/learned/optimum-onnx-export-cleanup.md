# Optimum ONNX Export — Partial File Cleanup

## When to load: downloading and exporting HuggingFace models to ONNX

---

## Pattern: clean up partial files on export failure

`optimum` downloads a PyTorch model from HuggingFace, then exports to ONNX via
`torch.onnx.export`. If the process crashes mid-export (network timeout, OOM,
disk full), a partial `.onnx` file may be left on disk.

The idempotent check (`if out_path.exists(): return`) then **skips re-download on
next run**, leaving a corrupt model that loads but produces garbage predictions —
or crashes with an opaque ONNX parsing error.

### Fix: wrap export in try/except, delete partial on failure

```python
try:
    ort_model = ORTModelForImageClassification.from_pretrained(hf_model, export=True)
    ort_model.save_pretrained(str(out_path.parent))
    exported = out_path.parent / "model.onnx"
    if exported.exists() and exported != out_path:
        exported.rename(out_path)
except Exception:
    if out_path.exists():
        out_path.unlink()  # remove partial so idempotent check retries next run
    raise
```

**Why:** The idempotent pattern (`if exists: skip`) is correct for the happy path
but creates a silent failure mode when combined with partial writes. The fix is
trivial but easy to forget.

---

## Pattern: optimum saves as `model.onnx`, not your filename

`ort_model.save_pretrained(directory)` always writes `model.onnx` in the target
directory. If your settings expect a different filename (e.g., `face_deepfake.onnx`),
you must rename after export:

```python
exported = out_path.parent / "model.onnx"
if exported.exists() and exported != out_path:
    exported.rename(out_path)
```

---

## Dependency: `optimum[onnxruntime,exporters]`

The base `optimum` package does NOT include `optimum.onnxruntime`. You need the
extras:
- `optimum[exporters]` — provides `torch.onnx.export` wrappers
- `optimum[onnxruntime]` — provides `ORTModelForImageClassification`

Install both: `pip install "optimum[onnxruntime,exporters]"`

Missing `[onnxruntime]` produces `ModuleNotFoundError: No module named 'optimum.onnxruntime'`
even though `import optimum` succeeds.
