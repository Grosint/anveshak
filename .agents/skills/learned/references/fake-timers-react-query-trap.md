# Fake Timers + React Query = Timeout Trap

## Problem
Using `vi.useFakeTimers()` with components that use React Query causes test
timeouts. React Query's internal retry/refetch timers never fire because
fake timers freeze `setTimeout`/`setInterval`. `waitFor()` from Testing
Library also uses timers internally, creating a deadlock.

`userEvent.setup()` is especially problematic — it uses internal delays that
never resolve under fake timers unless `advanceTimers` is provided.

## Symptoms
- Tests time out at 5000ms
- `waitFor(() => ...)` never resolves
- Works fine without fake timers

## Solution

**Option A: Don't use fake timers with React Query components.**
Mock the API at the module level with `vi.mock()` and use real timers.
`waitFor()` works naturally.

**Option B: If you need fake timers (e.g., testing countdown):**
- Use `fireEvent.click()` instead of `userEvent.click()` (no internal delays)
- Use `act(() => { vi.advanceTimersByTime(N) })` to manually tick
- Set `refetchInterval: false` on React Query to prevent timer-based refetches
- Don't wrap React Query components with fake timers — test the context/hook
  in isolation instead

**Option C: For AuthContext expiry tests:**
- Fake timers work because AuthContext uses raw `setInterval`, not React Query
- But `userEvent.setup()` still deadlocks — use `fireEvent` instead

## Example
```tsx
// BAD: times out
vi.useFakeTimers()
const user = userEvent.setup()
await user.click(button)  // deadlocks!

// GOOD: works with fake timers
vi.useFakeTimers()
fireEvent.click(button)
act(() => { vi.advanceTimersByTime(1100) })
```
