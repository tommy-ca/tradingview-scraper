---
status: complete
priority: p2
issue_id: "080"
tags: [quality, safety, validation]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The migration plan relies on "regression tests passing" as the only success metric. This is insufficient for a storage engine change (Pickle -> Parquet) where precision loss or schema changes might occur.

## Findings
- **Reviewer**: Kieran Rails Reviewer
- **Issue**: Lack of explicit data parity verification.

## Proposed Solutions

### Solution A: Parity Check Script (Recommended)
Create a script that:
1. Loads a sample "Golden Run" from Pickle.
2. Loads the migrated Parquet version.
3. Asserts frame equality with strict tolerance.
4. Checks dtypes.

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [ ] Parity check script created.
- [ ] Verified against 5 random artifacts.

## Work Log
- 2026-02-05: Identified during plan review.
