---
status: complete
priority: p2
issue_id: "096"
tags: [cleanup, simplicity, yagni]
dependencies: []
---

# Dead Code Purge (Simplicity Audit)

## Problem Statement
The repository contains numerous legacy artifacts, backup files, and temporary scripts that clutter the workspace and increase cognitive load.

## Findings
- **Files identified**: `pipeline.py.bak`, `settings.py.bak`, `symbols.parquet.bak`, various `reproduce_*.py`, `test_*.py` (ghost scripts).
- **Issue**: Repository hygiene.

## Proposed Solutions

### Solution A: Aggressive Purge
Delete all identified legacy and temporary files. Git history preserves them if needed.

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [x] Root directory and `scripts/` are clean of non-essential files.
- [x] `mlflow.db` removed from git tracking.

## Work Log
- 2026-02-07: Identified during simplicity audit.
- 2026-02-08: Purged identified files and updated .gitignore.
