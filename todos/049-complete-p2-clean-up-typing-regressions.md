---
status: complete
priority: p2
issue_id: "049"
tags: [quality, typing]
dependencies: []
---

# Problem Statement
The recent refactor introduced minor typing regressions and redundant casts.

# Findings
- `Optional` used in `audit.py` without being imported.
- Redundant `cast(pd.Timestamp, ...)` in `engine.py`.

# Proposed Solutions
1. Fix imports in `audit.py`.
2. Remove redundant casts in `engine.py`.

# Acceptance Criteria
- [ ] No LSP errors in `audit.py` or `engine.py`.
