---
status: complete
priority: p2
issue_id: "079"
tags: [refactor, simplification, maintenance]
dependencies: []
created_at: 2026-02-05
completed_at: 2026-02-05
---

## Problem Statement
The plan includes refactoring `scripts/archive/*.py` to use `DataLoader`. This is dead code ("archive") and refactoring it is waste.

## Findings
- **Reviewer**: Code Simplicity Reviewer
- **Issue**: Maintenance of obsolete code violates YAGNI.

## Proposed Solutions

### Solution A: Delete Archive (Recommended)
Delete `scripts/archive/` entirely. Git history preserves it if needed.

### Solution B: Ignore Archive
Exclude `scripts/archive/` from the migration plan/linting.

## Recommended Action
Implement Solution A. `rm -rf scripts/archive`.

## Acceptance Criteria
- [x] `scripts/archive` directory is removed.
- [x] Plan updated to remove this refactoring step.

## Work Log
- 2026-02-05: Identified during plan review.
- 2026-02-05: Deleted scripts/archive directory.
