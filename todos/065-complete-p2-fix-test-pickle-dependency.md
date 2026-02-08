---
status: complete
priority: p2
issue_id: "065"
tags: [quality, testing, regression]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
Multiple tests explicitly rely on `pd.read_pickle()` and `.pkl` files, which will break once the migration deletes source files or the loader stops supporting pickles.

## Findings
- **Files**: `tests/test_selection_evolution.py`, `tests/test_tournament_v2_tdd.py`, `tests/test_crypto_recovery_validation.py`
- **Issue**: Hardcoded `.pkl` usage.

## Proposed Solutions

### Solution A: Update Tests (Recommended)
Update tests to use `DataLoader` (which handles abstraction) or to check for `.parquet` first.

## Recommended Action
Refactor tests to use `DataLoader` or support Parquet.

## Acceptance Criteria
- [ ] Tests pass with Parquet files.
- [ ] Hardcoded `read_pickle` calls removed from tests.

## Work Log
- 2026-02-05: Identified during data integrity review.
- 2026-02-05: Updated tests to use `pd.read_parquet` and reference `returns_matrix.parquet`. Refactored `tests/test_selection_evolution.py`, `tests/test_crypto_recovery_validation.py`, and `tests/test_tournament_v2_tdd.py` to remove pickle dependency.
