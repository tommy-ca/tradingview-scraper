---
status: complete
priority: p1
issue_id: "048"
tags: [architecture, optimization, risk]
dependencies: []
---

# Problem Statement
Numerical stability retries are implemented redundantly across multiple layers (decorator, engine loop, and internal solver functions), leading to exponential waste.

# Findings
- `@ridge_hardening` in `base.py` performs retries.
- `CustomClusteredEngine._cov_shrunk` has its own `while` loop for shrinkage.
- `_solve_cvxpy` has recursive fallbacks.

# Proposed Solutions
1. Consolidate all retry logic into the `@ridge_hardening` decorator.
2. Make internal solver functions deterministic/single-pass.

# Acceptance Criteria
- [ ] Redundant loops removed from `custom.py`.
- [ ] `@ridge_hardening` is the single source of truth for stability retries.
