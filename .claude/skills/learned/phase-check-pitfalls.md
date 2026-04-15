# Pitfall Log: Phase-Check Failures

## When to load: before declaring a phase complete, or during code review

---

## Pitfall 1: WebSocket auth looks implemented but isn't (Phase 2, criterion 2.17)

**What happened:** The WebSocket handler docstring said "Authenticated via token query param"
and `verify_token()` existed in jwt.py, but the handler called `websocket.accept()` before
any validation. Auth was aspirational — never enforced.

**Why it's easy to miss:** Unlike REST routes where `Depends(get_current_user)` is obvious,
WebSocket handlers have no framework-enforced dependency injection for auth.
The code compiled and ran — the test suite didn't cover unauthenticated WS connections.

**Detection:** `/phase-check` caught it by reading the handler, not by running tests.

**Fix:** Always verify token before `websocket.accept()`. See `websocket-auth-pattern.md`.

**Rule to add to all WS code reviews:**
> Grep for `websocket.accept()` — every occurrence must be preceded by `verify_token()`.

---

## Pitfall 2: Transient Pydantic models and the labels rule

**What happened:** `ClusterLabel(BaseModel)` — used to validate Ollama LLM output shape —
was created without a `labels: Labels` field. CLAUDE.md says "every Pydantic model MUST
have a `labels: Labels` field." The test suite only checked SDK storage models.

**Resolution:** Transient LLM-output validation schemas (used only to parse a response,
never stored to DB, never passed between services) are exempt by convention.
Add a comment to make the exemption explicit:

```python
class ClusterLabel(BaseModel):
    """LLM output validation schema — not a stored model, labels not required."""
    model_config = ConfigDict(strict=True)
    label: str
    confidence: float
```

**Rule:** If a Pydantic model is stored to DB or passed across service boundaries,
it MUST have `labels`. If it is a transient parse/validation DTO, add the exemption comment.

---

## Pitfall 3: `independent_source_count` — SQL vs Python

The criterion says "COUNT(DISTINCT sources.platform)". The implementation uses
`len(set(platforms))` in Python after loading platforms via a JOIN in SQL.
Functionally identical but easy to flag as a mismatch during review.

**Lesson:** When the criterion uses SQL language, note explicitly in the function docstring
that it is the Python equivalent of the SQL aggregate. Reduces review noise.

---

## Pitfall 4: Context not threaded through to where it's actually needed (Phase 3, criterion 3.10)

**What happened:** Telegram's `_download_media()` needed `topic_id` for the media storage
path (`media/{topic_id}/{date}/{hash}.ext`), but `topic_id` was only available in
`poll_social_topic()` — several call levels above `collect()`. The initial implementation
used `channel_slug` as a substitute, which failed the criterion.

**Root cause:** The `collect()` ABC signature was designed without thinking about what
downstream helpers would need. When writing the ABC, ask: "what data will every
implementation eventually need, even deep in helper methods?" Add it to the signature up
front.

**Fix:** Added `topic_id: str` to `SourceAdapterBase.collect()`. Propagated through
`_iter_channel()` → `_download_media()`.

**Rule:** When designing an abstract method signature, trace all the way to the leaf
helpers that the implementation will call. If a leaf needs context, add it to the top-level
signature — it's much harder to add it later when you have multiple implementations.

---

## Pitfall 5: Setting defined in settings.py but never referenced (Phase 3, criterion 3.25)

**What happened:** `x_poll_interval_s: int = 900` existed in `SocialSettings` with the
correct default and docstring, but nothing in the codebase ever imported or used it.
The global `poll_interval_s` coincidentally had the same default, so behaviour was correct
but the criterion failed because the *specific setting* wasn't wired.

**Detection:** `/phase-check` caught it by grepping for `settings.x_poll_interval_s` in
the service code — zero matches.

**Rule:** After adding any new setting to `settings.py`, immediately grep for it in the
service code. If it has zero matches, it's not wired yet. Settings that aren't used are
misleading documentation at best, silent bugs at worst.

```bash
# Run this after every settings.py change:
grep -r "settings\." services/social/src/ | grep "x_poll_interval_s"
# Must return ≥1 match
```

---

## Pitfall 6: Per-adapter disabled warning missing (Phase 3, criterion 3.5)

**What happened:** Each adapter's `authenticate()` silently returned when
`*_adapter_enabled=False`. The only warning was a collective "no adapters enabled" log
in `main.py`. The criterion required a per-adapter warning.

**Why it happens:** `return` on a false-guard feels like "do nothing quietly", but for
operational visibility every disabled component should announce itself.

**Rule:** Every `authenticate()` early-return for disabled state must log a warning:
```python
if not settings.telegram_adapter_enabled:
    log.warning("social.adapter_disabled", adapter=self.adapter_id,
                hint="Set TELEGRAM_ADAPTER_ENABLED=true to activate")
    return
```
This makes it obvious in logs *why* an adapter isn't collecting — not a bug, just disabled.

---

## Pitfall 7: ARQ functions must be standalone — helpers inside another job don't count (Phase 4)

**What happened:** `run_yolo` and `run_clip` logic existed as helper code called from
`run_vision_analysis`, but they were NOT registered as named ARQ functions in
`WorkerSettings.functions`. The criteria explicitly required:
- `run_yolo(media_asset_id: str)` as an independently-enqueuable ARQ function
- `run_clip(media_asset_id: str, categories: list[str])` as an independently-enqueuable ARQ function

Phase-check caught both as FAIL.

**Root cause:** "The logic exists" ≠ "The ARQ function exists". ARQ routes jobs by function
name — if a function isn't in `WorkerSettings.functions`, it cannot be enqueued.

**Fix:** Promote both to full top-level `async def run_yolo(ctx, media_asset_id)` functions
with their own DB access and result storage. Register in `WorkerSettings.functions`.

**Rule:** When criteria say "X function exists and can be enqueued independently", verify:
1. `async def X(ctx: dict, ...)` exists at module level (not nested, not a method)
2. `X` is listed in `WorkerSettings.functions`
3. The function accesses `ctx["db_pool"]` directly (not via another job's conn)

```python
class WorkerSettings:
    functions = [run_vision_analysis, run_yolo, run_clip]  # all three, not just the main one
```

---

## Pitfall 8: Request model uses convenience alias instead of spec field names (Phase 5, criterion 5.30)

**What happened:** The BUILD_SEQUENCE criterion said `POST /api/v1/reports` accepts
`{topic_id, report_type, time_window_start, time_window_end}`. The implementation
used `time_window_hours: int = 72` — a convenience alias that computes the window
on the server side. Functionally equivalent, but the criterion explicitly named the
fields and `/phase-check` caught the mismatch.

**Rule:** When a criterion names specific request/response fields, use exactly those
field names. Convenience aliases (`*_hours`, `*_count`, `*_limit`) are fine as
*additional* optional fields but cannot *replace* the named fields.

**Fix pattern:**
```python
class GenerateReportRequest(BaseModel):
    topic_id: str
    report_type: str = "intelligence_brief"
    time_window_start: Optional[datetime] = None   # spec-named field
    time_window_end: Optional[datetime] = None     # spec-named field
    time_window_hours: int = 72                    # convenience fallback
```
Server logic: `time_end = req.time_window_end or now`.

---

## Pitfall 9: Status string values must match spec exactly (Phase 5, criterion 5.32)

**What happened:** `generation_status` was returned as `"pending"` for ungenerated
reports. The BUILD_SEQUENCE spec stated valid values: `queued/generating/complete/failed`.
`"pending"` is not in that set — the criterion failed.

**Why it happens:** "pending" is a natural English synonym for "queued", so the
developer writes it without checking the spec. Status strings are easy to eyeball
as "equivalent" when reviewing, and tests rarely assert on exact string values.

**Rule:** Grep the BUILD_SEQUENCE criterion for the exact status string values listed.
Copy them verbatim. If the spec says `queued`, use `"queued"` not `"pending"`.

**Rule:** Tests for status fields must assert the exact string, not just `assert status`.

```python
# WRONG
assert result["generation_status"]  # passes for any truthy string

# RIGHT
assert result["generation_status"] in {"queued", "generating", "complete", "failed"}
```

---

## Pitfall 10: pHash is colour-blind — solid colour test images produce identical hashes

**What happened:** `test_phash_different_images_differ` used solid red vs solid blue
images. Both returned the same hash (`0x8000000000000000`). The test expectation was
wrong — pHash uses DCT of grayscale values; a uniform image has zero AC frequency
components regardless of colour, so all solid images hash identically.

**Root cause:** pHash is a *perceptual* hash designed to detect near-duplicate
images with similar visual content. Solid colour patches have no texture/frequency
variation, so they're all "perceptually identical" to pHash.

**Fix:** Use images with actual texture — e.g. opposite-polarity checkerboard patterns:

```python
def _make_checkerboard(block_size: int, invert: bool) -> bytes:
    arr = np.zeros((64, 64, 3), dtype=np.uint8)
    for r in range(64):
        for c in range(64):
            cell = (r // block_size + c // block_size) % 2
            val = 255 if (cell == 0) ^ invert else 0
            arr[r, c] = [val, val, val]
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")  # PNG avoids JPEG DCT smearing
    return buf.getvalue()
```

**Rule:** pHash test images must have spatial frequency variation (checkerboards,
gradients, noise). Never test with solid-colour images.

---

## Pitfall 11: EXIF extraction returns empty dict before setting mandatory keys

**What happened:** `extract_exif()` returned `{}` early when a synthetic test image
had no EXIF metadata (`img._getexif()` returned None). The `ai_software_detected`
key was set after that early return and was never reached. Test failed:
`assert "ai_software_detected" in result`.

**Root cause:** Early-return `{}` before setting keys that are supposed to be
*always* present is a common pattern bug — it's easy to miss that the early return
bypasses mandatory field setting.

**Rule:** If a function guarantees certain keys are always in its output dict,
those keys must be set in ALL return paths — not just the happy path.

```python
# WRONG
if not raw:
    return {}  # ai_software_detected never set

# RIGHT
if not raw:
    return {"ai_software_detected": False}  # mandatory key present even on empty EXIF
```

**General rule:** Mandatory output keys → set them first (or in every branch), not last.

---

## Pitfall 12: postcss.config.js — `export default` breaks on Node 18 CJS (Phase 6)

**What happened:** PostCSS config used `export default { plugins: { tailwindcss: {}, autoprefixer: {} } }`.
Vite build failed: `SyntaxError: Unexpected token 'export'`.

**Root cause:** PostCSS loads its config file via `require()` on Node 18 (CJS resolution).
`export default` is ESM syntax and throws in CJS context. The Vite config (which is ESM) worked
fine, but PostCSS is a separate process that doesn't inherit Vite's ESM resolution.

**Fix:** Always use `module.exports` for PostCSS config:
```js
// postcss.config.js — CORRECT
module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } }
```

**Rule:** `postcss.config.js` and `tailwind.config.js` must use `module.exports`, not `export default`,
even in an otherwise ESM project. They are loaded by Node directly, not by Vite's ESM bundler.

---

## Pitfall 13: List API missing JOIN → frontend fields silently null (Phase 6)

**What happened:** `GET /api/v1/topics/{id}/content` returned content items but `source_name`
and `platform` were always null/undefined in the frontend. The TypeScript types declared
those fields, components tried to render them, no errors — just blank badges.

**Root cause:** The SQL `SELECT` only queried `content_items` without JOIN-ing `sources`.
The backend never returned the fields; the frontend silently rendered nothing.

**Why it's easy to miss:** TypeScript only type-checks what the client declares, not what the
server actually returns. A field typed as `string | null` that comes back as `null` from the
server looks correct to the compiler.

**Detection:** Phase-check caught it by reading the SQL in the route handler — saw no JOIN.

**Rule:** When a criterion says "card shows X from related table Y", immediately check the SQL
in the route handler. If there's no JOIN to table Y, add it — don't trust frontend types.

```sql
-- WRONG: content_items only, source fields will be null
SELECT ci.id, ci.url FROM content_items ci WHERE ci.topic_id = $1

-- CORRECT: JOIN sources so frontend gets source_name and platform
SELECT ci.id, ci.url, s.name AS source_name, s.platform
FROM content_items ci
LEFT JOIN sources s ON s.id = ci.source_id
WHERE ci.topic_id = $1
```

Use `LEFT JOIN` (not `INNER JOIN`) so content items without a source still appear.

---

## Pitfall 14: Vitest test files cause `tsc --noEmit` failures before `npm install` (Phase 6)

**What happened:** After creating `src/test/*.test.ts` files that import from `vitest`,
`tsc --noEmit` (run as part of `npm run build`) failed: `Cannot find module 'vitest'`.

**Root cause:** `vitest` is a `devDependency`. Before `npm install` runs (or in CI before
the install step), tsc cannot resolve the `vitest` module.

**Fix:** Exclude the test directory from the production TypeScript config:
```json
// tsconfig.json
{
  "include": ["src"],
  "exclude": ["src/test"]
}
```

Vitest handles its own type-checking during `vitest run`. The prod tsconfig doesn't need to
know about test files. `tsc && vite build` stays clean.

**Rule:** Always add `"exclude": ["src/test"]` to `tsconfig.json` when adding Vitest to
a Vite project. The test runner handles its own type-checking.

---

## Pitfall 15: Self-defeating defaults — a feature's own configuration makes it permanently inactive

**What happened (Phase 7, criterion 7.1):** `run_cross_verification_update()` was fully
implemented and registered as an ARQ job. The skip guard was:

```python
if abs(new_score - old_score) < settings.credibility_min_auto_drop:
    continue
```

Default: `credibility_min_auto_drop = 10.0`, `credibility_cross_verify_boost = 2.0`.
Since `2.0 < 10.0`, every boost was silently skipped. The feature built, tested (import-level),
deployed — and never fired once.

**Why it's hard to catch:** The code is logically correct. The skip guard is correct for drops.
There is no exception, no log message, no test failure. The feature just silently does nothing.
Review and unit tests that don't check default-value consistency miss this entirely.

**Detection:** Architectural review comparing all settings defaults for internal consistency.

**Fix:** Separate `credibility_min_auto_boost: float = 1.0` — a distinct threshold for boosts,
always defaulted below the boost amount. See `bidirectional-auto-scoring.md`.

**Rule:** Whenever a feature has a "minimum delta to act" guard, write a test that asserts
the default delta is larger than the default minimum:

```python
def test_boost_is_larger_than_min_boost_threshold():
    s = Settings()
    assert s.cross_verify_boost > s.min_auto_boost, (
        "Default boost must exceed min threshold or feature never fires"
    )
```

This test would have caught the defect before a single line of the feature code was written.

**General rule:** For any system that both produces a value AND guards on a minimum for that value,
assert `produced_value > minimum_value` in a settings-level test. Applies to: score changes,
retry delays, batch sizes, similarity thresholds.
