# Path.parents[] Index Off-by-One

## Pitfall
`Path(__file__).resolve().parents[N]` counts from the file's directory (parents[0]),
NOT from the file itself. When computing project root from a deeply nested module,
always print the parent chain to verify.

## What happened
`geocoder.py` at `services/reporter/anveshak/reporter/geocoder.py` used `parents[5]`
to reach the project root. The correct index was `parents[4]`:
```
parents[0] = services/reporter/anveshak/reporter/     ← file's dir
parents[1] = services/reporter/anveshak/
parents[2] = services/reporter/
parents[3] = services/
parents[4] = .                                         ← project root ✓
parents[5] = ..                                        ← one level too high ✗
```

## Impact
Custom defence locations (`custom_locations.json`) silently failed to load.
38 locations (Galwan Valley, Pangong Tso, LAC, etc.) were missing from geocoding.
No error — just an empty `_CUSTOM_LOCATIONS` dict and a debug-level log.

## Prevention
```python
# Before using parents[N], verify:
print(Path(__file__).resolve().parents[N] / "expected_file.json")
# Or use a marker-file search:
p = Path(__file__).resolve()
while p.parent != p:
    if (p / "pyproject.toml").exists(): break
    p = p.parent
```

## Files
- `services/reporter/anveshak/reporter/geocoder.py` — fixed parents[5] → parents[4]
