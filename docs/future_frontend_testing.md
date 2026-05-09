# Frontend Testing Strategy — Architectural Review & Revised Plan

## Executive Summary

The original plan focused on **structure** (35 new files, 7 layers, Makefile targets). After deep code review, the real problem is **substance** — the existing 45 tests catch almost zero real bugs. The revised plan prioritizes **test quality over test count**, mirrors the backend's philosophy (not just its folder structure), and fixes 5 critical risks discovered during review.

## Methodology: Characterization Testing (NOT TDD)

TDD is wrong for this effort. TDD is for **building new features** — write the test first, watch it fail, then write the code. We're doing the opposite: **the code already exists and works**. We're adding a safety net around existing, running code.

**Characterization Testing approach:**
1. Read the code — understand what it actually does (not what it should do)
2. Write tests that pin the current behavior — including bugs
3. Mark known bugs as explicit test cases — `test('BUG: defaults to HIGH for unknown signals — should be LOW')`
4. Fix bugs separately — with the safety net already in place

**One exception:** If Phase 0's `lib/domain.ts` extraction introduces a new file, we can TDD that extraction — write tests for `inferSeverity` based on the SignalCard.tsx implementation, extract the function, verify tests pass. But that's a 30-minute task, not a methodology for the whole effort.

---

## Part 1: Honest Assessment of Current State

### What the existing 45 tests actually catch

| Test File | Tests | Would catch a real bug? | Why |
|-----------|-------|------------------------|-----|
| `auth.test.ts` | 7 | **Partially** — but tests an inline copy of `decodeJWT`, not the real function from AuthContext | Drift risk: if AuthContext changes `>=` to `>` in expiry check, test still passes |
| `signals.test.ts` | 8 | **No** — tests a function that doesn't exist in the app. Real `inferSeverity` in SignalCard.tsx has different logic (checks `independent_source_count` first) | **Live bug**: test passes but tests wrong code |
| `reports.test.ts` | 10 | **Partially** — `confidenceVariant()` is inline, not imported from component | Same drift risk |
| `topics.test.ts` | 6 | **No** — `hasRequiredFields()` is test-only, validates types that TypeScript already enforces | Redundant with compiler |
| `common.test.tsx` | 6 | **No** — `expect(container.firstChild).toBeTruthy()` passes for any element | No meaningful assertion |
| `Login.test.tsx` | 4 | **No** — 1 test checks input accepts typing; others check text exists. Never tests form submission, error state, or auth flow | Renders, doesn't test |
| `TopicsDashboard.test.tsx` | 2 | **No** — `expect(document.body).toBeTruthy()` always passes | Always-green test |
| `SignalsInbox.test.tsx` | 2 | **No** — `expect(text.length).toBeGreaterThan(0)` passes for any render | Always-green test |

**Verdict: 4 of 45 tests have partial value. 41 are noise.**

### What the original plan got wrong

1. **Over-indexed on layer taxonomy** — Mapping 8 backend layers to 9 frontend layers sounds impressive but misses the point. Backend layers exist because they test fundamentally different things (pure Python vs real DB vs Docker exec). Frontend doesn't need `migration` or `smoke` layers until there's substance in the core layers.

2. **Proposed builders before understanding what needs testing** — Fluent builders are infrastructure. You build infrastructure to serve tests, not the other way around. The backend built builders after writing 20+ tests with duplicated setup code. We should follow the same path.

3. **Coverage gate targets are aspirational without quality gates** — Going from 10% to 30% by creating hollow `expect(document.body).toBeTruthy()` tests defeats the purpose. The backend's 80% gate works because every test has meaningful assertions.

4. **Missed the critical bugs in the code** — A solution architect's first job is risk assessment. The code has 5 critical risks and 5 high risks that should drive test priorities, not a generic "test all pages" approach.

---

## Part 2: Critical Risks Found in Code Review

### RED — Will cause production incidents

| # | Risk | Location | Impact |
|---|------|----------|--------|
| R1 | **401 interceptor does hard `window.location.href` redirect** | `api/client.ts:15-25` | Orphans all in-flight requests, loses React state, no cleanup. If 401 hits during a mutation, data can be partially saved. |
| R2 | **`inferSeverity` defaults to HIGH for unknown signals** | `SignalCard.tsx:32` | Signal with `independent_source_count=null` and unknown type shows as HIGH severity. Creates false alerts. |
| R3 | **WSContext `disconnectedAt` overwritten on rapid disconnects** | `WSContext.tsx:104` | If two close events fire rapidly, second overwrites first. Resume point lost. Signals missed silently. |
| R4 | **JWT expiry countdown race condition** | `AuthContext.tsx:78-95` | 1-second interval can trigger logout while user dismisses warning banner. No cross-tab sync — token expires on background tab silently. |
| R5 | **Mock response shape mismatch in existing tests** | `TopicsDashboard.test.tsx:9` | Mock returns `{ data: [] }` but real `topicsApi.list()` returns `Topic[]` (already unwrapped). Tests pass, behavior is wrong. |

### ORANGE — Will cause analyst confusion

| # | Risk | Location | Impact |
|---|------|----------|--------|
| R6 | **Client-side filtering only** — language, credibility, date filters don't hit API | `useInfiniteContent.ts:7-15` | Loads all items into memory, filters in JS. Works for 100 items, breaks at 10,000. |
| R7 | **No file validation in DropZone** — `accept` attribute is UI-only | `DropZone.tsx:13-18` | User can drop .exe file, it gets uploaded. Parent must validate but may not. |
| R8 | **Date timezone mismatch** — uses YYYY-MM-DD without timezone | `SignalsInbox.tsx:79-84`, `ReportBuilder.tsx:99-106` | Analyst in UTC+5:30 selecting "Today" gets UTC boundaries. Off by up to 12 hours. |
| R9 | **Error message regex parsing** for delete confirmation | `SourceManager.tsx:290-293` | Extracts content count from error string via regex. Backend message format change = silent failure. |
| R10 | **`useQueries` mapped by array index** for warning counts | `SourceManager.tsx:516-526` | If sources array re-orders, warning counts map to wrong sources. |

---

## Part 3: Revised Plan — Quality Over Quantity

### Philosophy

The backend's Amazon-grade quality comes from three principles:
1. **Every test encodes a business rule** — not "renders without crashing" but "deepfake score 0.7 shows red label 'Likely synthetic'"
2. **Tests import the real function** — no inline re-implementations that drift
3. **Failure modes are tested explicitly** — not just happy path

### Phase 0: Fix What's Broken (Day 1)

Before writing new tests, fix the existing ones. Currently 41 of 45 tests provide false confidence.

**0.1 Extract testable functions from components into shared modules**

The root cause of the "inline re-implementation" problem is that business logic lives inside React components and can't be imported. Extract:

```
src/lib/domain.ts  <- NEW
  - inferSeverity(signal) — from SignalCard.tsx:23-32
  - confidenceVariant(score) — from report badge logic
  - credibilityVariant(score) — from CredibilityBadge thresholds
  - deepfakeLabel(score) — from DeepfakeMeter.tsx:31-38
  - resolveTimeRange(preset, from, to) — from SignalsInbox.tsx
  - applyClientFilters(items, filters) — from useInfiniteContent.ts:7-15
```

Components import from `lib/domain.ts`. Tests import the same functions. No drift.

**0.2 Fix the failing test** (`Login.test.tsx` — multiple elements match `/password/i`)

**0.3 Fix mock response shapes** — existing mocks return `{ data: [] }` but API clients return unwrapped arrays

**0.4 Delete always-green tests** — remove tests where the assertion always passes regardless of component behavior (e.g., `expect(document.body).toBeTruthy()`)

**Files modified:** 8 existing test files + 1 new `src/lib/domain.ts`

---

### Phase 1: Infrastructure That Earns Its Keep (Days 2-3)

Build only the infrastructure that the Phase 2 tests actually need. Don't build speculative infrastructure.

**1.1 Enhanced `setup.ts`** — global mocks for browser APIs
- `ResizeObserver`, `IntersectionObserver`, `matchMedia` stubs (needed by 4+ components)
- NOT a mock WebSocket — that's per-test, not global

**1.2 Enhanced `test-utils.tsx`**
- Wrap with `AuthContext` (currently missing — every page test mocks it separately)
- Accept `authState` overrides for authenticated/expired/unauthenticated scenarios
- Accept `initialEntries` for route-dependent pages
- Create `QueryClient` with `retry: false, gcTime: 0` (currently missing — can leak between tests)

**1.3 Mock factories — `src/test/mocks/api.ts`**
Build ONLY for the 3 API clients used in Phase 2 tests (not all 7 upfront):
- `mockTopicsApi(overrides?)` — list, create, toggleStatus
- `mockSignalsApi(overrides?)` — list, acknowledge, dismiss
- `mockSourcesApi(overrides?)` — list, get, updateCredibility

Each factory returns correct response shapes (matching the real `.then(r => r.data)` unwrapping).

**1.4 Data factories — `src/test/factories.ts`**
Simple factory functions (NOT fluent builders yet — earn that complexity):
```ts
export function makeTopic(overrides?: Partial<Topic>): Topic
export function makeSignal(overrides?: Partial<Signal>): Signal
export function makeSource(overrides?: Partial<Source>): Source
export function makeContentItem(overrides?: Partial<ContentItem>): ContentItem
export function makeReport(overrides?: Partial<Report>): Report
```

Fluent builders are justified when you have 20+ tests with 5+ variants each. We're not there yet.

**1.5 Coverage config** — `vite.config.ts`
- Add `@vitest/coverage-v8`
- Set initial threshold at 0% (don't gate on empty — gate after Phase 2)
- Exclude: `test/`, `main.tsx`, canvas components

**Files:** 4 modified (setup.ts, test-utils.tsx, vite.config.ts, package.json) + 2 new (mocks/api.ts, factories.ts)

---

### Phase 2: Tests That Catch Real Bugs (Days 4-10)

This is the core of the plan. Every test here encodes a specific business rule or catches a specific failure mode. Organized by risk priority, not by file type.

**2.1 Domain logic tests — `src/test/unit/domain.test.ts`**

Test the REAL extracted functions from `lib/domain.ts`:

```
inferSeverity:
  - independent_source_count >= 3 -> HIGH
  - independent_source_count >= 2 -> MEDIUM
  - independent_source_count = 1, type contains "CRITICAL" -> HIGH
  - independent_source_count = null, type = "unknown" -> should be LOW (bug R2: currently returns HIGH)
  - type contains "MED" -> MEDIUM

confidenceVariant:
  - score 0.75 -> 'success'
  - score 0.50 -> 'warning'
  - score 0.30 -> 'danger'
  - boundary: 0.70 exactly -> 'success'
  - boundary: 0.40 exactly -> 'warning'

deepfakeLabel:
  - 0.0 -> green, "Likely authentic"
  - 0.29 -> green (boundary)
  - 0.30 -> amber, "Inconclusive" (boundary)
  - 0.69 -> amber (boundary)
  - 0.70 -> red, "Likely synthetic" (boundary)
  - 1.0 -> red

applyClientFilters:
  - filters by language
  - filters by credibility_min
  - filters by date_from (string comparison)
  - filters by date_to
  - null/undefined filters pass through
  - empty items array returns empty
```

**2.2 API client interceptor tests — `src/test/unit/api-client.test.ts`**

This is the most critical untested code. A broken interceptor = entire app unusable.

```
Request interceptor:
  - Attaches Authorization header when token exists in localStorage
  - Skips header when no token
  - Uses Bearer prefix

Response interceptor:
  - 401 response triggers logout + redirect
  - 403 response does NOT trigger logout (different error)
  - 500 response propagates error normally
  - Network error propagates normally
```

**2.3 AuthContext lifecycle tests — `src/test/component/AuthContext.test.tsx`**

```
Login flow:
  - login(token) stores token in localStorage
  - login(token) decodes user from JWT payload
  - login(token) sets isAuthenticated = true

Expiry handling:
  - expired token on mount -> clears state, isAuthenticated = false
  - valid token on mount -> restores session
  - countdown reaches 300s -> shows warning banner
  - countdown reaches 0 -> triggers logout

Logout flow:
  - logout() clears localStorage
  - logout() sets isAuthenticated = false
  - logout() clears user

Edge cases:
  - malformed token -> handles gracefully (no crash)
  - missing token -> starts unauthenticated
```

**2.4 WSContext tests — `src/test/component/WSContext.test.tsx`**

```
Connection:
  - connects with JWT token as query param
  - uses wss:// for https origin
  - uses ws:// for http origin

Message handling:
  - JSON message dispatched to subscribers
  - ping messages filtered out
  - malformed JSON doesn't crash

Reconnect:
  - on close, schedules reconnect with backoff
  - backoff doubles: 1s -> 2s -> 4s -> 8s (capped)
  - on successful reconnect, backoff resets to 1s
  - disconnectedAt timestamp passed as 'since' param

Cleanup:
  - on unmount, closes socket
  - on unmount, clears reconnect timer
  - unsubscribe removes handler
```

**2.5 Page interaction tests — `src/test/integration/`**

NOT "renders without crashing". Each test simulates a user workflow:

**Login.test.tsx:**
```
- submit with valid credentials -> calls API -> navigates to /topics
- submit with wrong credentials -> shows error message
- submit while loading -> button is disabled
- show/hide password toggle works
```

**TopicsDashboard.test.tsx:**
```
- loads topics from API -> renders topic cards
- empty topics -> shows empty state
- click "Create Topic" -> opens modal
- click "Pause" on topic -> calls toggleStatus, updates UI optimistically
- API error on toggle -> shows error, reverts UI
```

**SignalsInbox.test.tsx:**
```
- loads signals -> renders signal cards with correct severity
- empty signals -> shows empty state
- click "Acknowledge" -> removes from 'new' tab optimistically
- switch to 'acknowledged' tab -> fetches different status
- time filter "Today" -> passes correct date range to API
- WS message arrives -> invalidates query, updates badge count
```

**2.6 Critical component tests**

**DropZone.test.tsx:**
```
- drag over -> visual feedback (dragging state)
- drop file -> calls onFile with dropped file
- click -> opens file picker
- keyboard Enter -> opens file picker
- disabled state -> no interactions
- drag leave -> removes visual feedback
```

**DeepfakeMeter.test.tsx:**
```
- score 0.1 -> green arc, "Likely authentic"
- score 0.5 -> amber arc, "Inconclusive"
- score 0.9 -> red arc, "Likely synthetic"
- aria-label includes percentage
- aria-live="polite" for screen reader updates
```

---

### Phase 3: Contract & Resilience (Days 11-14)

**3.1 API contract test — `src/test/contracts/api-contracts.test.ts`**

Mirror backend's `test_arq_job_contracts.py` philosophy: verify shape, not behavior.

```
For each API client module (topics, signals, content, reports, sources, vision):
  - Every exported function exists and is a function
  - Every function calls the shared `api` instance (not raw axios)
  - Response type assertion: call with mock, verify return shape matches TypeScript interface

For the shared api instance (client.ts):
  - baseURL is set
  - request interceptor is registered
  - response interceptor is registered
```

This catches the same class of bug as backend contract tests: when backend changes a response field and frontend API client isn't updated.

**3.2 Resilience tests — `src/test/resilience/error-handling.test.tsx`**

```
API failures:
  - 500 error -> page shows error state (not crash)
  - Network timeout -> page shows retry option
  - 401 during mutation -> redirects to login (tests R1 behavior)

WebSocket failures:
  - WS close during active session -> reconnect fires
  - WS error event -> socket closes cleanly
  - Server sends non-JSON -> no crash, message ignored

ErrorBoundary:
  - Component throws during render -> shows error UI with reload button
  - Component throws async -> error boundary does NOT catch (documents limitation)
```

**3.3 Regression tests — `src/test/regression/known-regressions.test.ts`**

Start with bugs found during this review:

```
R2: inferSeverity defaults to HIGH for unknown signals (not LOW)
R5: Mock response shape mismatch ({ data: [] } vs [])
Login.test.tsx: Multiple elements matching /password/i
```

Each test documents: bug description, root cause, regression risk.

---

### Phase 4: Conformance & E2E (Days 15-18)

**4.1 Component accessibility conformance — `src/test/conformance/a11y.test.tsx`**

Parametrized test over all interactive components:
```
For each of [SignalCard, ContentCard, DropZone, Button, Modal, Badge]:
  - has appropriate ARIA role or semantic element
  - is keyboard-navigable (Enter/Space trigger action)
  - has aria-label or visible label text
  - disabled state prevents interaction AND is communicated to screen reader
```

This mirrors the backend's `SourceAdapterConformanceSuite` — a standard every component must meet.

**4.2 Playwright E2E (2 files)**

Only after unit/component/integration layers are solid:
- `e2e/login-and-navigate.spec.ts` — login -> dashboard -> create topic -> navigate feed
- `e2e/analyst-workflow.spec.ts` — upload image -> view results -> generate report

Requires: `make up && make seed-demo`

---

### Phase 5: Makefile & CI Integration (Day 19)

```makefile
# -- Frontend Testing --
test-frontend:             ## Unit + component tests (~15s)
test-frontend-unit:        ## Pure TS logic tests (~5s)
test-frontend-component:   ## React component tests (~10s)
test-frontend-integration: ## Page-level tests with mock API (~20s)
test-frontend-contracts:   ## API shape verification (~2s)
test-frontend-resilience:  ## Error handling tests (~10s)
test-frontend-e2e:         ## Playwright against live stack (~2min)
test-frontend-coverage:    ## Coverage report + gate
test-frontend-full:        ## All layers except E2E

# Update composite target
test-full: test test-frontend-full
```

**Coverage gate ramp:**
- After Phase 2: set gate at measured coverage (whatever we actually hit with real tests)
- After Phase 3: raise by 10%
- After Phase 4: raise by 10%
- Target: 65-70% (not 80% — canvas/map components are legitimately untestable in jsdom)

---

## Part 4: What's Different From Original Plan

| Aspect | Original Plan | Revised Plan | Why |
|--------|--------------|--------------|-----|
| **Methodology** | Implied TDD | Characterization Testing | Code exists — we're adding a safety net, not building features |
| **Phase 0** | None | Fix existing broken tests first | 41 of 45 tests are noise — clean before building |
| **Domain logic** | Keep inline re-implementations | Extract to `lib/domain.ts`, import in tests AND components | Eliminates drift — the #1 existing problem |
| **Builders** | 7 fluent builders upfront (Day 1) | Simple factory functions; upgrade to builders when justified | YAGNI — earn complexity |
| **Test count** | ~55 new files | ~20 meaningful files | Quality over quantity |
| **Coverage gate** | 30% -> 80% in 3 months | Set gate at actual measured value after Phase 2 | Don't incentivize hollow tests |
| **Conformance suite** | Custom framework | Parametrized test with `test.each` | Simpler, same coverage |
| **Vitest workspace** | 4 projects with `--project` flag | Single test config with marker comments | Complexity not justified for 20 test files |
| **MSW/mock layer** | Full MSW setup | `vi.mock()` factories (3 modules, not 7) | Build what Phase 2 needs, add more in Phase 3+ |
| **Priorities** | Test by layer taxonomy | Test by risk severity (R1-R10) | Architect prioritizes by blast radius |

---

## Part 5: Files Summary

### Phase 0 (Day 1) — Fix
- **Create:** `src/lib/domain.ts` (extracted business logic)
- **Modify:** 8 existing test files (fix mocks, import real functions, delete hollow tests)
- **Modify:** Components that currently inline business logic (SignalCard, CredibilityBadge, DeepfakeMeter, SignalsInbox, useInfiniteContent)

### Phase 1 (Days 2-3) — Infrastructure
- **Modify:** `src/test/setup.ts`, `src/test/test-utils.tsx`, `vite.config.ts`, `package.json`
- **Create:** `src/test/mocks/api.ts`, `src/test/factories.ts`

### Phase 2 (Days 4-10) — Core tests
- **Create:** `src/test/unit/domain.test.ts`, `src/test/unit/api-client.test.ts`
- **Create:** `src/test/component/AuthContext.test.tsx`, `src/test/component/WSContext.test.tsx`, `src/test/component/DropZone.test.tsx`, `src/test/component/DeepfakeMeter.test.tsx`
- **Create:** `src/test/integration/Login.test.tsx`, `src/test/integration/TopicsDashboard.test.tsx`, `src/test/integration/SignalsInbox.test.tsx`

### Phase 3 (Days 11-14) — Contracts & Resilience
- **Create:** `src/test/contracts/api-contracts.test.ts`, `src/test/resilience/error-handling.test.tsx`, `src/test/regression/known-regressions.test.ts`

### Phase 4 (Days 15-18) — Conformance & E2E
- **Create:** `src/test/conformance/a11y.test.tsx`, `frontend/e2e/login-and-navigate.spec.ts`, `frontend/e2e/analyst-workflow.spec.ts`, `frontend/playwright.config.ts`

### Phase 5 (Day 19) — CI
- **Modify:** `Makefile`, `package.json` (scripts)

**Total: ~20 new test files, 1 new source file, ~15 modified files**

---

## Part 6: Verification

After each phase:
1. `cd frontend && npx vitest run` — all tests pass, zero always-green tests
2. `cd frontend && npx vitest run --coverage` — coverage reflects real assertions
3. Manual review: for each test, ask "if I delete the component, does this test fail?" If no -> test is hollow
4. After Phase 4: `make test-frontend-e2e` with live stack
5. After Phase 5: `make test-full` includes frontend

**The acid test:** Can you break the app in a specific way and have exactly one test fail with a clear error message? If yes, the test suite works. If no test fails, or 20 tests fail with vague messages, the suite needs work.
