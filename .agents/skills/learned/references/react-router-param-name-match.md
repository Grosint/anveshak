# React Router Param Name Must Match useParams

## Pattern
Route param name in `<Route path="/:paramName">` must exactly match
the destructured key in `useParams<{ paramName: string }>()`.

## Pitfall
Mismatch causes blank page with no error — `undefined` ID silently
disables all queries (via `enabled: !!id`), so nothing renders but
nothing crashes either. Hard to debug.

## Example
```
// Route:   <Route path="/trackers/:trackerId" .../>
// WRONG:   const { id } = useParams<{ id: string }>()         // id = undefined
// RIGHT:   const { trackerId: id } = useParams<{ trackerId: string }>()
```

## Prevention
When adding a new route + page, grep the route path for the param name
and verify it matches useParams in the component.
