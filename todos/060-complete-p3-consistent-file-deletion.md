---
status: complete
priority: p3
issue_id: "060"
tags: [quality, cleanup, consistency]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The `ingest_data.py` script used `os.remove` instead of the consistent `pathlib.Path.unlink` method used elsewhere.

## Findings
- **Location**: `scripts/services/ingest_data.py`: Line 132
- **Evidence**: `os.remove(p_path)`

## Proposed Solutions

### Solution A: Use Path.unlink (Recommended)
Replace with `p_path.unlink(missing_ok=True)`.

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [x] `os.remove` replaced with `unlink()`.

## Work Log
- 2026-02-05: Identified during code quality review.
- 2026-02-07: Replaced `os.remove` with `p_path.unlink(missing_ok=True)` in `scripts/services/ingest_data.py`.
