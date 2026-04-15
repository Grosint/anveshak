---
paths:
  - "**/*.py"
---
# Testing Rules

- pytest as test framework
- Tests MUST pass on CPU with default medium/nano/cpu config
- Never assume GPU availability in tests
- 80%+ coverage on all new service code
- pytest.mark.unit — no external dependencies
- pytest.mark.integration — requires running Docker Compose services
- pytest.mark.e2e — full demo arc, requires seeded data

## Hardware in Tests
- Mock Ollama responses in unit tests (never call real Ollama)
- Mock vision model inference in unit tests
- Use httpx.MockTransport for external API calls
- Integration tests use real PostgreSQL and Redis (Docker Compose)
