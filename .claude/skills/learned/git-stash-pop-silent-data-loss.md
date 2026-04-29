# Git Stash Pop Failure — Silent Data Loss

## When to load: any time you consider using git stash to test a hypothesis or verify pre-existing state

---

## Problem

`git stash pop` can **silently drop changes** when it encounters a merge conflict. Unlike `git merge` which leaves conflict markers, a failed stash pop:

1. Partially restores some files
2. Leaves other files in their pre-stash (clean) state
3. Keeps the stash entry (does NOT drop it)
4. Reports the conflict on only the conflicting file

If you then `git stash drop` thinking the pop worked, the stash is gone and the changes are unrecoverable.

## What happened (2026-04-29)

```bash
git stash                    # Stashed 14 modified files
# Ran a test to verify pre-existing failure
git stash pop                # FAILED — conflict on uv.lock
# ERROR: uv.lock would be overwritten
# Git partially restored frontend files, backend files reverted silently
git stash drop               # Destroyed the stash — changes gone
git checkout -- uv.lock      # Fixed the conflict file, didn't notice others were lost
```

Result: All backend changes (api/db/topics.py, routes/topics.py, signal_engine.py, settings.py) were silently reverted. Had to re-apply everything manually.

## Rules

1. **NEVER use `git stash` to verify pre-existing state.** Instead:
   - Use `git worktree` for isolated testing
   - Skip the failing test with `--deselect` and move on
   - Use the Agent tool with `isolation: "worktree"` for safe verification

2. **If you must stash, ALWAYS verify after pop:**
   ```bash
   git stash pop
   git diff --stat    # Verify ALL expected files show changes
   ```

3. **If stash pop fails, do NOT `git stash drop`.** Instead:
   ```bash
   git checkout -- <conflicting-file>   # Resolve the conflict
   git stash pop                        # Try again
   ```

4. **After ANY stash operation, run `git status`** and compare against the expected file list before proceeding.

## Detection

If you see fewer modified files than expected after a stash pop, the pop failed silently. Check `git stash list` — if the stash is still there, pop again after resolving conflicts.
