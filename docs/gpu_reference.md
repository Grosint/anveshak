# GPU & LLM Reference Guide

## GPU Comparison — Cloud/Server

| | **T4** | **L4** | **A10** | **A100** |
|---|--------|--------|---------|----------|
| Generation | Turing (2018) | Ada Lovelace (2023) | Ampere (2021) | Ampere (2020) |
| VRAM | 16 GB | 24 GB | 24 GB | 40/80 GB |
| FP16 TFLOPS | 65 | 121 | 125 | 312 |
| Power draw | 70W | 72W | 150W | 300W |
| Form factor | Single slot | Single slot | Dual slot | SXM/PCIe |
| Cloud cost | Cheapest | ~1.5x T4 | ~2x T4 | ~5x T4 |
| Best for | Budget inference | Sweet spot | Heavy compute | Training/huge models |

## GPU Comparison — Consumer (for appliance builds)

| | **RTX 4060 Ti 16GB** | **RTX 4070 Ti Super** | **RTX 4090** |
|---|---------------------|----------------------|-------------|
| VRAM | 16 GB | 16 GB | 24 GB |
| FP16 TFLOPS | ~44 | ~93 | ~165 |
| Power draw | 165W | 285W | 450W |
| Street price (India) | ~₹45K | ~₹70K | ~₹1.8L |
| Equivalent to | ~T4 | ~L4 (compute) | ~L4+ (VRAM) |

Consumer GPUs lack ECC memory and server features but deliver equivalent ML inference.

## Key Concepts

### VRAM (Video RAM)

GPU's own dedicated memory. Models must be loaded into VRAM for GPU inference.
System RAM (32/64GB) is separate — irrelevant for GPU inference speed.
Model doesn't fit in VRAM → falls back to CPU (10x slower) or fails.

Exception: NVIDIA Jetson uses unified memory (CPU + GPU share same pool).

### TFLOPS (Trillion Floating-Point Operations Per Second)

Measure of raw GPU compute speed. Higher = faster inference.
Analogy: horsepower for math. More TFLOPS = more matrix multiplications per second.

Practical impact on Anveshak:
```
T4  (65 TFLOPS):  qwen2.5:14b → ~20 tokens/sec → ~25 sec per report BLUF
L4 (121 TFLOPS):  qwen2.5:14b → ~40 tokens/sec → ~12 sec per report BLUF
```

### Precision (FP32 / FP16 / INT8)

| Precision | Bits per number | Use | Speed |
|-----------|----------------|-----|-------|
| FP32 | 32 | Training | Baseline |
| FP16 | 16 | Inference | ~2x faster |
| INT8 | 8 | Quantized inference | ~4x faster |
| INT4 | 4 | Heavily quantized | ~8x faster |

All Anveshak models run FP16 or lower. Quality nearly identical to FP32 for inference.

### Quantization

Compresses model weights from full precision to fewer bits. Reduces VRAM, minor quality loss.

| Quantization | Bits/param | 70B model size | Quality loss |
|-------------|-----------|----------------|-------------|
| FP16 (full) | 16 | ~140 GB | None |
| Q8 | 8 | ~70 GB | Negligible |
| Q4_K_M | 4 | ~40 GB | Small |
| Q2 | 2 | ~20 GB | Noticeable |

When Ollama shows `qwen2.5:14b` = 9GB, that's Q4 quantized. Full FP16 = ~28GB.

### Multi-GPU Scaling

**Tensor Parallelism:** Split model layers across GPUs. Each GPU holds a slice.
```
GPU 0 (24GB): Layers 0-39
GPU 1 (24GB): Layers 40-79
= 48GB total, runs 70B Q4
```
Ollama supports this natively. Needs fast inter-GPU link (NVLink or PCIe).

**CPU Offloading:** Some layers in VRAM, rest in system RAM. Automatic in Ollama.
Works but 3-5x slower than full GPU. Happens when model > VRAM.

### PCIe vs SXM

How GPU connects to motherboard.
- PCIe: standard slot, cloud VMs and workstations. Sufficient for single-GPU inference.
- SXM: server-grade socket, faster bandwidth, multi-GPU interconnect. Overkill for Anveshak.

### Dedicated vs Shared GPU (vGPU/MIG)

- Dedicated: full GPU, all VRAM yours. Required for Anveshak.
- Shared (vGPU): fraction of GPU, unpredictable latency, VRAM slice may not fit models.
- MIG (Multi-Instance GPU): A100/H100 feature, hardware-partitioned. Only useful for very large GPUs.

Always ask cloud provider: "Is the GPU dedicated or shared?"

## Ollama Model Upgrade Path

### Qwen Family (recommended for Anveshak)

| Model | Download | VRAM | Quality | Notes |
|-------|----------|------|---------|-------|
| `qwen2.5:7b` | 4.7 GB | ~6 GB | Good | CPU fallback |
| `qwen2.5:14b` | 9 GB | ~10 GB | Great | Current production |
| `qwen3:8b` | 5 GB | ~7 GB | Great | Thinking mode, newer |
| `qwen3:14b` | 9 GB | ~11 GB | Excellent | Recommended T4 upgrade |
| `qwen3:32b` | 20 GB | ~22 GB | Outstanding | Recommended L4 upgrade |
| `qwen3:72b` | 43 GB | ~48 GB | Best | Needs 2x GPU or A100 |

### Other Options

| Model | VRAM | Strength |
|-------|------|----------|
| `llama3.1:8b` | ~6 GB | Well-tested, general purpose |
| `gemma3:12b` | ~10 GB | Good multilingual (Google) |
| `gemma3:27b` | ~20 GB | Strong reasoning |
| `mistral-small:24b` | ~16 GB | Fast structured output |
| `phi4:14b` | ~10 GB | Strong reasoning (Microsoft) |
| `command-r:35b` | ~22 GB | Built for RAG (Cohere) |
| `deepseek-r1:14b` | ~10 GB | Reasoning-focused |

### Qwen 2.5 vs Qwen 3

Qwen 3 (April 2025):
- "Thinking mode" — reasons step-by-step before answering
- Better structured JSON output
- Better multilingual support
- Same VRAM as equivalent Qwen 2.5 size

### Model Selection by GPU

| GPU | VRAM | Best Ollama Model | Remaining for Vision |
|-----|------|--------------------|---------------------|
| CPU only | N/A | `qwen3:8b` (in RAM) | N/A |
| RTX 4060 Ti / T4 | 16 GB | `qwen3:14b` (~11 GB) | ~5 GB |
| RTX 4090 / L4 | 24 GB | `qwen3:32b` (~22 GB) | ~2 GB (tight) |
| RTX 4090 / L4 | 24 GB | `qwen3:14b` (~11 GB) | ~13 GB (comfortable) |
| A100 | 40/80 GB | `qwen3:72b` (~48 GB) | Plenty |

### Upgrade Command

```bash
docker compose -p anveshak exec ollama ollama pull qwen3:32b
# Update .env: OLLAMA_MODEL=qwen3:32b
# Restart: docker compose -p anveshak restart
```

No code changes — OLLAMA_MODEL env var drives everything.

## Anveshak VRAM Budget

| Model | VRAM | Always loaded? |
|-------|------|---------------|
| Ollama (LLM) | 6-22 GB | Yes (keep-alive) |
| YOLOv8 | ~0.5 GB | On demand |
| CLIP | ~0.5 GB | On demand |
| DIRE (deepfake) | ~0.3 GB | On demand |
| sentence-transformers | ~0.5 GB | Yes (analyst worker) |
| **Total (with qwen3:14b)** | **~13 GB** | Fits T4 |
| **Total (with qwen3:32b)** | **~24 GB** | Fits L4 (tight) |

Vision models burst fast (50-100ms per image), release VRAM quickly.
Ollama holds VRAM persistently but only generates on report requests.
Simultaneous contention window is small in practice.
