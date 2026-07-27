# Domain Docs

## Layout

**Single-context.** One product, one glossary, one ADR folder.

## Files

| File | Purpose |
|------|---------|
| `/CONTEXT.md` | Domain glossary — canonical terms and their meanings |
| `/docs/adr/` | Architectural Decision Records |

## Consumer rules

### Reading CONTEXT.md

- Read `CONTEXT.md` at the start of any design or architecture task
- Use the glossary terms exactly — don't invent synonyms
- If a user's term conflicts with the glossary, surface the conflict immediately
- If a term is missing, propose adding it during the session

### Reading ADRs

- Before proposing an alternative to an existing pattern, check if an ADR explains why the current approach was chosen
- ADRs document trade-offs, not just decisions — read the "Alternatives Considered" section
- If an ADR's context has changed, propose updating its status rather than ignoring it

### Writing CONTEXT.md

- Update inline during design sessions — don't batch
- Keep it a glossary only — no implementation details, no specs, no architecture
- Each term: bold name + one-paragraph definition

### Writing ADRs

Only create when all three are true:
1. Hard to reverse
2. Surprising without context
3. Result of a real trade-off

Use the format: Status, Date, Context, Decision, Alternatives Considered, Consequences.
