# Issue Tracker

## Provider

GitHub Issues

## Repository

`Grosint/anveshak`

## CLI

`gh` (GitHub CLI)

## Workflow

Solo developer. All issues self-filed. No external contributors.

## External PRs as triage surface

No. This is a private defence product. PRs come only from the maintainer.

## How to create an issue

```bash
gh issue create --title "..." --body "..." --label "needs-triage"
```

## How to read issues

```bash
gh issue list --label "needs-triage"
gh issue list --label "ready-for-agent"
gh issue view <number>
```

## How to update an issue

```bash
gh issue edit <number> --add-label "ready-for-agent" --remove-label "needs-triage"
gh issue close <number> --reason completed
```
