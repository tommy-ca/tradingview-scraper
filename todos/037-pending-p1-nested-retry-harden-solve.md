---
status: complete
priority: p1
issue_id: "037"
tags: ['quant', 'performance', 'refactor']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
The `harden_solve` utility and its `@ridge_hardening` decorator both implement internal retry loops. This leads to redundant optimization attempts and potential exponential retry behavior, wasting compute resources and making logging harder to follow.

## Findings
- **File**: Solver utilities.
- **Issue**: Nested retry logic where both the caller (decorator) and the callee (function) handle their own retries for the same failure modes.
- **Impact**: Unnecessary delay in solver failure/success reporting and redundant compute usage.

## Proposed Solutions

### Solution A: Consolidate Retries in Decorator
Remove the internal retry loop from `harden_solve` and let the `@ridge_hardening` decorator handle all retry logic consistently.

### Solution B: Move Logic to Utility
If the decorator is too generic, move the specific hardening retry logic into the utility and simplify the decorator.

## Recommended Action
Remove the internal retry loop from `harden_solve` and rely on the `@ridge_hardening` decorator for consistent retry behavior across the solver suite.

## Acceptance Criteria
- [ ] Redundant retries eliminated in `harden_solve`.
- [ ] Solver attempts are correctly tracked in audit logs.
- [ ] Retry behavior remains stable and configurable via settings.

## Work Log
- 2026-02-02: Issue identified as P1 finding. Created todo file.
