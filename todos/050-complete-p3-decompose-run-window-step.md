---
status: complete
priority: p3
issue_id: "050"
tags: [refactoring, architecture]
dependencies: []
---

# Problem Statement
`BacktestEngine._run_window_step` was becoming a God Method handling multiple pipeline stages.

# Findings
- Method handles filtering, regime detection, selection, synthesis, and allocation orchestration.

# Proposed Solutions
1. Extract stages into private helper methods (`_execute_selection`, `_execute_synthesis`, etc.).

# Acceptance Criteria
- [x] `_run_window_step` is reduced to high-level orchestration calls.
- [x] Sub-pillars are handled by dedicated methods.

# Work Log
- 2026-02-07: Completed decomposition of `BacktestEngine` methods. `_run_window_step` now delegates to `_execute_selection`, `_execute_synthesis`, and `_execute_allocation`.
