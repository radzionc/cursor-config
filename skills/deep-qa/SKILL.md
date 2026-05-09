---
name: deep-qa
description: >-
  Deep QA testing of a feature. Generates a tiered test plan from codebase
  analysis, executes adaptively in the browser, fixes frontend issues inline,
  and skips tests blocked by backend problems. Invoke explicitly via "deep QA",
  "comprehensive QA", or "test everything".
disable-model-invocation: true
---

# Deep QA

You are an orchestrator for end-to-end feature verification. Delegate everything — browser testing, code exploration, code fixes. Your only work is decomposition, triage, and synthesis.

## Input

The user provides:

- **Feature to test** — name or description
- **URL** — page URL, or an already-open browser tab
- **Focus areas** (optional) — specific flows or concerns to prioritize

If no URL is provided, check the attached browser tab context. If neither is available, ask.

## Process Overview

```
Phase 1 → Generate tiered test plan (explore + plan subagents)
Phase 2 → Adaptive execution (run tier by tier, fix or skip as needed)
Phase 3 → Final report
```

---

## Phase 1: Generate Tiered Test Plan

### 1a. Explore the Feature Codebase

Delegate to an `explore` subagent (thoroughness: "very thorough"):

```
Explore the codebase for the "{feature}" feature. Find all relevant source files.

For every relevant file, report:

1. **Component inventory** — what it renders, what props/inputs it takes
2. **State management** — stores, context, form state, derived state
3. **API integration** — which endpoints are called, what data flows in/out
4. **User interactions** — buttons, inputs, dropdowns, toggles, forms, modals, dialogs
5. **Validation rules** — schemas, form validation, input constraints
6. **Conditional rendering** — loading states, error states, empty states, disabled states
7. **Navigation** — routes, links, redirects within the feature

Return a structured inventory. Be exhaustive — every file matters.
```

### 1b. Generate Tiered Test Scenarios

Delegate to a `generalPurpose` subagent with the exploration results:

```
You are a senior QA engineer who thinks outside the box. Given this feature inventory, generate a COMPREHENSIVE test plan organized into TIERS.

FEATURE: {feature_name}
URL: {url}

CODEBASE INVENTORY:
{paste exploration results here}

TIER SYSTEM — tests are grouped by dependency depth:

**Tier 0: Foundation** — does the page load? does data appear? are API calls succeeding?
Smoke tests. If they fail, most other tests are pointless.

**Tier 1: Core Interactions** — do the main user flows work?
Depend on Tier 0 passing. If basic data isn't loading, skip these.

**Tier 2: Validation & Error Handling** — does the feature handle bad input and failure gracefully?
Depend on core interactions working.

**Tier 3: Edge Cases & Polish** — creative, adversarial, and UX-focused tests.
Only worth running once the basics all work.

For each test, specify DEPENDENCIES:
- **Depends on API**: {endpoint} — if this API is broken, SKIP this test
- **Depends on test**: {test ID} — if that test failed, SKIP this test
- **Independent**: no dependencies, always runnable

CATEGORIES to cover across tiers:

- Happy paths — every main user flow end-to-end
- Input validation — empty, max length, special chars, negative, zero, decimals, paste
- State transitions — loading → loaded → error, enabled → disabled
- Error handling — API failures, network issues, malformed data
- Edge cases — double-click, rapid actions, back/forward, quick switching
- Boundary conditions — min/max values, overflow, truncation
- Data display — formatting, calculations, labels, currency, percentages
- Empty/zero states — no data, no items, zero values
- UI/UX — hover, tooltips, cursors, focus, keyboard nav
- Cross-feature — auth states, navigation, interactions with adjacent features

Think creatively. What would break? What would a user accidentally do?

OUTPUT FORMAT — return a numbered list grouped by tier:

## Tier 0: Foundation
---
T01 | Foundation | Page loads and displays data
Depends on API: /api/items
Steps:
1. Navigate to the URL
2. Wait for page to fully load
Expected: Content is visible with real data, no errors in console
Screenshot: qa-deep-T01.png
---

## Tier 1: Core Interactions
---
T05 | Core | Submit the main form
Depends on test: T01
Steps:
1. Fill in required fields
2. Click submit
Expected: Form submits successfully, confirmation is shown
Screenshot: qa-deep-T05.png
---

## Tier 2: Validation & Errors
...

## Tier 3: Edge Cases & Polish
...

Generate 20-25 test scenarios across all tiers. Merge related validations into
single multi-step tests (e.g., all form validation rules = 1 test with multiple
sub-assertions, not 3 separate tests). Each test should be a meaningful user flow,
not a unit-test-style single assertion.
```

After receiving the test plan, record per test: `id`, `tier`, `deps` (api + test), `status`. Nothing else. Test steps, screenshots, and full results live in subagent returns, not your context.

---

## Phase 2: Adaptive Execution

Execute tests **tier by tier, sequentially within each tier**. After EACH test result, decide the next action before running the next test.

Never launch more than one QA subagent at a time — they share one browser instance.

### Batching Observation-Only Tests

Tier 0 tests that are purely observational (no interactions, just checking data displays) can be batched as numbered sub-tests inside a single QA delegation. This is one subagent running several assertions sequentially in one browser session — not parallel subagents.

### Execution Algorithm

```
blocked_apis = []
blocked_tests = []

for each tier (0, 1, 2, 3):
    for each test in tier:

        # Check if this test should be skipped
        if test.depends_on_api IN blocked_apis → mark SKIPPED, continue
        if test.depends_on_test IN blocked_tests → mark SKIPPED, continue

        # Run the test
        result = delegate to qa subagent

        if result == PASS:
            continue to next test

        if result == INCONCLUSIVE or UNCLEAR:
            # Retry with a different approach — NEVER mark as "manual verification"
            re-delegate with explicit workaround instructions
            max 2 retry strategies, then mark UNFIXED

        if result == FAIL:
            # Immediate triage: is this frontend or backend?

            if BACKEND issue (API errors, missing data, wrong responses):
                mark test as BE_BLOCKED
                add test.depends_on_api to blocked_apis
                add test.id to blocked_tests
                continue to next test

            if FRONTEND issue (UI logic, validation, styling, interaction):
                # Fix it NOW before running more tests
                delegate fix to generalPurpose subagent
                run lint/typecheck via shell subagent
                retest this specific test via qa subagent
                if still fails after 3 attempts:
                    mark as UNFIXED, add to blocked_tests
                else:
                    mark as FIXED
                continue to next test

    # After completing a tier, summarize before moving to next
    log: "Tier {N} complete: X passed, Y fixed, Z blocked, W skipped"
    if ALL tests in this tier are blocked/skipped:
        log: "Skipping remaining tiers — foundation is broken"
        break
```

### QA Delegation Prompt

For each test, delegate to `Task(subagent_type="qa")`:

```
QA environment: cursor

TEST: {test_id} — {test_name}
Category: {category}

Navigate to: {url}

Steps:
{numbered steps from test plan}

Expected outcome:
{expected behavior}

After completing the test:
1. Take a screenshot named "{screenshot_filename}"
2. Report PASS or FAIL
3. If FAIL: describe exactly what went wrong (expected vs actual)
4. If FAIL: classify the root cause:
   - FRONTEND: wrong UI logic, missing validation, broken interaction, styling issue
   - BACKEND: API returns wrong/missing data, endpoint errors, server error in console
   - UNCLEAR: could be either, needs investigation
5. If BACKEND: note which API endpoint is broken and what it returns

Important:
- Use browser_snapshot to read page content and check for console errors.
- Use browser_take_screenshot for visual evidence.
```

### Frontend Fix Delegation Prompt

When fixing inline, delegate to a `generalPurpose` subagent:

```
Fix the following frontend bug:

BUG: {description of what's wrong}
EXPECTED: {what should happen}
ACTUAL: {what currently happens}
AFFECTED FILE(S): {file paths if known from exploration}
TEST CONTEXT: This was found during test {test_id}

Fix the code. After fixing:
1. Run the project's lint and typecheck commands to verify no regressions
2. Report what you changed and which files were modified

Rules:
- Follow all project conventions (check .cursor/rules/ if available)
- Minimal fix — don't refactor unrelated code
```

---

## Phase 3: Final Report

A deep-qa run satisfies the `quality-gates` QA gate for the feature area it covered. Subsequent edits re-arm the gate as usual.

Present a summary to the user:

### Results Table

| Test | Tier | Name | Result | Details |
|------|------|------|--------|---------|
| T01 | 0 | Page loads | PASS | — |
| T02 | 0 | API data displays | BE BLOCKED | /api/items returns 500 |
| T03 | 1 | Form submission | PASS | — |
| T04 | 1 | Input validation | FIXED | Added min-length check in `form.tsx` |
| T05 | 2 | Empty input | SKIPPED | Depends on T02 (BE blocked) |
| T06 | 3 | Double-click submit | SKIPPED | Depends on T02 (BE blocked) |

### Summary

- **Total tests**: X
- **Passed**: Y (passed on first run)
- **Fixed**: Z (failed, then fixed inline and now passing)
- **BE blockers**: W (backend issues preventing test execution)
- **Skipped**: S (skipped due to upstream blocker)
- **Unfixed**: U (failed, retried with different approaches, still failing)

### Screenshots

Display screenshots for any FAIL, FIXED, or BE BLOCKED items:
1. Run `echo "${TMPDIR}cursor/screenshots/"` to get the screenshots directory
2. For each screenshot filename, resolve full path: `<screenshots-dir><filename>`
3. Call `Read` on the full path to render inline
4. Add clickable link below each

### Backend Blockers

For each backend issue (deduplicated by endpoint — multiple tests hitting the same broken endpoint = one entry):

- **Endpoint**: the broken API path
- **Symptom**: what it returns vs what's expected
- **Affected tests**: which tests are blocked
- **Impact**: what user-facing functionality is broken

### Skipped Tests

List tests that were skipped and why, so the user knows what to retest once blockers are resolved.

---

## Execution invariants

- **Screenshot convention** — bare filenames, prefixed `qa-deep-`, e.g. `qa-deep-T07.png`. The `qa` agent writes them under `${TMPDIR}cursor/screenshots/`.
- **No manual verification** — if a test is inconclusive, retry with a different approach. Only mark "cannot verify" for flows genuinely requiring human credentials (auth, payment, hardware tokens). Max 2 retry strategies before marking UNFIXED.
- **No skipping for convenience** — every test in the plan must be executed or explicitly blocked by a dependency failure. "Similar to a tested pattern" is not a valid skip reason. If the plan has too many tests, fix the plan size, not execution.
- **Strict PASS/FAIL triage** — when a QA agent reports FAIL but you suspect an automation artifact: (1) do NOT override to PASS based on code reading alone, (2) re-delegate with workaround instructions, (3) only mark PASS after a QA agent confirms it in the browser.
