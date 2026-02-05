---
status: pending
priority: p2
issue_id: "058"
tags: [architecture, backward-compatibility, loader]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The `DataLoader` now strictly looks for `.parquet` files for returns, with no fallback to `.pkl`. If migration hasn't run or failed, historical data becomes inaccessible.

## Findings
- **Location**: `tradingview_scraper/data/loader.py`: Lines 147-153
- **Issue**: Strict dependency on parquet.

## Proposed Solutions

### Solution A: Add Fallback with Warning
Add a temporary fallback to `.pkl` if `.parquet` is missing, but log a warning.

### Solution B: Accept Strictness (If blocking migration intended)
If the migration is intended to be blocking/mandatory, keep as is but verify this decision.

## Recommended Action
Discuss with team. If backward compatibility is needed during transition, implement Solution A. If we are fully cutting over, Solution B is acceptable but risky. For now, flagging as P2 to ensure it's a conscious decision.

## Acceptance Criteria
- [ ] Decision made on backward compatibility.
- [ ] Implementation updated if fallback required.

## Work Log
- 2026-02-05: Identified during data integrity review.
