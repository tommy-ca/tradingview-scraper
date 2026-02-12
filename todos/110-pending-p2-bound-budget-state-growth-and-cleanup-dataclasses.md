---
status: pending
priority: p2
issue_id: "110"
tags: [code-review, performance, quality]
dependencies: []
---

# Bound budget state growth and clean up dataclass defaults

## Problem Statement

`RiskBudgetState` keeps unbounded in-memory caches (`spent_keys`, `prior_decisions`) and uses `None` defaults with `__post_init__` + type ignores.

This can create memory growth in long runs and makes type safety weaker.

## Findings

- `tradingview_scraper/risk/budget.py`:
  - `spent_keys`/`prior_decisions` can grow with unique intents
  - Defaults are `None` with `__post_init__` + `# type: ignore`

## Proposed Solutions

### Option 1: Use `default_factory` and bound retention (Recommended)

**Approach:**
- Use `field(default_factory=set)` / `field(default_factory=dict)`.
- Scope idempotency cache by day_key and/or store only ALLOW decisions.

**Pros:**
- Cleaner code, bounded memory

**Cons:**
- Slightly more logic around eviction

**Effort:** Small

**Risk:** Low

---

### Option 2: Remove in-memory cache and rely on ledger-only

**Approach:**
- For retries, re-check ledger tail (or require intent_id and store only a small state file).

**Pros:**
- No unbounded in-memory growth

**Cons:**
- Requires fast ledger append/lookup (see issue 105)

**Effort:** Medium

**Risk:** Medium

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `tradingview_scraper/risk/budget.py`

## Acceptance Criteria

- [ ] No `# type: ignore` needed for default containers
- [ ] Cache growth is bounded by a documented policy (day scope / LRU / allow-only)

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Identified unbounded state and dataclass default anti-pattern
