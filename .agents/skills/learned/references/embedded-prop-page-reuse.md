# Embedded Prop Pattern for Page Component Reuse

## Problem
Page components (SourceManager, UserManagement) need to work both as standalone pages
at their own route AND as embedded content inside a parent page (Settings tabs).
Duplicating the component creates drift; wrapping creates layout issues.

## Solution
Add an `embedded` prop with a default of `false`:

```tsx
export default function SourceManager({ embedded = false }: { embedded?: boolean }) {
  return (
    <div className="h-full flex flex-col">
      {!embedded && (
        <div className="px-6 pt-6 pb-4 border-b ...">
          <h1>Sources</h1>  {/* full page header */}
        </div>
      )}
      {embedded && (
        <div className="px-4 pt-3 pb-3 ...">
          {/* compact header: just filter bar + action button */}
        </div>
      )}
      {/* shared content below — identical in both modes */}
    </div>
  )
}
```

Parent page provides its own header and renders `<SourceManager embedded />`.

## Key rules
- Default is `false` so standalone usage is unchanged (backward compat)
- The outer `h-full flex flex-col` stays in both modes — parent controls the height context
- Only the header/chrome changes; all functional content is shared
- Route redirects (`/sources` → `/settings/sources`) preserve bookmarks

## When to apply
Any time a page component needs to appear inside another page (tabs, split views, dashboards).
