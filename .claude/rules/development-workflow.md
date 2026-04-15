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

3. **Code Review**
   - Use /code-review after writing code
   - Address all FAIL issues before committing

4. **Commit**
   - Conventional commits format
   - See git-workflow.md
