---
status: complete
priority: p1
issue_id: "103"
tags: [code-review, risk, audit, agent-native]
dependencies: []
---

# Audit all entry decisions in risk budget

## Problem Statement

The daily risk budget guard must be auditable. Today, some BLOCK decisions return early without emitting a ledger event.

This breaks forensics and agent parity (an agent cannot inspect why entries were blocked).

## Findings

- In `tradingview_scraper/risk/budget.py`, `evaluate_entry()` returns early for:
  - `INVALID_E_REF`
  - `MISSING_STOP`
  - `INVALID_PRICES`
- Those early returns do not append `RISK_BUDGET_ENTRY_DECISION` to `AuditLedger`, even when a ledger is provided.

## Proposed Solutions

### Option 1: Always emit a decision record (Recommended)

**Approach:**
- Centralize “build decision + append record” so every path writes the same event shape with `decision=BLOCK` and `reason_code`.

**Pros:**
- Matches spec and agent-native requirements
- Simplifies debugging and compliance tooling

**Cons:**
- Slightly more code

**Effort:** Small

**Risk:** Low

---

### Option 2: Enforce that a ledger is always present

**Approach:**
- If feature flag is enabled and `ledger is None`, fail closed (block entries).

**Pros:**
- Guarantees auditability in production

**Cons:**
- Requires plumbing a ledger into the authoritative enforcement point

**Effort:** Medium

**Risk:** Medium

## Recommended Action

Implemented Option 1: always emit a decision record when a ledger is provided.

## Technical Details

**Affected files:**
- `tradingview_scraper/risk/budget.py`

## Acceptance Criteria

- [ ] Every call to `evaluate_entry()` produces exactly one decision record when a ledger is provided
- [ ] Decision record schema is consistent for ALLOW and BLOCK
- [ ] Tests assert that missing-stop and invalid-price blocks write ledger events

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Identified unaudited early-return block paths

**Learnings:**
- Audit gaps are worse than “no audit” because they imply correctness without proof

### 2026-02-12 - Resolution

**By:** OpenCode

**Actions:**
- Updated `DailyRiskBudgetSlices.evaluate_entry()` to always append `RISK_BUDGET_ENTRY_DECISION` when a ledger is provided, including early-return blocks (`INVALID_E_REF`, `MISSING_STOP`, `INVALID_PRICES`).
- Added tests asserting one BLOCK decision record is written for each early-return reason.
