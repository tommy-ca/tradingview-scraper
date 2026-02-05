---
status: pending
priority: p3
issue_id: "081"
tags: [refactor, simplification, architecture]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The plan proposes using Docker sandboxing and `joblib` parallelization for the migration script. Reviewers flagged this as "Security Theater" and "Premature Optimization".

## Findings
- **Reviewer**: DHH Rails Reviewer / Simplicity Reviewer
- **Issue**: Over-engineering simple maintenance task.

## Proposed Solutions

### Solution A: Simplify Script (Recommended)
Remove `joblib` dependency. Use a simple loop. Remove Docker requirement from plan.

## Recommended Action
Update plan and script to remove unnecessary complexity.

## Acceptance Criteria
- [ ] Migration script uses simple loop (easier to debug).
- [ ] Plan updated to remove Docker requirement.

## Work Log
- 2026-02-05: Identified during plan review.
