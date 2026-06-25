---
# Hooks Configuration

Hooks are configured in .claude/settings.json.
They run automatically on file events.

Active hooks:
- PostFileWrite(services/**): triggers security-auditor
- PostFileWrite(sdk/**): triggers schema-guard
- PostFileWrite(infra/**): triggers infra-validator
- PostFileWrite(services/reporter/**): triggers llm-safety-reviewer
- PostFileWrite(services/analyst/**): triggers llm-safety-reviewer

Do not disable hooks without explicit user instruction.
