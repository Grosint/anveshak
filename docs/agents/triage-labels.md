# Triage Labels

Five canonical labels used by the `triage` skill to track issue state.

| Role | Label | Description |
|------|-------|-------------|
| Evaluate | `needs-triage` | Maintainer needs to evaluate this issue |
| Waiting | `needs-info` | Needs more thought / clarification before acting |
| Agent-ready | `ready-for-agent` | Fully specified, an AFK agent can pick this up |
| Human-ready | `ready-for-human` | Needs human implementation (judgment, design, security) |
| Won't fix | `wontfix` | Will not be actioned |

## State transitions

```
new issue → needs-triage
  → needs-info (incomplete spec)
  → ready-for-agent (clear spec, mechanical work)
  → ready-for-human (needs judgment or design)
  → wontfix (out of scope or duplicate)

needs-info → needs-triage (info provided)
ready-for-agent → closed (agent completes)
ready-for-human → closed (human completes)
```

## Notes

- No custom overrides. Default labels used as-is.
- Labels must exist in GitHub before first use. Create with:
  ```bash
  gh label create needs-triage --color "d93f0b" --description "Maintainer needs to evaluate"
  gh label create needs-info --color "fbca04" --description "Needs more info before acting"
  gh label create ready-for-agent --color "0e8a16" --description "Fully specified, agent can pick up"
  gh label create ready-for-human --color "1d76db" --description "Needs human implementation"
  gh label create wontfix --color "ffffff" --description "Will not be actioned"
  ```
