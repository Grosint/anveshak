# Git & Build

Consolidated from 4 learned instincts. These apply to git workflow and build configuration.

## .gitignore Safety

- Blanket directory patterns (`models/`, `media/`) silently exclude Python packages
  with the same name. Use negation rules to whitelist: `!sdk/anveshak/models/`
  Invisible on developer machines (files exist in working tree) — only breaks on fresh clone
  See: `learned/gitignore-blanket-pattern-collision.md`

- Files with `.local` suffix or user-specific scope must be in `.gitignore`
  and removed from tracking with `git rm --cached`. Examples: `.claude/settings.local.json`,
  IDE workspace files, personal shell configs
  See: `learned/gitignore-user-specific-config.md`

## Git Operations

- Never use `git stash` to test hypotheses — use worktrees or `--deselect` instead
  Failed `git stash pop` partially restores files and silently reverts others
  Stash entry remains, so `git stash drop` destroys unrecoverable changes
  Always verify after pop with `git diff --stat`; resolve conflicts before dropping
  See: `learned/git-stash-pop-silent-data-loss.md`

## NPM in Docker

- Two `npm ci` failure modes: lockfile not copied (use explicit paths, not globs)
  and lockfile missing packages (delete both `node_modules` and `package-lock.json`,
  reinstall from scratch)
  Never use `--prefer-offline` in Docker (skips packages not in non-existent cache)
  Correct form: `npm ci --no-audit`
  See: `learned/npm-lockfile-docker-ci.md`
