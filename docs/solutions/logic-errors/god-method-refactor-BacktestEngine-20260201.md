---
category: logic-errors
tags: [refactoring, srp, backtest-engine, clean-code]
module: backtest
symptoms: [maintenance-overhead, god-method, srp-violation]
---

# BacktestEngine God Method Refactoring

## Problem
The `BacktestEngine.run_tournament` method had evolved into a 450-line "God Method" that violated the Single Responsibility Principle (SRP). It was responsible for:
1.  Loading and validating data.
2.  Handling fractal meta-portfolio recursion.
3.  Dynamic universe filtering.
4.  Market regime detection.
5.  Pillar 1: Universe Selection (HTR).
6.  Pillar 2: Strategy Synthesis.
7.  Pillar 3: Portfolio Optimization (Adaptive Ridge logic).
8.  Backtest Simulation and metrics collection.
9.  Artifact persistence.

This complexity made it impossible to unit test individual components of the tournament flow and significantly increased the risk of side effects during feature updates.

## Root Cause
Initial development focused on rapid feature delivery. As new capabilities like **Adaptive Ridge Reloading**, **Fractal Backtesting**, and **Market Regime Detection** were added, they were implemented inline within the main rolling-window loop to minimize architectural friction. Over time, this cumulative growth resulted in a monolithic method that was difficult to navigate and debug.

## Solution
The method was modularized into a suite of private helpers, each with a single, well-defined responsibility. The main `run_tournament` method now acts purely as an orchestrator.

### 1. Extracted Orchestration Helpers
- **`_prepare_meta_returns`**: Isolated the recursive logic for meta-portfolio backtesting.
- **`_apply_dynamic_filter`**: Encapsulated the logic for filtering candidates based on the `features_matrix` ratings.
- **`_detect_market_regime`**: Wrapped the regime detection logic, providing a clean interface for environment identification.

### 2. Optimization Decomposition
The core optimization loop was moved to **`_process_optimization_window`**, which further delegates tasks:
- **`_apply_diversity_constraints`**: Handles weight clipping (25% caps) and normalization.
- **`_get_equal_weight_flat`**: Provides fallback logic for unstable windows.

### 3. Simulation & Persistence
- **`_run_simulation`**: Manages the interaction with the simulator build system, state tracking for holdings, and metrics sanitization.
- **`_save_tournament_artifacts`**: Centralized the logic for persisting stitched return streams and aliases.

## Results
- **Readability**: `run_tournament` was reduced from ~450 lines to ~140 lines of high-level orchestration logic.
- **Maintainability**: New optimization engines or filtering logics can now be added to their respective helpers without touching the main loop.
- **Testability**: Private methods can now be targeted for internal validation, and the simplified main loop is easier to verify via integration tests.

## Related Components
- `tradingview_scraper/portfolio_engines/` (Pillar 3 Solvers)
- `tradingview_scraper/selection_engines/` (Pillar 1 Selection)
- `tradingview_scraper/utils/synthesis.py` (Pillar 2 Synthesis)
