# Pattern: Optimistic UI Mutations (React Query)

## When to load: implementing list actions that should feel instant (ack, dismiss, delete, archive)

---

## The pattern

For list-mutating actions (remove, update, reorder), apply the change to the cache immediately
in `onMutate`, then roll back in `onError`. The server confirms asynchronously.
User sees instant feedback; errors silently restore state.

```tsx
// Canonical: optimistic remove from a list (signal dismiss / acknowledge)
const dismiss = useMutation({
  mutationFn: signalsApi.dismiss,

  onMutate: async (signalId: string) => {
    // 1. Cancel any in-flight refetches that would clobber our optimistic update
    await qc.cancelQueries({ queryKey: ['signals', activeTab] })

    // 2. Snapshot current state for rollback
    const prev = qc.getQueryData<Signal[]>(['signals', activeTab])

    // 3. Apply optimistic update immediately
    qc.setQueryData<Signal[]>(['signals', activeTab], (old = []) =>
      old.filter((s) => s.id !== signalId)
    )

    // 4. Return snapshot as rollback context
    return { prev }
  },

  onError: (_error, _signalId, ctx) => {
    // 5. Restore snapshot on failure
    if (ctx?.prev) {
      qc.setQueryData(['signals', activeTab], ctx.prev)
    }
  },

  onSettled: () => {
    // 6. Always refetch to sync server truth (catches partial failures)
    qc.invalidateQueries({ queryKey: ['signals'] })
  },
})
```

## Optimistic status update (change a field, not remove)

```tsx
const acknowledge = useMutation({
  mutationFn: signalsApi.acknowledge,
  onMutate: async (signalId) => {
    await qc.cancelQueries({ queryKey: ['signals', 'new'] })
    const prev = qc.getQueryData<Signal[]>(['signals', 'new'])
    qc.setQueryData<Signal[]>(['signals', 'new'], (old = []) =>
      old.map((s) => s.id === signalId ? { ...s, status: 'acknowledged' } : s)
    )
    return { prev }
  },
  onError: (_e, _id, ctx) => ctx?.prev && qc.setQueryData(['signals', 'new'], ctx.prev),
  onSettled: () => qc.invalidateQueries({ queryKey: ['signals'] }),
})
```

## Rules

1. **Always `cancelQueries` first** — prevent in-flight refetches from overwriting your optimistic state.
2. **Snapshot before mutating** — `getQueryData` before `setQueryData`.
3. **Return snapshot from `onMutate`** — React Query passes it as `ctx` to `onError`/`onSettled`.
4. **`onSettled` always invalidates** — even on success, sync with server to catch edge cases.
5. **Never disable the loading spinner** — optimistic UI for the list; button still shows `isPending` to prevent double-submit.

## When NOT to use optimistic UI

- Creates (POST) — server assigns the ID; can't fake it without a temporary ID
- Bulk operations — rollback is expensive
- Mutations that trigger side effects analysts need to see immediately (e.g. credibility updates that change a score display)
- Actions inside modals — modal closes on success anyway; optimism adds no UX value

## Button guarding

```tsx
// Show loading state on the action button — prevents double-submit
// while still updating the list optimistically
<Button
  onClick={() => dismiss.mutate(signal.id)}
  disabled={dismiss.isPending}   // ← still guard the button
  loading={dismiss.isPending}
>
  Dismiss
</Button>
```
