# jsdom Dual-Nav Testing: Desktop + Mobile Both Render

## Problem
Layout components that render both a desktop sidebar (`hidden md:flex`) and a mobile
bottom nav (`md:hidden`) produce duplicate nav links in jsdom. Tailwind's responsive
classes (`hidden`, `md:flex`) have no effect in jsdom because there's no CSS engine
evaluating media queries — both navs are fully rendered in the DOM.

## Symptom
```
TestingLibraryElementError: Found multiple elements with the role "link" and name `/settings/i`
```

## Solution
Use `getAllByRole` instead of `getByRole` for nav link assertions:

```tsx
// WRONG — fails with "found multiple elements"
expect(screen.getByRole('link', { name: /topics/i })).toBeInTheDocument()

// CORRECT — handles desktop + mobile duplicates
expect(screen.getAllByRole('link', { name: /topics/i }).length).toBeGreaterThanOrEqual(1)
```

For "does NOT exist" assertions, filter by exact text to avoid partial matches:

```tsx
const links = screen.getAllByRole('link')
const sourcesLinks = links.filter((l) => l.textContent?.trim() === 'Sources')
expect(sourcesLinks).toHaveLength(0)
```

## When to apply
Any test for a Layout/Shell component that renders separate desktop and mobile navs.
