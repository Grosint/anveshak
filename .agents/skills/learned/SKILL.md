---
name: learned
description: "Index of 181 one-page notes on specific failure modes hit in this repository, each named after the mistake it prevents. The other skills and AGENTS.md cite these notes by path. Use when a rule cites a reference path, when a bug looks like one this repository has seen before, or when recording a newly learned failure mode."
---

# Learned notes

181 notes under `references/`, one failure mode per file.
A note exists because the failure happened here, cost time, and was not obvious from the code.

## How to use this skill

Read the specific note a rule cites rather than the whole set.
AGENTS.md, CLAUDE.md and the other skills cite notes by path, for example
`.agents/skills/learned/references/quality-gate-all-consumers.md`.

When no path is cited, search by symptom.
File names are the failure, not the subject, so grep the name first:

```bash
ls .agents/skills/learned/references | grep -i mock
grep -rl "ON CONFLICT" .agents/skills/learned/references
```

A note that names a file, function, setting or flag records what was true when it was
written, so verify the symbol still exists before acting on it.

## Adding a note

One failure mode per file, named after the mistake rather than the fix,
in the shape the existing notes use: the pattern, when it applies, why, and the
anti-pattern.
Cite the new note by path from whichever rule or skill sends a reader to it,
since nothing scans this directory automatically.
