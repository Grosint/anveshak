@AGENTS.md

# Claude Code specifics

Everything above applies to every agent working in this repo.
This section covers behaviour that only Claude Code implements.

## Skills

Skills are stored harness-agnostically in `.agents/skills/` and exposed to Claude Code
through per-skill symlinks under `.claude/skills/`.
Run `make agents-sync` after adding a skill or a persona so the symlink is created,
and `make agents-check` to verify the bridge has not drifted.
Never author a skill directly in `.claude/skills/`, since it will be invisible to Codex and Cursor.

## Subagents

| Agent | Purpose | When to use |
|-------|---------|-------------|
| security-auditor | Security violation detection | After any code write |
| schema-guard | Backward compat on model changes | After any Pydantic model change |
| code-reviewer | Architecture and quality review | After writing service code |
| infra-validator | Docker Compose validation | After infra changes |
| llm-safety-reviewer | LLM prompt injection and hallucination | After reporter or analyst changes |

Use these without being asked:

1. New service code goes to code-reviewer
2. A Pydantic model change goes to schema-guard
3. An `infra/` change goes to infra-validator
4. LLM code goes to llm-safety-reviewer
5. Security-sensitive code goes to security-auditor

Run independent agents in parallel.
security-auditor and schema-guard always run in parallel, as do code-reviewer and llm-safety-reviewer.

## Personas

Nine domain personas live in `.agents/personas/` and are symlinked into `.claude/agents/`.
They are review lenses rather than reviewers: ED, IB, LEA cyber, MEA, NCB, NIA, SEBI,
product manager, and solution architect.
Invoke one when a design decision needs a specific operational perspective.

IB is the only lens for a service that does not arrest, charge or prosecute.
Use it when the question is warning time, network mapping, external involvement,
or how an assessment is framed for a government consumer, since the other
agency lenses all assume a prosecution at the end of the work.
`make agents-sync` creates the symlink and `tests/unit/test_agent_persona_bridge.py`
asserts every persona has one.
