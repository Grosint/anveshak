# Agent Wiring Check After GREEN

## Pattern
After implementation passes tests (GREEN), verify every new symbol has a caller.
Agents create new files but don't modify existing ones — wiring gets missed.

## When to use
Every TDD cycle, especially when using subagents to build code.

## How it works
After GREEN, before declaring done:
1. Every new function → grep for callers
2. Every new async loop → grep for registration in lifespan/startup
3. Every new UI button → verify onClick triggers API call
4. Every new API router → verify registered in main.py
5. Every new component → verify imported and rendered in route

## Why it matters
Two misses in one session:
- `_run_tracker_matching_cycle()` defined but never registered in scheduler loop
- Watch/Open Tracker buttons planned for cluster cards but never added to OverviewTab.tsx

Both were in the plan. Both were missed because agents created new files without modifying existing ones.

## Prevention
Added CONNECT step (step 3) to `/tdd` command. Runs automatically as part of TDD workflow.
Also: when delegating to agents, explicitly list which EXISTING files need modification.
