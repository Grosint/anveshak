# Plan-Driven Development Across Session Boundaries

## Pattern
For multi-week implementation projects, write the complete plan to a docs/ file
ONCE. Each Claude Code session starts with:

```
Read docs/{plan_file}.md completely.
Session N: {Step name}. Phase {X}.
Start with /tdd.
```

Three lines. The plan has what to build, tests to write, and exit criteria.
No re-explanation needed across sessions.

## When to apply
- Any implementation exceeding 1 session (> ~4 hours of work)
- Engine C: 12 sessions across 8 weeks, all driven by engine_c_implementation_plan.md
- Plan document contains: architecture, steps, TDD per step, exit criteria per phase,
  test types, Makefile targets, risk register, definition of done

## Why
- Context window resets between sessions — plan file IS the context
- Memory system tracks progress ("EC-1 Step 10 migration complete")
- Plan changes stay in ONE authoritative file, not scattered across conversations
- /tdd and /code-review skills work within a session; plan coordinates ACROSS sessions

## Structure of a good plan document
1. Architecture overview (what the system looks like after)
2. Finalized steps (numbered, with module paths and purpose)
3. Phased implementation (steps grouped into phases with exit criteria)
4. Per-phase: Day-by-day tasks with TDD workflow
5. Test type matrix (which of the 9 test types apply where)
6. Makefile targets for running tests
7. Risk register
8. Definition of done

## Anti-pattern
Trying to hold implementation context in memory files. Memory is for
decisions and preferences. Plans are for implementation sequences.
