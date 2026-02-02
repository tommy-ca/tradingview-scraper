---
category: logic-errors
tags: [architecture, decorators, srp, numerical-stability]
module: RiskLayer
symptoms: [parameter-bloat, mixed-responsibilities, backtest-failure]
---

# Refactoring Numerical Stability: Solver Decorator Pattern

## Problem
The backtest orchestration loop was suffering from **parameter bloat** and **mixed responsibilities**. Mathematical hardening logic (Adaptive Ridge) and stability checks (Sanity Veto) were implemented inline within the core loop, making it brittle and difficult to maintain.

## Root Cause
- **Inline Hardening**: The orchestrator had to manage low-level retry logic for ill-conditioned covariance matrices.
- **Coupling**: Risk management logic was tightly coupled with time-stepping logic.

## Solution
Implemented a **Decorator Pattern** for allocation solvers to encapsulate numerical hardening and stability validation.

### 1. `@ridge_hardening`
Mathematically bounds the condition number of the covariance matrix. If optimization fails due to numerical divergence, the decorator automatically retries with progressively higher shrinkage intensities (0.50, 0.95).

### 2. `@sanity_veto`
Performs post-optimization validation on portfolio weights. If instability is detected (e.g., $W_{sum} \le 0$ or `NaN`), it flags the period for fallback to Equal Weight (EW).

## Impact
- **Decoupling**: Orchestration loop size reduced; logic now focuses purely on date handling.
- **Maintainability**: Parameter count in internal methods reduced by ~50% via instance state consolidation and decorator extraction.
- **Reusability**: Stability measures can be applied to any new solver with a single line of code.

## Related Issues
- `todos/017-pending-p1-parameter-bloat-optimization.md`
