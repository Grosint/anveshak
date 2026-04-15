Check Ollama LLM runtime health:

1. curl -s http://ollama:11434/api/tags — list loaded models, report names and sizes
2. Assert llama3.2:3b is present (cluster labelling model)
3. Assert mistral:7b is present (report generation model)
4. Smoke test: POST http://ollama:11434/api/generate with model=llama3.2:3b and prompt="Reply with the single word OK"
   — assert response contains "OK", record latency
5. redis-cli -u $REDIS_URL ping — assert PONG (ARQ queue healthy)
6. Check analysis_jobs table: SELECT count(*) FROM analysis_jobs WHERE status='running' AND updated_at < NOW() - INTERVAL '10 minutes'
   — WARN if any stuck jobs found
7. Check OLLAMA_KEEP_ALIVE env var — WARN if not set to -1 on GPU hardware

Report model status, inference latency, queue health.
