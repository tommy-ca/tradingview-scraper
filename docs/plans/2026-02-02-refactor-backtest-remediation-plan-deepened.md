---
title: "refactor: Remediate technical debt and architectural flaws in Backtest Engine (Deepened - Final)"
type: refactor
date: 2026-02-02
---

# refactor: Remediate technical debt and architectural flaws in Backtest Engine

## Enhancement Summary

**Deepened on:** 2026-02-02
**Finalized via:** DHH-Architect, Kieran-Python, Code-Simplicity parallel review.

### Final Design Decisions
1.  **Look-Ahead Purge**: Total deletion of `harden_solve`. Numerical hardening is now iterative and restricted to training data properties (Kappa bounds).
2.  **Majestic Monolith Alignment**: Core engine moved to `tradingview_scraper.backtest.engine`. `DataLoader` implemented as a functional module, not a stateful service.
3.  **Minimalist Numerical Workspace**: Retained for "Zero-Allocation" compliance but restricted to a simple `dataclass` of pre-allocated buffers. No management logic or factories.
4.  **Institutional Security**: Inlined `pathlib.resolve()` + `is_relative_to()` guards in the `DataLoader`.
5.  **Strict Type Narrowing**: Full Python 3.10+ syntax (builtin generics, pipe operator). Narrowed `SimulationContext` to eliminate `Any`.

---

## Problem Statement / Motivation

The recent "Hardening" refactor introduced critical regressions:
1.  **Intellectual Dishonesty**: `harden_solve` used future data (`test_rets`) to veto past windows (Look-ahead bias).
2.  **Packaging Spaghetti**: Core logic resided in `scripts/`, creating circular dependencies.
3.  **Performance Debt**: High-frequency allocations in JIT loops and unboxing overhead.
4.  **Security Risks**: Insecure `pd.read_pickle` without anchoring.

## Proposed Solution

### 1. Numerical Purity & Hardening
- **Consolidate `@ridge_hardening`**: Move retry logic into a single, robust decorator in `tradingview_scraper/portfolio_engines/base.py`. Retries are triggered purely by Training Set properties (Condition Number $\kappa > 5000$).
- **Minimalist `NumericalWorkspace`**: Pre-allocate buffers (`returns`, `weights`, `equity_curve`) once per backtest run.
- **Zero-Allocation Kernels**: Refactor JIT cores (`_get_rs_jit`, etc.) to handle NaNs internally, removing redundant data copying.

### 2. Architectural Refinement
- **Library Core Migration**: Move `BacktestEngine` to `tradingview_scraper.backtest.engine`.
- **Functional `DataLoader`**: Extract loading logic into a stateless `tradingview_scraper.data.loader` module.
- **Unify Metrics**: Merge script-local annualization logic into the library core.

### 3. Institutional Security
- **Path Anchoring**: Enforce `is_relative_to` checks at the `DataLoader` boundary.
- **Parquet Transition**: Mandate migration of backtest artifacts from Pickle to Parquet.

## Implementation Plan

### Phase 1: Foundation & Namespace (P1)
- [ ] Move `BacktestEngine` to `tradingview_scraper.backtest.engine`.
- [ ] Move `SimulationContext` and `StrategyFactory` to library; narrow all types.
- [ ] Implement `NumericalWorkspace` dataclass (minimalist buffers only).

### Phase 2: Numerical Purity & Hardening (P1)
- [ ] Refactor `@ridge_hardening` to handle retries internally (Condition-number based).
- [ ] Delete `harden_solve` and all look-ahead peeking logic.
- [ ] Refactor JIT kernels for zero-allocation NaN handling and buffer reuse.

### Phase 3: Data & Structural Cleanup (P1/P2)
- [ ] Implement functional `DataLoader` with inlined path anchoring.
- [ ] Unify `detect_annualization_factor` in `utils/metrics.py`.
- [ ] Remove redundant decorators from `SkfolioEngine`.

### Phase 4: Validation & Parity (P2)
- [ ] Implement Parquet artifact loading.
- [ ] Verify "Bit-Exact" parity for optimized kernels.
- [ ] Final docstring audit (Args/Returns/Audit format).

## Success Metrics
- 100% elimination of look-ahead bias.
- Institutional-grade numerical stability (Kappa < 5000).
- 30%+ reduction in backtest latency for large asset universes.
- 0 circular dependencies between `scripts/` and library.
