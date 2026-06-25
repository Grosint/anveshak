---
# Development Workflow

## Feature Implementation Workflow

0. **Research & Reuse** (mandatory before any new implementation)
   - Search for existing patterns in this codebase first
   - Check hardware.md before adding any ML component
   - Check .claude/skills/ for relevant patterns

1. **Plan First**
   - Use /plan command for any non-trivial change
   - Identify hardware-sensitive decisions — document in hardware.md
   - Break into phases

2. **TDD Approach**
   - Use /tdd command
   - Tests must pass on CPU with default config (never assume GPU)
   - Write tests first (RED) → implement (GREEN) → refactor (IMPROVE)
   - 80%+ coverage on new code

3. **Test** (run appropriate layer for what changed)
   - Use /test command — auto-detects which test layer to run
   - Changed pure logic? → `make test-unit` (< 30s)
   - Changed SQL/DB/wiring? → `make test-integration` (< 5min)
   - Changed service contracts? → `make test-contract` (< 60s)
   - Before push → `make test-ci` (< 6min)
   - Before demo → `make test-scrape` (< 10min)
   - Every test run shows: pass/fail with file:line, coverage per module

4. **Code Review**
   - Use /code-review after writing code
   - Address all FAIL issues before committing

5. **Commit**
   - Unit tests must pass before commit (make test-unit)
   - Conventional commits format
   - See git-workflow.md
