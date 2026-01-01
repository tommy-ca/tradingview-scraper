# Market Profile Unification & Validation (Jan 2026)

This document details the transition from a standalone `market` engine to a unified `market` profile supported by all optimization engines.

## 1. Architectural Shift

Previously, the institutional benchmark was handled by a special-case `MarketBaselineEngine`. This created duplication in rebalancing and backtesting logic.

**New Standard**: The institutional benchmark is now a native `market` profile implemented in the base optimization class (`CustomClusteredEngine`).

| Feature | Legacy Implementation | Unified Implementation |
| :--- | :--- | :--- |
| **Engine Class** | `MarketBaselineEngine` | Integrated into all engines |
| **Profile Name** | `equal_weight` (special case) | `market` |
| **Universe** | Fixed SPY (hardcoded fallback) | `settings.benchmark_symbols` |
| **Parity** | Engine-specific | Guaranteed across all engines |

## 2. Implementation Details

The `market` profile logic follows these steps:
1.  **Symbol Filtering**: Filter the available training returns to only those found in `settings.benchmark_symbols`.
2.  **Fallback**: If no benchmark symbols are found in the returns matrix, the engine falls back to an equal-weight allocation across the entire active universe (ensuring continuity).
3.  **Equal Weighting**: Assign $1/N$ weight to all target symbols.
4.  **Metadata Tagging**: All benchmark assets are tagged with `Cluster_ID: MARKET_BENCHMARK`.

## 3. Validation

### A. Unit Testing
The implementation was validated using `tests/test_market_profile.py`:
- **`test_market_profile_parity`**: Confirmed that `custom`, `skfolio`, `riskfolio`, and `cvxportfolio` produce bit-identical weights for the `market` profile.
- **`test_multi_asset_market_profile`**: Validated that multi-asset benchmarks (e.g., SPY + QQQ) are correctly equal-weighted.
- **`test_market_profile_fallback`**: Verified graceful fallback behavior when benchmark data is missing.

### B. Integration Testing
A tournament run was executed comparing all engines using the `market` profile.
- **Result**: All simulators reported identical returns and turnover for the benchmark, confirming the elimination of "Simulator Bias" for the control group.

## 4. Conclusion
The unified `market` profile simplifies the codebase while providing a more robust and transparent mechanism for simulator calibration and institutional benchmarking.
