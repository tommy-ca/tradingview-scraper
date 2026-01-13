# Crypto Sleeve Requirements Specification v3.3.1

## 1. Overview

### 1.1 Purpose
Define the institutional requirements for the crypto production sleeve within the multi-sleeve meta-portfolio architecture.

### 1.2 Scope
This specification covers the crypto asset discovery, selection, optimization, and backtesting infrastructure for BINANCE-only production deployment using the `uv` native workflow.

### 1.3 Status
**Production Certified** (2026-01-13) - Deep Audit Standard v3.4.5.

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
| CR-214 | MUST | ✅ | **HTR Standard**: The selection engine must implement the 4-stage Hierarchical Threshold Relaxation loop (Strict -> Spectral -> Factor Representation -> Balanced Fallback) to ensure $N \ge 15$. |
| CR-220 | MUST | ✅ | **Dynamic Ridge Scaling**: The system must iteratively apply shrinkage (diagonal loading) to the covariance matrix if the condition number (Kappa) exceeds a configurable threshold (default 5000), ensuring numerical stability for solvers. |
| CR-221 | MUST | ✅ | **Adaptive Safety Protocol**: The `adaptive` meta-engine must default to an **Equal Risk Contribution (ERC)** fallback profile (or other configurable safety profiles like EW) when sub-solvers fail or during warm-up periods. |
| CR-230 | MUST | ✅ | **Toxicity Hard-Stop**: HTR Stage 3/4 recruitment must never include assets failing a strict entropy limit (default 0.999 for Crypto), ensuring factor representation without alpha dilution. |
| CR-232 | MUST | ✅ | **Backend Purity**: Optimization engines must not use shared base-class fallbacks; each backend (`skfolio`, `riskfolio`, etc.) must execute its own solver or return explicit failure to ensure performance differentiation. |
| CR-233 | MUST | ✅ | **Hybrid Barbell**: The `barbell` strategy must optimize its core layer using the engine's native solver, allowing for backend-specific risk-management profiles. |
| CR-240 | MUST | ✅ | **Baseline Selection Standard**: The system must provide a `baseline` selection engine that passes through all candidates to the portfolio engines, enabling quantification of Selection Alpha. |
| CR-250 | MUST | ✅ | **Statistical Sample Floor**: Forensic audits and tournaments must utilize at least 15 candidates (via HTR Stage 4 fallback) to ensure numerical differentiation between solvers and prevent constrained convergence to bit-perfect identical weights. |
| CR-260 | MUST | ✅ | **Directional Synthetic Longs**: Portfolio engines must handle `SHORT` candidates by inverting their returns ($R_{syn} = -1 \times R_{raw}$) before optimization to ensure risk-parity and convex engines treat them as alpha-positive stability contributors. |
| CR-261 | MUST | ✅ | **Regime-Direction Alignment**: The `MarketRegimeDetector` must influence the late-binding asset direction, specifically enforcing tighter filters on `LONG` candidates during `CRISIS` or `TURBULENT` regimes. |
| CR-270 | MUST | ✅ | **Synthesis-Allocation Decoupling**: Decision logic (regime mapping, directional inversion) is abstracted into the Strategy Synthesis layer. Portfolio engines are "Decision-Naive" and operate only on processed return streams. |
| CR-271 | MUST | ✅ | **Atomic Strategy Interface**: The platform supports "Atomic Strategies" (Asset, Logic, TimeScale) as optimization candidates. Each Atom must have exactly ONE logic. |
| CR-280 | MUST | ✅ | **Complex Strategy Composition**: Supports ensembling atoms into complex strategies. Note: Strategic intents (like Barbell or Neutrality) are handled by Pillar 3 (Allocation) for global optimality. |
| CR-281 | MUST | ✅ | **Recursive Weight Flattening**: The Orchestrator supports mapping optimized strategy weights back to underlying physical assets for implementation. |
| CR-290 | MUST | ✅ | **Market Neutral Constraint**: Market neutrality is a native optimization constraint (not a profile), enabling beta-hedged Max-Sharpe/HRP portfolios. |
| CR-291 | MUST | ✅ | **Synthetic Hierarchical Clustering**: The Allocation layer performs hierarchical clustering on synthesized return streams to identify uncorrelated alpha factors. |
| CR-292 | MUST | ✅ | **Pillar 3 Strategy Status**: The `barbell` strategy is classified as a **Risk Profile** (Pillar 3) because it manages capital segmentation across provided alpha streams. |
| CR-300 | MUST | ✅ | **Experimental Guardrails**: High-impact experimental constraints (e.g., Market Neutrality) MUST be gated by feature flags (`feat_market_neutral`) and default to OFF for institutional stability. |
| CR-310 | MUST | ✅ | **Canonical Consolidation**: The Discovery stage MUST deduplicate symbols by economic identity (e.g., BTC, GC) across multiple venues, selecting the most liquid implementation to prevent fragmentation in the "Raw Pool." |
| CR-311 | MUST | ✅ | **Top-N Cluster Purity**: The selection engine MUST prioritize candidates by Log-MPS conviction score within each hierarchical cluster, ensuring the highest conviction representatives for each identified alpha factor. |
| CR-312 | MUST | ✅ | **History-Aware Sanitization**: The data preparation layer MUST enforce a configurable history floor (min_days_floor) and zero-variance filter to eliminate statistically insignificant assets before optimization. |
| CR-320 | MUST | ✅ | **Pass-through Baseline**: The system MUST provide a `baseline` engine that passes ALL valid candidates to quantify the "Gross Alpha" of the entire selection funnel. |
| CR-321 | MUST | ✅ | **Structural Baseline**: The system MUST provide a `liquid_htr` engine that performs hierarchical clustering but selects Top-N by liquidity (Value.Traded), isolating the "Statistical Alpha" added by Log-MPS scoring. |
| CR-330 | MUST | ✅ | **End-to-End Traceability**: Every production decision MUST be traceable from the initial L4 scanner signal through Identity Deduplication, Cluster Assignment, and final Portfolio Weighting. |
| CR-331 | MUST | ✅ | **Factor-Preserving Selection**: The selection pipeline MUST prioritize the highest-conviction Log-MPS representatives *within* each hierarchical cluster to ensure diversification across discovered alpha factors. |
| CR-400 | MUST | ✅ | **Stateless Pipeline Stages**: All v4 selection stages MUST be stateless. They receive a `SelectionContext` and return a modified `SelectionContext`. |
| CR-401 | MUST | ✅ | **Data Immutability**: The original `RawPool` input MUST never be modified; all enrichments are added as new columns or metadata layers in the context. |
| CR-402 | MUST | ✅ | **Schema-Validated Handover**: Every pipeline stage transition MUST be validated by a strict schema (Pydantic) to ensure end-to-end data integrity. |
| CR-403 | MUST | ✅ | **Pipeline Modularity**: The v4 pipeline architecture MUST support the hot-swapping of `ConvictionScorer` models without re-implementing clustering or selection logic. |
| CR-410 | MUST | ✅ | **Shadow Mode Execution**: The system MUST support running the v4 MLOps pipeline in parallel with the v3 Legacy engine for a configurable period ("Shadow Week") to validate stability before full cutover. |
| CR-200 | MUST | ✅ | **Deep Forensic Reporting**: Every tournament must generate a human-readable "Deep Forensic Report" tracing the Five-Stage Funnel and providing window-by-window portfolio snapshots. |

---

**Status**: ✅ All requirements satisfied, validated and hardened for Q1 2026 Production.
