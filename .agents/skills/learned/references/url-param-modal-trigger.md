# URL-Param Modal Trigger

## Pattern
Open a Layout-level modal from any page by navigating with a URL query parameter.
Layout reads the param, opens the modal with prefilled state, then clears the param.

## When to use
When a modal (search, detail view, action sheet) lives in Layout but needs to be
triggered from child pages (e.g., Analytics clicking a convergence row should open
the global search modal prefilled with an identifier value).

## Implementation
```tsx
// In Layout.tsx
const [searchParams, setSearchParams] = useSearchParams()
const [modalOpen, setModalOpen] = useState(false)
const [initialValue, setInitialValue] = useState('')

useEffect(() => {
  const q = searchParams.get('search')
  if (q) {
    setInitialValue(q)
    setModalOpen(true)
    setSearchParams({}, { replace: true })  // clear param, don't pollute history
  }
}, [searchParams, setSearchParams])
```

```tsx
// In child page (e.g., AnalyticsDashboard)
// Option A: local modal instance with initialQuery prop
<IdentifierSearch open={open} onClose={close} initialQuery={value} />

// Option B: navigate to trigger Layout modal
navigate(`/analytics?search=${encodeURIComponent(value)}`)
```

## Key details
- Use `{ replace: true }` when clearing the param to avoid back-button pollution
- Modal component needs `initialQuery` prop (or equivalent) for prefill
- Reset `initialQuery` to `''` on close, not just on open
- Both approaches (local modal + URL param) can coexist — local is simpler for
  same-page triggers, URL param is for cross-page triggers

## Origin
Identifiers UX redesign — convergence card on Analytics opens global search modal
in Layout prefilled with clicked identifier value.
