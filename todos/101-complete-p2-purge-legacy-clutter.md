---
status: complete
priority: p2
issue_id: "101"
tags: [simplicity, cleanup, refactor]
dependencies: []
---

## Problem Statement
The codebase contains significant logic duplication and redundant orchestrators between legacy script wrappers and the new modular pipelines. This "split-brain" architecture increases maintenance cost and risk of drift.

## Findings
- **Issue**: Redundant entry points (Subprocess Make vs QuantSDK).
- **Issue**: Legacy scripts (e.g., `natural_selection.py`) carry logic that is now encapsulated in modular stages.
- **Impact**: ~1,850 lines of dead or redundant code identified by Simplicity Reviewer.

## Proposed Solutions

### Solution A: Ruthless Purge of Legacy Logic (Recommended)
Delete legacy script logic and replace them with thin wrappers around `QuantSDK`. Purge old selection engines (v2/v3) once v4 is fully certified.

## Recommended Action
Execute a simplicity sweep to remove identified legacy files.

## Acceptance Criteria
- [x] Legacy scripts in root are reduced to thin wrappers.
- [x] `scripts/archive/` is completely purged.

## Work Log
- 2026-02-07: Identified during simplicity audit.
- 2026-02-08: Resolved by Antigravity. Deleted redundant orchestrators and thinned main scripts.
