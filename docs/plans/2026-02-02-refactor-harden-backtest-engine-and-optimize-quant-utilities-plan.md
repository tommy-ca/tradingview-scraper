---
title: "refactor: Harden BacktestEngine and optimize quant utilities"
type: refactor
date: 2026-02-02
---

# refactor: Harden BacktestEngine and optimize quant utilities

## Overview
This plan addresses technical debt and architectural regressions identified during the PR #3 code review. The focus is on ensuring thread-safety in recursive meta-portfolio simulations, reducing parameter bloat through encapsulation, and further optimizing Numba JIT performance.

## Problem Statement / Motivation
1.  **Global State Pollution**: `BacktestEngine` currently manipulates `os.environ` and clears global caches during recursive sleeve simulations, which is not thread-safe and will cause race conditions in parallel Ray/multiprocessing execution.
2.  **Parameter Bloat**: Extracted helper methods like `_process_optimization_window` accept up to 20 parameters, violating best practices for maintainability and testability.
3.  **Performance Bottlenecks**: Buffer allocations inside Numba JIT loops and lack of input validation for permutation entropy calculations present scaling risks.
4.  **Brittle Logic**: The data loader uses nested loops for "fuzzy" file searching instead of deterministic path resolution.

## Proposed Solution
1.  **Dependency Injection (DI)**: Refactor `BacktestEngine` and `get_settings` to allow explicit configuration passing, eliminating the need for `os.environ` mutations and thread-unsafe cache clearing.
2.  **Stateful Orchestrator Pattern**: Use instance variables on `BacktestEngine` to store common configurations and accumulators, significantly reducing method parameter counts without adding complex "Context" or "Param" objects.
3.  **Solver-Side Hardening**: Extract "Adaptive Ridge" and "Sanity Veto" logic into a reusable decorator for allocation solvers, decoupling risk management from the backtest coordination loop.
4.  **JIT Hardening**: Pre-allocate Numba buffers outside the hot loop using the "Out" parameter pattern to eliminate GC pressure.

## Technical Considerations
- **Architecture**: Prioritize clarity and explicit state management over clever "Context Managers" or global side effects.
- **Performance**: Maintain O(1) complexity for permutation entropy while reducing GC pressure via buffer reuse.
- **Security**: Utilize `is_relative_to` for more robust path anchoring in `SecurityUtils`.

## Acceptance Criteria
- [ ] `BacktestEngine` accepts an explicit `settings` object and no longer modifies `os.environ`.
- [ ] `_process_optimization_window` parameter count is reduced by ~50% via instance state consolidation.
- [ ] Adaptive Ridge logic is moved into a solver-side decorator or wrapper.
- [ ] `permutation_entropy` JIT loop uses the "Out" parameter pattern for pre-allocated buffers.
- [ ] All methods in `backtest_engine.py` have complete, modern return type hints (`list[T] | None`).
- [ ] All related tests pass under parallel execution without race conditions.

## Implementation Phases

### Phase 1: Foundation & Utilities
- Create `tradingview_scraper/utils/data_utils.py` for shared datetime/timezone logic.
- Update `SecurityUtils` to use `is_relative_to`.
- Refactor `BacktestEngine.load_data` for deterministic resolution.

### Phase 2: Engine Refactoring (DI & Stateful Orchestration)
- **Isolate Configuration (Dependency Injection)**:
  - Add explicit `settings` parameter to `BacktestEngine.__init__`, defaulting to `get_settings()`.
  - Update `TradingViewScraperSettings` to allow constructor-based clones with overrides for `profile` and `manifest_path`.
- **Consolidate Engine State**:
  - Move constant configs (`synthesizer`, `ledger`, `lightweight`, `sim_names`) and accumulators (`results`, `return_series`) to `BacktestEngine` instance variables during `run_tournament`.
  - Refactor `_process_optimization_window` and `_run_simulation` to utilize this instance state.
- **Eliminate Global Side Effects**:
  - Replace `os.environ` mutation and `cache_clear()` with explicit child-engine instantiation using injected settings.
  - Remove dead `_get_sleeve_returns`.

### Phase 3: Solver & Performance Hardening
- **Solver Decorators**:
  - Implement `RidgeHardening` and `SanityVeto` decorators in `tradingview_scraper/portfolio_engines/base.py`.
  - Wrap allocation solvers with these decorators to handle numerical stability outside the backtest loop.
- **Numba Buffer Optimization**:
    - Refactor `_get_rs_jit` and `_calculate_permutation_entropy_jit` in `predictability.py` to use the **"Out" parameter pattern**.
    - Implement zero-copy handoff using `.to_numpy()` and enforce memory contiguity via `np.ascontiguousarray()`.


### Phase 4: Quality & Polish
- Move local imports to module level.
- Standardize all return type hints.
- Final regression testing.
