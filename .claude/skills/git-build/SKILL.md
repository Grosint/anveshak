---
name: git-build
description: "gitignore safety and Docker npm builds. Covers blanket directory patterns silently excluding same-named Python packages, user-specific files needing git rm --cached, git stash losing changes on a failed pop, and the two npm ci failure modes in Docker. Use when editing .gitignore, running git stash, or debugging npm ci in a Dockerfile."
---

# Git & Build

4 learned instincts. Git workflow + build config.

## .gitignore Safety

- Blanket dir patterns (`models/`, `media/`) silently exclude Python packages w/ same name. Use negation: `!sdk/anveshak/models/`
  Invisible on dev machines (files in working tree) — breaks on fresh clone only

- `.local` suffix or user-specific files must be in `.gitignore` + `git rm --cached`. Examples: `.claude/settings.local.json`, IDE workspace files, personal shell configs
  See: `.claude/skills/learned/gitignore-user-specific-config.md`

## Git Operations

- Never `git stash` for hypotheses — use worktrees or `--deselect`
  Failed `git stash pop` partially restores, silently reverts others
  Stash entry remains → `git stash drop` destroys unrecoverable changes
  Always verify w/ `git diff --stat`; resolve conflicts before dropping
  See: `.claude/skills/learned/git-stash-pop-silent-data-loss.md`

## NPM in Docker

- Two `npm ci` failure modes: lockfile not copied (use explicit paths, not globs) and lockfile missing packages (delete both `node_modules` and `package-lock.json`, reinstall fresh)
  Never `--prefer-offline` in Docker (skips packages not in non-existent cache)
  Correct: `npm ci --no-audit`
