---
status: pending
priority: p2
issue_id: "072"
tags: [data-integrity, safety, migration]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The migration script deletes the source pickle file if `--delete-source` is set, even if the conversion was skipped because the target exists (`SKIPPED_EXISTS`). This risks data loss if the existing target is corrupt.

## Findings
- **Location**: `scripts/maintenance/migrate_pickle_to_parquet.py`: Lines 59, 161
- **Issue**: Deletion logic doesn't check *why* the file was skipped.

## Proposed Solutions

### Solution A: Conditional Deletion (Recommended)
Only delete source files if the conversion status is `CONVERTED_PARQUET` or `CONVERTED_JSON`. If skipped, do not delete unless explicitly forced or verified.

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [ ] Source file preserved if conversion is skipped.
- [ ] Source file deleted only on successful conversion.

## Work Log
- 2026-02-05: Identified during data integrity review.
