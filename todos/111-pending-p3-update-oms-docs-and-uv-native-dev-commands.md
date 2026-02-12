---
status: pending
priority: p3
issue_id: "111"
tags: [code-review, docs, devex]
dependencies: []
---

# Update OMS docs and uv-native dev commands

## Problem Statement

The code now includes `stop_loss` / `take_profit` fields on `UnifiedOrderRequest`, and local development should use `uv` native commands (no `pip` or global python).

Documentation should match the code and preferred tooling.

## Findings

- `tradingview_scraper/execution/oms.py` adds `stop_loss` / `take_profit`.
- `tradingview_scraper/execution/adapters/mt5_adapter.py` maps these fields.
- Running tests with `python -m pytest` is not supported in this environment; `uv` is installed and works.
- Full suite currently fails due to unrelated import errors, but targeted tests pass:
  - `uv run --extra dev pytest -q tests/test_daily_risk_budget_slices.py`

## Proposed Solutions

### Option 1: Update docs + add focused uv test targets (Recommended)

**Approach:**
- Update `docs/specs/unified_oms_design.md` to include SL/TP fields.
- Add a `Makefile` (or docs) entry for uv-native test runs:
  - `uv run --extra dev pytest -q tests/test_daily_risk_budget_slices.py`

**Pros:**
- Keeps docs accurate
- Encourages spec/TDD workflow without relying on global python

**Cons:**
- Small doc churn

**Effort:** Small

**Risk:** Low

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files (likely):**
- `docs/specs/unified_oms_design.md`
- `Makefile` and/or `README.md`

## Acceptance Criteria

- [ ] Docs reflect `UnifiedOrderRequest` fields including SL/TP
- [ ] Dev instructions use `uv` native commands (no pip)
- [ ] Provide at least one targeted test command for this feature

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Verified `uv` works and ran targeted tests successfully
