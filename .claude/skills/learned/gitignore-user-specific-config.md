# Gitignore User-Specific Config Files

## Problem

Files like `.claude/settings.local.json` contain user-specific IDE/tool preferences
(allowed tools, permission settings). Tracking them in git causes merge conflicts
and leaks individual developer preferences into the shared repo.

## Rule

Any file with `local`, `personal`, or user-specific scope must be:
1. Listed in `.gitignore`
2. Removed from git tracking with `git rm --cached <file>`

Common candidates:
- `.claude/settings.local.json` (Claude Code user prefs)
- `.vscode/settings.json` (VS Code user prefs — already covered by `.vscode/`)
- `.idea/` (JetBrains user prefs — already covered)

## Fix Pattern

```bash
# Add to .gitignore
echo ".claude/settings.local.json" >> .gitignore

# Remove from tracking (keeps local file)
git rm --cached .claude/settings.local.json

# Commit both changes
git commit -m "chore: untrack user-specific config"
```

## Lesson

If a config file has a `.local` suffix, it almost certainly should not be in git.
