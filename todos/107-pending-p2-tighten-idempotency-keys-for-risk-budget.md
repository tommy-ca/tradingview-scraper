---
status: pending
priority: p2
issue_id: "107"
tags: [code-review, risk, integrity]
dependencies: ["103", "106"]
---

# Tighten idempotency keys for risk budget

## Problem Statement

If `intent_id` is missing, the current idempotency key is derived from static order economics and can collide across days.

This can undercharge budget (treat a new entry as a retry) and violate pacing constraints.

## Findings

- `EntryIntent.idempotency_key()` hashes only `{account_id, symbol, side, quantity, expected_entry_price, stop_loss_price}`.
- No day_key/campaign identifier is included in the fallback key.
- `spent_keys` is campaign-global and can cause old decisions to be replayed in later days.

## Proposed Solutions

### Option 1: Require intent_id at enforcement boundary (Recommended for live)

**Approach:**
- Make `intent_id` mandatory when `feat_daily_risk_budget_slices=1`.
- Use upstream `order.ref_id` or a generated stable intent UUID.

**Pros:**
- Clean contract, prevents collisions

**Cons:**
- Requires plumbing upstream

**Effort:** Medium

**Risk:** Medium

---

### Option 2: Scope the fallback key by day_key

**Approach:**
- Include `day_key` in the fallback key payload so identical orders on different days spend again.

**Pros:**
- Backwards compatible

**Cons:**
- Still collision-prone if multiple identical entries in one day are intended

**Effort:** Small

**Risk:** Low

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `tradingview_scraper/risk/budget.py`

## Acceptance Criteria

- [ ] Identical economic intents on different days consume budget independently when intent_id missing
- [ ] True retries (same intent_id) do not double-spend
- [ ] Add a test for “same params, different day”

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Identified cross-day collision risk in fallback idempotency
