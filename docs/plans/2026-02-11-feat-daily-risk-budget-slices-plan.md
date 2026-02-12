---
title: "feat: Daily Risk Budget (10 x 0.5% Entry Slices)"
type: feat
date: 2026-02-11
---

# feat: Daily Risk Budget (10 x 0.5% Entry Slices)

## Overview

Implement a prop-trading style **Daily Risk Budget** that throttles new entries using a fixed “slice” budget:

- Total budget per campaign: **5%** of reference equity
- Split into **10 slices of 0.5%** each
- Daily pacing: at most **2 entry decisions/day** that consume slices (<= 1.0% entry risk/day)
- The goal is to naturally spend the budget across **5–10 trading days** (min 5 days by design; no “must trade daily” enforcement).

This plan folds in reviewer feedback:

- Keep the MVP small (no DSL/policy engine, no complex reservation state machine)
- Tighten definitions/invariants (day boundary, what counts as an entry, how risk is computed)
- Make it auditable and restart-safe (append-only audit records + deterministic rehydration)

## Motivation

Prop firm rule sets (often 5% daily / 10% overall loss) fail accounts on equity touches and are sensitive to overtrading. The platform already has scaffolding for account guards (daily drawdown, overall equity guard), but we need an additional *variance + behavior control layer* that limits entry “attempt velocity”:

- Prevents blowing a day’s loss limit via too many attempts
- Enforces a steady pacing that matches real prop evaluation behavior
- Produces a deterministic, forensics-friendly audit trail (“why was this entry blocked?”)

## Scope

### In scope (MVP)

- A single guard that blocks **new entry intents** once daily or total slice limits are reached.
- Deterministic math and rounding at slice boundaries.
- Append-only audit records for every entry decision and daily reset.
- Restart safety by rehydrating state from audit records.

### Out of scope (defer)

- “Release slices on close” (open-risk budgeting). MVP treats slices as **spent** on entry.
- Multi-layer enforcement (pipeline + simulator + OMS) beyond one authoritative enforcement point.
- A general rule/policy engine / DSL.
- Rolling 3–5 day “risk velocity” limits (can be added later once the base budget is stable).

## Definitions (Must Be Explicit)

### Day boundary

- A “day” is defined by `risk_reset_tz` + `risk_reset_time` in settings (default: UTC 00:00).
- All daily counters reset only at that boundary.

### Reference equity (E_ref)

- For daily slice sizing, use **daily starting equity** at the day boundary.
- Equity is **mark-to-market** equity (open + closed PnL), net of fees if available.

### Entry

An “entry” is any instruction/order intent that **increases exposure**:

- New position open = entry (counts)
- Add-to-position / pyramid = entry (counts)
- Reduce/close = not an entry
- Replace/amend of existing bracket orders = not an entry unless it increases exposure

### Entry risk

Entry risk is computed as risk-to-stop divided by reference equity:

- `entry_risk_pct = max_loss_to_stop / E_ref`
- `max_loss_to_stop` is derived from the stop definition and position sizing.

Data contract:

- Entries must have a stop definition (explicit stop price or a rule that can deterministically derive it).
- If stop is missing/invalid, the entry is **blocked** (fail closed).

### Slice sizing

- `slice_pct = 0.005` (0.5%)
- `required_slices = ceil(entry_risk_pct / slice_pct)`
- Any entry requiring `required_slices > 2` is blocked (would exceed 1.0% daily cap).

Numerical rules:

- Use deterministic rounding (avoid float drift at boundaries).
- `ceil` must be stable (e.g., treat values within epsilon of an integer as exact).

## Policy Parameters

MVP parameters (defaults shown):

- `total_slices_per_campaign = 10`
- `slice_pct = 0.005`
- `max_entries_per_day = 2`
- `max_slices_per_day = 2`
- `campaign_total_slices = 10` (spent, not released)

Interpretation:

- “5–10 days” is an emergent property:
  - Max 2 slices/day implies a 5-day minimum to spend 10 slices.
  - Many runs will naturally spend 1–2 slices/day and finish within ~10 days.
  - If there are no signals, the system does not force trading.

## Proposed Solution (MVP)

### Core idea

Maintain a tiny per-account (or per-sleeve) state:

- `campaign_slices_remaining` (starts at 10)
- `entries_today` (resets daily)
- `slices_used_today` (resets daily)
- `day_key` and `E_ref` (frozen at the first decision of the day)

On each entry decision:

1. Ensure daily reset has run for the current day_key.
2. Compute `entry_risk_pct` and `required_slices`.
3. Block if any constraint would be violated.
4. If allowed, decrement:
   - `campaign_slices_remaining -= required_slices`
   - `entries_today += 1`
   - `slices_used_today += required_slices`
5. Emit an append-only audit record capturing inputs, computed values, and the resulting state.

### Authoritative enforcement point

Pick one authoritative enforcement point for MVP:

- Live: immediately before placing an entry order intent (OMS/strategy boundary)
- Backtest: immediately before turning an entry intent into fills/trades

Defer additional “belt and suspenders” enforcement in pipeline/export until the guard is stable and tested.

## Audit & Restart Contract

Every state mutation must be explained by an append-only record.

### Required audit record types

- `RISK_BUDGET_DAY_RESET`
  - Fields: `day_key`, `E_ref`, `campaign_slices_remaining`, `policy_version/hash`
- `RISK_BUDGET_ENTRY_DECISION`
  - Fields:
    - identifiers: `run_id`, account/sleeve id, (optional) strategy/provenance
    - inputs: symbol, sizing, stop definition, prices used
    - computed: `entry_risk_pct`, `required_slices`, daily counters pre/post
    - decision: allow/block
    - reason_code (if blocked)

### Restart safety

- On restart, rehydrate budget state by replaying audit records for the relevant scope.
- Idempotency requirement:
  - Each entry decision record should include a deterministic idempotency key (e.g., order intent id) so retries do not double-spend slices.

## Concurrency & Determinism

Constraints like “max 2/day” and “<= 1%/day” can be violated under concurrent entry attempts unless we enforce atomicity.

MVP requirement:

- The decision + decrement must be atomic for the scope (account/sleeve/day).
- If two entry attempts arrive simultaneously, exactly one may consume the remaining capacity, deterministically.

## Acceptance Criteria

### Functional (MUST NEVER)

- [ ] MUST NEVER allow more than `max_entries_per_day` entry decisions per day.
- [ ] MUST NEVER allow more than `max_slices_per_day` slices to be consumed in one day.
- [ ] MUST NEVER allow spending more than `total_slices_per_campaign` slices across the campaign.
- [ ] MUST NEVER allow an entry that lacks a deterministic stop definition.

### Auditability

- [ ] Every entry decision writes a `RISK_BUDGET_ENTRY_DECISION` record with computed risk and reason.
- [ ] Every day boundary writes a `RISK_BUDGET_DAY_RESET` record (once per day).

### Restart + Idempotency

- [ ] Restarting mid-day rehydrates counters correctly and does not double-spend slices.
- [ ] Retried entry intents with the same idempotency key produce the same outcome.

### Performance

- [ ] Budget check is O(1) and does not allocate DataFrames or large objects.

## Scenario Tests (Required)

| Scenario | Setup | Action | Expected result | Assertions |
|---|---|---|---|---|
| Day boundary correctness | `risk_reset_tz/time` set; E_ref defined | 2 entries before boundary, 1 after boundary | First day enforces 2/day; next day counters reset | day_key correct; no off-by-one resets |
| Concurrency race | Remaining daily capacity = 1 entry | Submit 2 entry intents concurrently | Exactly one allowed, one blocked | atomic check+decrement; deterministic outcome |
| Slice math boundary | entry_risk_pct near 0.5% and 1.0% | attempt entries at 0.4999%, 0.5001%, 0.9999%, 1.0001% | required_slices stable; >1.0% blocks | no float drift; ceil behavior consistent |
| Missing stop | stop definition absent | attempt entry | blocked with reason_code | audit record includes missing-stop reason |
| Restart rehydration | Some decisions already recorded today | restart and attempt another entry | counters match replay; correct allow/block | state derived from ledger is exact |

## Future Extensions (After MVP)

1) Open-risk budgeting (release on close)
- Track slices as allocated-to-position and release on full close.
- Requires position lifecycle integration and idempotent close events.

2) Rolling risk velocity
- Add a rolling 3–5 day cap on slices or drawdown-based aggression scaling.

3) Policy/rule engine (typed, no eval)
- Keep policies as validated data (Pydantic), compiled to a small allowlisted operator set.
- Must remain deterministic, bounded (DoS safe), and auditable.

## References (Internal)

- `docs/brainstorms/2026-02-11-rebalance-vs-stops-unification-brainstorm.md`
- `docs/plans/2026-02-11-feat-hierarchical-risk-engine-plan.md`
- `tradingview_scraper/risk/engine.py`
- `tradingview_scraper/risk/guards.py`
- `tradingview_scraper/risk/models.py`

## References (External)

- FTMO Trading Objectives (daily/max loss mechanics vary by firm): https://ftmo.com/en/trading-objectives/
- Daily loss often includes open + closed PnL + commissions (example): https://help.earn2trade.com/en/articles/3395926-how-is-my-daily-loss-calculated
