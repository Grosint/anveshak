Run a full pre-deployment validation checklist:

1. docker compose -f infra/compose.yml config --quiet — validate compose syntax
2. uv run pytest tests/unit/ -v — all unit tests
3. uv run pytest tests/integration/ -v — integration tests
4. Ollama health: curl -s http://localhost:11434/api/tags — confirm required models present (llama3.2:3b, mistral:7b)
5. Check compose.yml — no hardcoded secrets in environment blocks (no PASSWORD=, SECRET=, TOKEN= with literal values)
6. Run: uv run python scripts/verify_labels.py — labels field exists on all Pydantic models
7. Run: uv run python scripts/verify_reports_immutable.py — reports write-once guard present
8. If ANVESHAK_DRISHTI_BRIDGE=true: run /bridge-check
9. Check hardware.md — confirm all hardware-sensitive settings are in .env not hardcoded

Report PASS or FAIL with details for each check.
Do not proceed with deployment if any check FAILs.
