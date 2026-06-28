# Ollama 500 Errors on Large Prompts (CPU)

## Pattern

Ollama returns HTTP 500 on CPU when prompt exceeds available memory. Large clusters (100+ items) with enriched prompts trigger this consistently.

## Observed

- 53 cluster regeneration: 19 LLM success, 33 HTTP 500 fallback
- Failures correlated with cluster size (228-item cluster always 500s)
- Small clusters (2-10 items) succeed reliably
- Each call takes 30s-3min on CPU

## Mitigations

1. **Truncate context proportionally** — cap total prompt tokens, reduce excerpts for large clusters
2. **Fallback labels must be good enough** — topic name + scam template + top entities
3. **Batch regeneration needs delay** — concurrent Ollama calls compound memory pressure
4. **Consider text sampling** — for 100+ item clusters, sample 10 diverse items, not just 10 most recent

## Hardware upgrade path

GPU deployment: Ollama with CUDA handles larger contexts reliably.
Update `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_NUM_PARALLEL` in compose when GPU available.

## See also

- `hardware.md` — full hardware upgrade matrix
- `learned/llm-narrate-structured-data.md` — structured context reduces token waste
