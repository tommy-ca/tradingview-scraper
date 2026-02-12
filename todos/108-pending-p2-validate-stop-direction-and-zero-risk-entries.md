---
status: pending
priority: p2
issue_id: "108"
tags: [code-review, risk, quality]
dependencies: ["103"]
---

# Validate stop direction and zero-risk entries

## Problem Statement

Entry risk computation currently uses `abs(entry - stop)` and allows “zero-risk” entries to consume 0 slices.

This can violate the spec’s deterministic data contract and allow pathological entries.

## Findings

- `tradingview_scraper/risk/budget.py` computes `max_loss_to_stop = abs(entry - stop) * qty`.
- This ignores whether the stop is on the correct side for BUY vs SELL.
- If `stop_loss_price == expected_entry_price`, required slices can be `0` and the entry can be ALLOW while incrementing entry counts without spending budget.

## Proposed Solutions

### Option 1: Enforce stop must increase loss in the correct direction (Recommended)

**Approach:**
- BUY: `stop_loss_price < expected_entry_price` else BLOCK
- SELL: `stop_loss_price > expected_entry_price` else BLOCK
- Decide policy for equal prices (block or treat as minimum 1 slice)

**Pros:**
- Enforces meaningful stops
- Avoids “free” entries

**Cons:**
- Requires agreement on what a valid stop is

**Effort:** Small

**Risk:** Low

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `tradingview_scraper/risk/budget.py`

## Acceptance Criteria

- [ ] Stops on the wrong side are BLOCKed with a specific reason code
- [ ] Zero-risk entries have explicit behavior (BLOCK or minimum slice)
- [ ] Add tests for BUY/SELL stop direction and equality

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Identified stop-direction ambiguity and zero-slice entry edge case
