---
status: complete
priority: p3
issue_id: "050"
tags: [refactoring, architecture]
dependencies: []
---

# Problem Statement
`BacktestEngine._run_window_step` is becoming a God Method handling multiple pipeline stages.

# Findings
- Method handles filtering, regime detection, selection, synthesis, and allocation orchestration.

# Proposed Solutions
1. Extract stages into private helper methods (`_execute_selection`, `_execute_synthesis`, etc.).

# Acceptance Criteria
- [ ] `_run_window_step` is reduced to high-level orchestration calls.
