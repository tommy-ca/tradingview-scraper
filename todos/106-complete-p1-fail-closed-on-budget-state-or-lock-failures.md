---
status: complete
priority: p1
issue_id: "106"
tags: [code-review, risk, reliability, security]
dependencies: []
---

# Fail closed on budget state/lock failures

## Problem Statement

Risk budgeting is a guardrail. When restart rehydration or locking fails, the system must not silently continue in a fail-open mode.

Today, budget and rehydration failures can reset capacity or disable atomicity, enabling overspend.

## Findings

- `tradingview_scraper/risk/engine.py:118-125` swallows rehydrate failures with `except Exception: pass`.
- `tradingview_scraper/risk/budget.py` disables locking if `run_dir` errors occur (`_lock=None` => `_NullLock`).
- `rehydrate_from_ledger()` warns but otherwise continues with a fresh state.

## Proposed Solutions

### Option 1: Fail closed when feature is enabled (Recommended)

**Approach:**
- If feature flag enabled and rehydrate fails, block entries until state is trusted.
- If lock cannot be acquired/initialized, block entries (or raise).
- Remove blanket exception swallowing; log + propagate a clear failure mode.

**Pros:**
- Guardrails remain guardrails
- Prevents silent bypass

**Cons:**
- Can halt trading if filesystem/ledger is broken

**Effort:** Medium

**Risk:** Medium

---

### Option 2: Persist a separate compact state file

**Approach:**
- Use a small state snapshot file written atomically (lock + temp + rename).
- Rehydrate from snapshot rather than replaying `audit.jsonl`.

**Pros:**
- Faster restarts
- Less dependent on large ledger replay

**Cons:**
- Adds another persistence channel

**Effort:** Medium

**Risk:** Medium

## Recommended Action

Implemented Option 1 (fail closed behind feature flag).

## Technical Details

**Affected files:**
- `tradingview_scraper/risk/engine.py`
- `tradingview_scraper/risk/budget.py`

## Acceptance Criteria

- [x] If rehydrate fails, the system does not allow spending new slices silently
- [x] Rehydrate/lock failures emit clear logs and an auditable event
- [x] Add a test that simulates ledger read failure and asserts conservative behavior

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Identified fail-open paths and swallowed exceptions in risk enforcement

### 2026-02-12 - Resolution

**Actions:**
- Removed silent exception swallowing in `RiskManagementEngine.sync_daily_state`.
- Enforced fail-closed budget decisions when strict budget enforcement is enabled and rehydration/locking is untrusted.
- Added regression unit test for ledger read failure -> conservative BLOCK with audit record.
