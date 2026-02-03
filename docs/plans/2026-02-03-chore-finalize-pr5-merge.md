---
title: "chore: Finalize PR #5 Merge and Post-Merge Cleanup"
type: chore
date: 2026-02-03
---

# chore: Finalize PR #5 Merge and Post-Merge Cleanup

## Overview
This plan focuses on the final verification steps required to safely merge PR #5 (`refactor/backtest-remediation`) and the immediate post-merge cleanup tasks. It ensures that the significant architectural changes (Library promotion of BacktestEngine, Parquet transition) do not disrupt ongoing operations.

## Problem Statement
PR #5 implements critical security and architectural fixes but leaves some loose ends:
1.  **Incomplete Script Migration**: While the core engine uses Parquet/DataLoader, numerous research scripts in `scripts/` still rely on `pd.read_pickle`.
2.  **Stale Todo State**: Several P1 todos (026, 029) are technically resolved but remain `pending` in the tracking system.
3.  **Documentation Gap**: `AGENTS.md` and developer guides need to reflect that `backtest_engine.py` is now a thin wrapper.

## Proposed Solution
1.  **Pre-Merge Verification**:
    -   Confirm CI passes on PR #5.
    -   Mark stale P1 todos as complete.
2.  **Merge Execution**:
    -   Merge PR #5 to main.
3.  **Post-Merge Cleanup (Immediate Follow-up)**:
    -   Create a new P2 plan to systematically migrate all 70+ research scripts to use `DataLoader` or `pd.read_parquet`.
    -   Update `AGENTS.md` command references.

## Technical Considerations
- **No Code Changes**: This plan avoids modifying the codebase further to prevent merge conflicts. It focuses on state management and documentation.
- **Dependency**: Relies on GitHub CI status for PR #5.

## Acceptance Criteria
- [ ] PR #5 is merged.
- [ ] Todos 026 and 029 are marked `complete`.
- [ ] A new plan file `2026-02-03-refactor-migrate-scripts-to-parquet.md` is created to track the script migration.

## Success Metrics
- Clean main branch with no regression in backtest functionality.
- Correct reflection of system state in `todos/` directory.

## Dependencies & Risks
- **Risk**: Merging PR #5 might temporarily break local research workflows if developers have local pickle files but the engine now defaults to Parquet. The `DataLoader` fallback to pickle mitigates this for now.

## References
- PR #5: https://github.com/tommy-ca/tradingview-scraper/pull/5
- Todo 039: Phase out pickle (Completed in Engine, Pending in Scripts)
