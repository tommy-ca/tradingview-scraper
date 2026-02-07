---
status: complete
priority: p1
issue_id: "083"
tags: [security, architecture, simplicity]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The plan includes complex steps for "Mass Artifact Conversion" (Docker, parallel processing) and "Refactoring Archive Scripts". This is over-engineering for stale data.

## Findings
- **Reviewer**: DHH / Simplicity Reviewer
- **Issue**: YAGNI violation. Treating local data conversion like a mission-critical system.

## Proposed Solutions

### Solution A: "Delete & Re-run" (Recommended)
1. Delete all `data/**/*.pkl` files.
2. Delete `scripts/archive/`.
3. Re-run `make flow-production` to generate fresh Parquet data.
4. Manually fix only *active* scripts that break.

### Solution B: Simple Loop Migration
Write a dumb, linear script to convert files. No Docker, no `joblib`.

## Recommended Action
Adopt Solution A if stakeholders agree to lose old artifacts (usually fine for research). Otherwise Solution B.
**Decision**: We will proceed with **Solution B (Simple Loop)** but prioritize deletions where safe, as "Delete & Re-run" might be too aggressive for all developers without checking. However, we will definitely **Delete Archive Scripts**.

## Acceptance Criteria
- [ ] `scripts/archive/` deleted.
- [ ] Migration script simplified (no joblib/docker).

## Work Log
- 2026-02-05: Identified during plan review.
