---
status: pending
priority: p2
issue_id: "109"
tags: [code-review, audit, integrity]
dependencies: ["105"]
---

# Remove raw JSONL fallback for risk budget audit

## Problem Statement

The budget module currently falls back to writing unchained JSONL records if `ledger._append` is unavailable.

That undermines the cryptographic chain guarantee of `AuditLedger` and can silently create mixed audit formats.

## Findings

- `tradingview_scraper/risk/budget.py:_append_ledger`:
  - uses `ledger._append` if present
  - otherwise writes raw JSON lines without `prev_hash`/`hash`

## Proposed Solutions

### Option 1: Require AuditLedger (Recommended)

**Approach:**
- Narrow the budget API to accept `AuditLedger | None`.
- If ledger is missing and feature enabled, fail closed (or at minimum, log loudly).

**Pros:**
- Preserves ledger invariants

**Cons:**
- Less flexible for ad-hoc callers

**Effort:** Small

**Risk:** Low

---

### Option 2: Make fallback writes chain-compatible

**Approach:**
- Implement the same `prev_hash/hash` mechanics inside the budget fallback.

**Pros:**
- Allows non-AuditLedger usage

**Cons:**
- Duplicates ledger logic; high risk of divergence

**Effort:** Medium

**Risk:** Medium

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files:**
- `tradingview_scraper/risk/budget.py`

## Acceptance Criteria

- [ ] No code path writes unchained records into `audit.jsonl`
- [ ] Budget audit records always include chain fields when using `AuditLedger`

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Identified chain integrity risk due to mixed write modes
