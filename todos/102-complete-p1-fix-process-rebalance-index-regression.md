---
status: complete
priority: p1
issue_id: "102"
tags: [code-review, risk, integrity]
dependencies: []
---

# Fix `process_rebalance` index regression

## Problem Statement

`RiskManagementEngine.process_rebalance()` can fail to zero out intended weights when the `pd.Series` index is not already string-typed.

This is a correctness issue in the risk layer: vetoed symbols may still be traded.

## Findings

- In `tradingview_scraper/risk/engine.py`, `process_rebalance()` iterates `for symbol in target_weights.index`, then does `sym = str(symbol)` and writes `final_weights[sym] = 0.0`.
- If `target_weights.index` contains non-string keys, this adds a *new* entry rather than overwriting the existing key.
- Reviewer finding: "looks like it worked" failure mode (silent regression).

## Proposed Solutions

### Option 1: Preserve original index key (Recommended)

**Approach:**
- Use `sym_str = str(symbol)` only for the veto lookup.
- Write `final_weights[symbol] = 0.0` to preserve the original key.

**Pros:**
- Minimal change, fixes bug
- Works for any index dtype

**Cons:**
- None material

**Effort:** Small

**Risk:** Low

---

### Option 2: Normalize weights to string index up front

**Approach:** Convert the entire series index to `str` once and use consistent string keys end-to-end.

**Pros:**
- Simplifies downstream lookups

**Cons:**
- Risky: changes external expectations of index types
- Easy to introduce subtle mismatch with upstream code

**Effort:** Medium

**Risk:** Medium

## Recommended Action

Implement Option 1.

## Technical Details

**Affected files:**
- `tradingview_scraper/risk/engine.py`

## Acceptance Criteria

- [x] Vetoed symbols are correctly zeroed for string and non-string index types
- [x] Add a unit test that uses a non-string index and verifies overwrite, not key insertion

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Identified potential silent correctness bug in veto application

**Learnings:**
- Pandas will happily add new keys to a Series when assigning with a different dtype key

### 2026-02-12 - Fix

**Actions:**
- Updated `RiskManagementEngine.process_rebalance()` to preserve original index keys when zeroing vetoed symbols.
- Added regression test for non-string index keys.
