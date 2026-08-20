---
name: git-workflow
description: "Commit message format and pull request workflow. Covers the conventional type prefixes, and analysing full commit history plus a base-branch diff before drafting a PR summary and test plan. Use when writing a commit message or opening a PR."
---

# Git Workflow

## Commit Message Format
```
<type>: <description>

<optional body>
```

Types: feat, fix, refactor, docs, test, chore, perf, ci

## Pull Request Workflow

1. Analyse full commit history (not just latest)
2. `git diff [base-branch]...HEAD` for all changes
3. Draft PR summary
4. Include test plan

Note: Attribution disabled globally.