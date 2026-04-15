Verify that Phase $ARGUMENTS exit criteria are met.

The exit criteria are in `BUILD_SEQUENCE.md` under `## PHASE $ARGUMENTS`.

## Steps

1. Read `BUILD_SEQUENCE.md` — find the section for Phase $ARGUMENTS
2. For each numbered exit criterion:
   - Identify the specific file, function, table, or test that satisfies it
   - Check if it exists (read the file / grep for function / check migration)
   - Report [PASS] or [FAIL] with evidence (file:line or "missing")
3. Check data flow assertions — trace data from one service to another
4. Check test coverage criteria — verify test files exist and cover the right cases
5. At the end: count PASS/FAIL, give GO / NO-GO for moving to the next phase

## Output format

```
## Phase N Exit Criteria — [date]

### [Category name]
[PASS] N.1 — services/analyst/src/.../nlp.py:42
[FAIL] N.2 — missing: services/analyst/src/.../cluster.py not found
...

### Summary
PASS: 23/30  FAIL: 7/30

### Failing items
- N.X description
- N.Y description

### Recommendation
GO / NO-GO — reason
```

## Hard NO-GO rules (any single FAIL → NO-GO regardless of total score)

- Labels non-optional (criterion 0.12) — CLAUDE.md rule 2
- Report immutability (criteria 5.14–5.16) — CLAUDE.md rule 4
- Hardcoded ML config (criteria 0.21, 8.21) — CLAUDE.md rule 6
- Deepfake score as bool anywhere (criterion 4.14) — CLAUDE.md rule 7
- Credibility change without audit log (criterion 2.23–2.24) — CLAUDE.md rule 8
- LLM output not Pydantic-validated (criterion 5.10) — CLAUDE.md rule 9
- Any cloud LLM call (criterion 5.13) — CLAUDE.md rule 10
- X spend guard bypassed (criterion 3.22) — CLAUDE.md rule 11
