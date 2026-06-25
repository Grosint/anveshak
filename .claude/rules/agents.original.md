---
# Agent Orchestration

## Available Agents

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| security-auditor | Security violation detection | After any code write |
| schema-guard | Backward compat on model changes | After any Pydantic model change |
| code-reviewer | Architecture + quality review | After writing service code |
| infra-validator | Docker Compose validation | After infra changes |
| llm-safety-reviewer | LLM prompt injection + hallucination | After reporter/analyst changes |

## Immediate Agent Usage (no prompt needed)
1. Any new service code → code-reviewer
2. Any Pydantic model change → schema-guard
3. Any infra/ change → infra-validator
4. Any LLM code → llm-safety-reviewer
5. Any security-sensitive code → security-auditor

## Parallel Execution
Run independent agents in parallel:
- security-auditor + schema-guard can always run in parallel
- code-reviewer + llm-safety-reviewer can run in parallel
