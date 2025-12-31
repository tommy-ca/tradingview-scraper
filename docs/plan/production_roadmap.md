# Production Roadmap: 2026 Quantitative Outlook

This roadmap outlines the strategic development goals for the TradingView Scraper quantitative platform for 2026, focusing on alpha expansion, execution intelligence, and institutional resilience.

## Q1 2026: Execution Intelligence & Churn Optimization (COMPLETED)

### 1. Advanced Rebalancing Logic
- **Drift-Aware Execution**: Upgraded `drift-monitor` with Partial Rebalancing and Order Generation.
- **Turnover Penalties**: Implemented L1-norm penalty in Custom Optimizer.
- **XS Momentum**: Transitioned to robust global percentile ranking.
- **Spectral Regimes**: Integrated `TURBULENT` state detection and Barbell scaling.

### 2. Immutable Audit & Reproducibility
- **Decision Ledger**: Implemented `audit.jsonl` with cryptographic chaining (SHA-256).
- **Data Hashing**: Implemented deterministic `df_hash` for verifiable data lineage.
- **Audit Orchestration**: Updated `run_production_pipeline.py` to wrap steps in audit blocks.
- **Integrity Verification**: Created `scripts/verify_ledger.py` to detect data tampering.

## Q2 2026: Strategy & Factor Expansion (PLANNED)


### 1. Relative Value & XS Momentum
- **Cross-Sectional (XS) Momentum**: Implement ranking logic to filter the universe based on relative performance (percentiles) rather than absolute technical thresholds.
- **Sector Rotation Engine**: Add first-class support for sector-level momentum analysis, allowing the optimizer to tilt towards outperforming industries.

### 2. Short Mean Reversion
- **Selling Rips**: Develop specialized configurations for identifying overbought assets within confirmed downtrends across Equities, Forex, and Crypto.

## Q3 2026: Spectral Intelligence & Regime Detection

### 1. Wavelet-Based Regime Detection
- **Spectral Turbulence**: Fully integrate Discrete Wavelet Transform (DWT) entropy metrics into the `MarketRegimeDetector` to identify non-stationary volatility shifts before they manifest in standard deviation metrics.
- **Regime-Specific Presets**: Create automated manifest profiles that trigger specialized constraints (e.g., tighter cluster caps) during `CRISIS` regimes.

## Q4 2026: Institutional Infrastructure

### 1. Manifest-Driven Orchestration
- **Universal Runner**: Replace remaining bash-based scan lists with a centralized manifest runner that supports concurrent execution, automated retries, and unified run-scoped logging.
- **Metadata Parity 2.0**: Implement real-time parity checking between the offline symbols catalog and TradingView's live data to prevent point-in-time mapping errors.

## Ongoing Maintenance
- **Data Resilience**: Continuous improvement of the self-healing `make recover` loop.
- **Optimizer Benchmarking**: Monthly "Tournament" runs to evaluate if third-party engines (`skfolio`, `Riskfolio`) are outperforming the `Custom` convex engine in realized Sharpe stability.
