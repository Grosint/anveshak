---
# Development Workflow

## Feature Implementation Workflow

0. **Research & Reuse** (mandatory before new implementation)
   - Search existing patterns in codebase first
   - Check hardware.md before adding ML component
   - Check .claude/skills/ for relevant patterns

1. **Plan First**
   - `/plan` for non-trivial changes
   - Hardware-sensitive decisions → document in hardware.md
   - Break into phases

2. **TDD Approach**
   - `/tdd` command
   - Tests must pass on CPU with default config (never assume GPU)
   - RED → GREEN → IMPROVE
   - 80%+ coverage on new code

3. **Test** (run appropriate layer for what changed)
   - `/test` — auto-detects test layer
   - Pure logic → `make test-unit` (< 30s)
   - SQL/DB/wiring → `make test-integration` (< 5min)
   - Service contracts → `make test-contract` (< 60s)
   - Before push → `make test-ci` (< 6min)
   - Before demo → `make test-scrape` (< 10min)
   - Every run shows: pass/fail with file:line, coverage per module

4. **Code Review**
   - `/code-review` after writing code
   - Address all FAIL issues before committing

5. **Commit**
   - Unit tests must pass before commit (`make test-unit`)
   - Conventional commits format
   - See git-workflow.md