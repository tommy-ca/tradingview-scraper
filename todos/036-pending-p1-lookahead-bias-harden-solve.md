---
status: pending
priority: p1
issue_id: "036"
tags: ['quant', 'risk', 'bug']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
`harden_solve` contains look-ahead bias by using out-of-sample data (`test_rets`) to make decisions about optimization windows. This is a stop-ship flaw as it invalidates backtest results by leaking future information into the training/hardening phase.

## Findings
- **File**: Likely in the optimization or solver utility modules.
- **Issue**: The utility uses `test_rets` to veto optimization windows, allowing the solver to "know" which windows will perform poorly before they are actually executed.
- **Impact**: Inflated performance metrics and unrealistic strategy results.

## Proposed Solutions

### Solution A: Remove `test_rets` from `harden_solve`
Completely remove the `test_rets` parameter and any logic that utilizes it within the `harden_solve` function. Ensure hardening decisions are made solely on training/validation data.

## Recommended Action
Refactor `harden_solve` to eliminate look-ahead bias by removing the `test_rets` dependency during the optimization phase.

## Acceptance Criteria
- [ ] `harden_solve` no longer accesses `test_rets` during optimization.
- [ ] Backtest verification confirms no future leakage in hardening windows.
- [ ] Audit logs reflect hardening decisions based only on historical/training data.

## Work Log
- 2026-02-02: Issue identified as P1 finding. Created todo file.
