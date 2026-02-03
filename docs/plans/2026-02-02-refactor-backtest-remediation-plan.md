---
title: "refactor: Remediate technical debt and architectural flaws in Backtest Engine"
type: refactor
date: 2026-02-02
---

# refactor: Remediate technical debt and architectural flaws in Backtest Engine

## Overview

This plan outlines the systematic remediation of technical debt and architectural flaws identified in the `BacktestEngine` and core quantitative utilities. The focus is on ensuring absolute backtest integrity by removing look-ahead bias, consolidating numerical hardening logic into pure library decorators, and hardening the security of the data loading layer.

## Problem Statement / Motivation

The recent "Hardening" refactor in PR #4, while improving performance and thread-safety, introduced several regressions:
1.  **Stop-Ship Logic Flaw**: The `harden_solve` utility uses out-of-sample (OOS) data to veto windows, creating critical look-ahead bias.
2.  **Redundancy**: Multiple layers of nested retry loops exist between the engine and decorators, leading to inefficient execution.
3.  **Encapsulation Leaks**: Core library logic (annualization, data loading) is leaking into the `scripts/` layer, and cross-package imports break boundaries.
4.  **Security Risks**: Remaining `pd.read_pickle` calls on potentially untrusted paths represent a remote code execution (RCE) vector.

## Proposed Solution

1.  **Numerical Purity & Decorator Consolidation**:
    -   **Delete `harden_solve` utility**: Remove the toxic look-ahead "Window Veto" logic immediately.
    -   **Consolidate `@ridge_hardening`**: Move all numerical stability retries into a single, robust decorator in `tradingview_scraper/portfolio_engines/base.py`. Retries will be based strictly on training data properties (e.g., matrix condition number `Kappa < 5000`) or solver convergence signals.
    -   **Pure `@sanity_veto`**: Implement post-optimization weight stability checks (variance, sum checks) without peeking at OOS returns.

2.  **Architectural Refinement (The Omakase Way)**:
    -   **Extract `DataLoader`**: Move the complex loading logic from `BacktestEngine.load_data` into a functional `tradingview_scraper.data.loader` module. Centralize path resolution, deterministic priority, and UTC standardization.
    -   **Unify Metrics**: Consolidate all annualization and frequency detection logic into `tradingview_scraper/utils/metrics.py`, incorporating the robust hourly detection from the script layer.
    -   **Model Migration**: Move `SimulationContext` to `tradingview_scraper/backtest/models.py` and `StrategyFactory` to `tradingview_scraper/backtest/strategies.py`.

3.  **Institutional Security**:
    -   **Path Anchoring**: Replace `pd.read_pickle` with Parquet where possible. For remaining loads, use an `ensure_safe_path` utility that enforces `is_relative_to` anchoring against allowed root directories.
    -   **Whitelist Validation**: Enforce strict sanitization for all user-provided inputs (`run_id`, `symbol`) using the centralized `SecurityUtils`.

4.  **Pythonic Excellence (Modern Standards)**:
    -   **Type Hinting**: Fully upgrade all modified files to Python 3.10+ syntax (using `dict[]`, `list[]`, and `| None` instead of `Dict`, `List`, `Optional`).
    -   **Docstring Audit**: Add comprehensive "Args/Returns/Audit" docstrings to all new library functions.

## Technical Considerations

-   **Zero-Allocation Standard**: Refactoring must preserve the performance gains achieved via Numba "Out" parameters and scalar tracking.
-   **Parallel Safety**: Ensure all new components maintain thread-safety for Ray/multiprocessing execution.
-   **Dependency Integrity**: Resolve all circular dependencies between `scripts/` and `tradingview_scraper/`.

## Acceptance Criteria

- [ ] `harden_solve` utility is removed; solvers are invoked directly through their hardened decorators.
- [ ] 100% elimination of OOS peeking in the optimization and hardening loops.
- [ ] `BacktestEngine` LOC is reduced by ~25% through logic delegation to the library.
- [ ] `DataLoader` successfully resolves latest runs and lakehouse data with deterministic priority.
- [ ] All type hints follow the Python 3.10+ builtin generics standard.
- [ ] All 11+ regression test suites pass with JIT enabled.

## Success Metrics

- Absolute backtest integrity (Zero look-ahead bias).
- Clean package boundaries between orchestration (scripts) and domain logic (library).
- Institutional-grade security for all filesystem operations.

## Implementation Plan (P1/P2)

### Phase 1: Numerical Purity & Type Hardening (P1)
- [ ] Consolidate `@ridge_hardening` logic and delete `harden_solve`.
- [ ] Upgrade `tradingview_scraper/portfolio_engines/base.py` to modern typing.
- [ ] Implement `ensure_safe_path` security utility.

### Phase 2: Structural Integrity (P1/P2)
- [ ] Extract `DataLoader` module and refactor `BacktestEngine.load_data`.
- [ ] Move models (`SimulationContext`) and factories into the library.
- [ ] Unify `_get_annualization_factor` in `utils/metrics.py`.

### Phase 3: Cleanup & Validation (P2)
- [ ] Remove redundant decorators from `SkfolioEngine`.
- [ ] Standardize docstrings and final typing cleanup across modified files.
- [ ] Run full regression and parallel stability tests.
