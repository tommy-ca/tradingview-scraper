# Crypto Sleeve Requirements Specification v3.3.1

## 1. Overview

### 1.1 Purpose
Define the institutional requirements for the crypto production sleeve within the multi-sleeve meta-portfolio architecture.

### 1.2 Scope
This specification covers the crypto asset discovery, selection, optimization, and backtesting infrastructure for BINANCE-only production deployment using the `uv` native workflow.

### 1.3 Status
**Production Certified** (2026-01-11) - Deep Audit Standard v3.3.1.

---

## 2. Functional Requirements

### 2.11 Dynamic Regime Adaptation & Risk Hardening
| Requirement ID | Priority | Status | Description |
|----------------|----------|--------|-------------|
| CR-110 | MUST | ✅ | **Regime Analysis V3**: Analyze returns for Tail Risk (MaxDD, VaR) and Alpha Potential (Momentum, Dispersion). |
| CR-114 | MUST | ✅ | **Alpha Immersion Floor**: The history floor for crypto assets is set to 90 days for production; this maximizes participation of high-momentum listings while maintaining statistical validity. |
| CR-116 | MUST | ✅ | **Antifragility Significance**: Antifragility scores must be weighted by a significance multiplier ($\min(1.0, N/252)$) to prevent low-history assets from dominating the ranking. |
| CR-115 | MUST | ✅ | **Cluster Diversification standard**: The selection engine must pick up to the Top 5 assets per direction (Long/Short) within each cluster to prevent single-asset factor concentration. |
| CR-181 | MUST | ✅ | **Directional Normalization Standard**: Returns matrices passed to risk and selection engines must be "Alpha-Aligned" (Synthetic Long) by inverting returns for assets identified as SHORT in the current window ($R_{synthetic} = \text{sign}(M) \times R_{raw}$). |
| CR-182 | MUST | ✅ | **Late-Binding Directional Assignment**: Asset direction must be dynamically determined at each rebalance window using recent momentum to ensure factor purity and protect against regime drift. |
| CR-183 | MUST | ✅ | **Direction-Blind Portfolio Engines**: All allocation engines (HRP, MVO, Barbell) must operate on the normalized "Synthetic Long" matrix, ensuring consistent logic across all strategy types without direction-specific code paths. |
| CR-184 | MUST | ✅ | **Simulator Reconstruction**: Backtest simulators must utilize the `Net_Weight` derived from synthetic weights and assigned directions ($W_{net} = W_{synthetic} \times \text{sign}(M)$) to execute trades correctly. |
| CR-190 | MUST | ✅ | **TDD Hardening**: Critical risk components (inversion, direction assignment) are protected by unit tests to ensure logical integrity. |
| CR-191 | MUST | ✅ | **Feature Flag Control**: Experimental risk features are gated behind specific toggles in `TradingViewScraperSettings` to allow for safe production rollouts. |
| CR-210 | MUST | ✅ | **Selection Scarcity Resilience**: The pipeline must implement the Selection Scarcity Protocol (SSP) to handle windows where high-resolution filters (Entropy Order=5) yield sparse winner pools (n < 3). |
| CR-211 | MUST | ✅ | **Solver Tolerance**: Optimization engines must implement explicit error handling and fallback logic for solver-specific failures (e.g., CVXPY infeasibility, skfolio recursion) triggered by low asset counts. |
| CR-212 | MUST | ✅ | **Balanced Selection Standard**: The selection engine must ensure a minimum pool of 15 candidates per window by falling back to the top-ranked rejected assets (by alpha score) if primary filters are too restrictive. |
| CR-213 | MUST | ✅ | **Global Metadata Fallback**: To prevent "Sparsity Vetoes" of high-alpha assets, the pipeline must provide default execution parameters (tick_size, lot_size) for recognized exchange classes (e.g., BINANCE_SPOT) if local metadata is missing. |
| CR-200 | MUST | ✅ | **Deep Forensic Reporting**: Every tournament must generate a human-readable "Deep Forensic Report" tracing the Five-Stage Funnel and providing window-by-window portfolio snapshots. |

---

**Status**: ✅ All requirements satisfied, validated and hardened for Q1 2026 Production.
