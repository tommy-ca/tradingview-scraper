---
status: complete
priority: p1
issue_id: "104"
tags: [code-review, risk, architecture, execution]
dependencies: []
---

# Wire entry budget into authoritative enforcement point

## Problem Statement

The daily risk budget slices feature is currently inert: `RiskManagementEngine.evaluate_entry_budget()` exists but is not called anywhere in the execution paths.

Without an authoritative integration point, risk budgeting cannot actually block entries in live or backtest.

## Findings

- `tradingview_scraper/risk/engine.py` defines `evaluate_entry_budget(intent)`.
- No call sites exist (repo grep shows only the definition).
- Allocation pipeline instantiates the risk engine, but does not place orders; OMS/live strategies do.

## Proposed Solutions

### Option 1: Enforce at OMS entry submission boundary (Recommended for MVP)

**Approach:**
- Define a single conversion `UnifiedOrderRequest -> EntryIntent`.
- Call `RiskManagementEngine.evaluate_entry_budget(...)` immediately before submitting any order that increases exposure.
- If BLOCK, do not submit the order; emit a clear log/audit record.

**Pros:**
- One authoritative boundary
- Avoids mismatches between pipeline and execution

**Cons:**
- Requires an engine/ledger handle at OMS boundary

**Effort:** Medium

**Risk:** Medium

---

### Option 2: Enforce inside backtest simulator only

**Approach:**
- Apply budget at the point where entries become fills.

**Pros:**
- Improves backtest truth

**Cons:**
- Does not protect live trading

**Effort:** Medium

**Risk:** Medium

## Recommended Action

Implemented Option 1 (OMS entry submission boundary) via a wrapper engine.

## Technical Details

**Affected files (likely):**
- `tradingview_scraper/portfolio_engines/nautilus_live_strategy.py`
- `tradingview_scraper/execution/*`
- `tradingview_scraper/risk/engine.py`

## Acceptance Criteria

- [x] Any exposure-increasing order intent is evaluated by the budget guard before submission
- [x] BLOCK decisions prevent order submission and are auditable
- [ ] Backtest path uses the same guard contract (EntryIntent -> Decision)

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Confirmed feature has no call sites and therefore cannot enforce constraints

### 2026-02-12 - Implementation

**By:** OpenCode (gpt-5.2)

**Actions:**
- Added `BudgetEnforcedExecutionEngine` to enforce entry-budget decisions at OMS `submit_order` boundary
- Defined `UnifiedOrderRequest -> EntryIntent` conversion helper
- Enforced only for exposure-increasing orders; exposure-decreasing bypasses budgeting
- Ensured BLOCK is auditable via both budget ledger decision and explicit OMS block record
- Added unit tests covering BLOCK + bypass behavior
