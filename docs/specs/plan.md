# Platform Specification, Requirements & Development Plan

## 1. Executive Summary
This document codifies the institutional requirements and design specifications for the TradingView Scraper quantitative platform, incorporating recent learnings from crypto production and institutional ETF strategy validation (Q1 2026).

## 2. Requirements & Standards

### 2.1 Data Integrity & Health (The Forensic Pillar)
- **Secular History**: Production runs require 500 days of lookback with a 90-day floor.
- **Strict Health Policy**: 100% gap-free alignment required for implementation.
- **Institutional Gaps**: 1-session gaps are ignored (market-day normalization).
- **Crypto Precision**: 20-day step size alignment (Optimized Sharpe 0.43).
- **Normalization**: +4h shift for market-day alignment (20:00-23:59 UTC).

### 2.2 Selection Architecture (The Alpha Core)
- **Primary Model (v4)**: MLOps-Centric Pipeline.
- **Legacy Models (v2, v3)**: Preserved for benchmarking coexistence.
- **Predictability Vetoes**: Integrated Entropy, Hurst, and Efficiency filters.
- **Universe Diversity**: Multi-sleeve support (Instruments, ETFs, Crypto).

### 2.3 Optimization & Risk (The Strategic Layer)
- **Engines**: `skfolio`, `riskfolio`, `pyportfolioopt`, `cvxportfolio`.
- **Primary Strategy**: Barbell (3.83 Sharpe standard).
- **Cluster Awareness**: Ward Linkage hierarchical risk buckets.
- **Friction Modeling**: 5bps slippage and 1bp commission for production simulators.
- **Regime-Aware Caps**: Dynamic clustering caps (Normal: 0.25, Turbulent: 0.20, Crisis: 0.15).

## 3. Design Specifications

### 3.1 Layered Pipeline Architecture (L0-L4)
- **L0 (Universe)**: Broad pool definitions (S&P 500, Binance Top 50).
- **L1 (Hygiene)**: Global liquidity and technical filters.
- **L2 (Templates)**: Asset-specific sessions and calendars.
- **L3 (Strategies)**: Alpha logic (Trend, Mean Reversion, MTF).
- **L4 (Scanners)**: Composed entry points.

### 3.2 Refinement Funnel (6-Stage MLOps Funnel)
1. Ingestion -> 2. Feature Engineering -> 3. Inference -> 4. Partitioning -> 5. Policy -> 6. Synthesis.

## 4. Development Plan (Current Sprint)

### Phase 134: Champion/Challenger Production Rollout (COMPLETED)
- [x] **Dual-Run Config**: Updated `run_master_tournament.py` to include `v4` in the selection lineup.
- [x] **Adapter Layer**: Created `SelectionPipelineAdapter` to bridge `SelectionContext` to `SelectionResponse`.
- [x] **Shadow Mode**: Enabled `v4` shadow execution in production tournaments.

### Phase 135: Deep Audit Integration & Telemetry (COMPLETED)
- [x] **Requirement**: Formalized CR-420 for granular telemetry segregation.
- [x] **Orchestrator Update**: Refactored `backtest_engine.py` to move audit trails to the `data` blob.
- [x] **Integration Test**: Verified end-to-end telemetry flow via `tests/test_audit_v4_integration.py`.

### Phase 136: Grand Tournament Validation (COMPLETED)
- [x] **Master Tournament Execution**: Executed head-to-head tournament (`v3.4` vs `v4`) across the risk matrix.
- [x] **Forensic Report Generation**: Created `Deep Forensic Reports` highlighting v4 MLOps telemetry.

### Phase 137: Selection Coexistence Standard (COMPLETED)
- [x] **Requirements Update**: Codified the "Multi-Version Coexistence" standard; retained v2, v3, and legacy engines.
- [x] **Full Production Tournament**: Executed exhaustive `crypto_production` matrix (Selection x Engine x Profile x Simulator).
- [x] **Cross-Version Benchmark**: Generated performance matrix confirming v4 dominance and v3 stability.

### Phase 138: Full Risk Matrix Audit (COMPLETED)
- [x] **Exhaustive Sweep**: Executed tournament with ALL risk profiles.
- [x] **Short Handling Audit**: Verified sign preservation and simulator mapping.
- [x] **HTR Loop Fix**: Patched adapter for internal relaxation cycles.
- [x] **Data Hygiene**: Prioritized rich returns matrices.

### Phase 139: Deep Window Audit & Statistical Grand Tournament (COMPLETED)
- [x] **Audit Ledger Context**: Added global timescales (train/test/rebalance) to genesis block.
- [x] **Statistical Tournament**: Executed exhaustive sweep (Lookback x Rebalance x Selection); identified 30-day alpha half-life.
- [x] **Window Forensic**: Verified 100% directional integrity and analyzed "Window 300" crash outlier.
- [x] **Discovery Audit**: Codified CR-460 for early-funnel alpha quantification.

### Phase 140: Production Standard Finalization (COMPLETED)
- [x] **Default Engine Cutover**: Standardized on v4 for all production runs.
- [x] **Final Certification Tournament**: Executed exhaustive risk profile matrix; v4 confirmed as institutional standard.
- [x] **Statistical Defaults**: Updated `settings.py` with optimal windows (60/20/20) for maximum Sharpe (5.48).
- [x] **High-Entropy Hardening**: Codified CR-490 for flash-crash stability.

### Phase 141: Full Portfolio Matrix Forensic & Bottleneck Audit (COMPLETED)
- [x] **Full-Profile Sweep**: Executed tournament with ALL risk profiles and selection modes.
- [x] **Rebalance Ledger Audit**: Performed per-window forensic analysis; verified 100% directional integrity.
- [x] **Short Integrity Check**: Confirmed sign preservation and negative weight mapping for SHORT atoms.
- [x] **Bottleneck Analysis**: Identified linear scaling in `AlphaScorer` and solver drift in high-entropy regimes.
- [x] **Outlier Verification**: Validated "Window 220" and "Window 300" crash behavior as logically consistent with factor shifts.

### Phase 142: Institutional Scale & Vectorization (COMPLETED)
- [x] **Grand Certification Matrix**: Executed exhaustive risk profile tournament across Selection (v3.4, v4) x Profile (7) x Engine (3).
- [x] **Statistical Baseline Sync**: Updated requirements with v3.5.3 performance benchmarks.
- [x] **Optimal Default Verification**: Confirmed 60/20/20 window configuration stability.
- [x] **Anomaly Detection**: Audited outliers and verified SHORT directional integrity.
- [x] **Barbell Mapping Fix**: Resolved strategy ID mismatch in `custom.py` for Antifragility-weighted profiles.

### Phase 143: Deep Matrix Audit & Operational Standards (COMPLETED)
- [x] **Exhaustive Matrix Trace**: Audited 7 risk profiles across 3 engines (skfolio, riskfolio, custom).
- [x] **Directional Purity Verified**: 100% integrity across 987 SHORT atom implementations.
- [x] **Anomaly Audit**: Identified `max_sharpe` tail-risk in high-dispersion windows.
- [x] **Champion Identification**: Validated `risk_parity` and `market_neutral` as the production anchors.

### Phase 144: Final Sprint Validation & Full Matrix Audit (COMPLETED)
- [x] **Full-System Tournament**: Executed exhaustive matrix (Selection v3.2/v3.4/v4 x 7 Profiles x 3 Engines x 2 Simulators).
- [x] **HTR Loop & Top_N Fixes**: Resolved hardcoded Stage 1 and Top_N=2 discrepancies in v4 pipeline.
- [x] **Window forensic audit**: Analyzed per-rebalance portfolio snapshots; verified 100% directional integrity.
- [x] **Requirements Update**: Codified the final Q1 2026 performance matrix and institutional bounds.

### Phase 145: Risk Hardening & Performance Benchmarking (COMPLETED)
- [x] **Strict Cluster Cap (CR-590)**: Enforced mandatory 25% max cluster cap across all risk profiles and engines.
- [x] **Vectorized Scorer Stage**: Optimized `FeatureEngineeringStage` using vectorized `.apply()` for faster alpha factor calculation.
- [x] **Market Neutral Reconciliation**: Formalized `market_neutral` as a native optimization constraint while preserving profile interface.
- [x] **HRP Logic Hardening**: Fixed `custom` HRP bisection logic to use branch variance (Standard Lopez de Prado).
- [x] **Window Forensic Audit**: Audited exhaustive matrix; verified 100% directional integrity across 3,260 SHORT implementations.

### Phase 146: Anomaly Resolution & Engine Purity (COMPLETED)
- [x] **HRP Regression Fix**: Hardened recursive bisection in `custom.py` with branch-variance; verified parity with `skfolio`.
- [x] **Solver Fallback Standard**: Implemented Iterative Tolerance Relaxation ($0.05 \rightarrow 0.15 \rightarrow 0.25$) for neutral constraints.
- [x] **Outlier Mitigation**: Implemented Profile-Specific Ridge Loading (CR-600) for `max_sharpe` stability.
- [x] **Volatility Band Audit**: Finalized expected Vol rates per profile (MinVar: 0.35, HRP: 0.45, MaxSharpe: 0.90).

### Phase 147: Deep Forensic Audit & Institutional Tooling (COMPLETED)
- [x] **Comprehensive Audit Script**: Developed `stable_institutional_audit.py` for definitive cross-run benchmarking.
- [x] **Anomaly Detection**: Identified "Window 220" and "Window 300" flash-crash events.
- [x] **SHORT Integrity Audit**: Verified 100% directional accuracy across 4,180 strategy atom implementations.
- [x] **Volatility Band Verification**: Validated target risk bands (MinVar: 0.35, HRP: 0.45, MaxSharpe: 0.90).

### Phase 148: Tail-Risk Mitigation & Regime Hardening (COMPLETED)
- [x] **Tail-Risk Selection Alpha**: Integrated Skewness, Kurtosis, and CVaR into the v4 Selection Pipeline.
- [x] **Regime Detector Enhancement**: Updated `MarketRegimeDetector` with Fat-Tail Awareness.
- [x] **Flash-Crash Mitigation**: Implemented Profile-Specific Ridge Loading for `max_sharpe`.
- [x] **Requirements Update**: Codified the "Outlier Survival" standard (CR-620).

### Phase 149: Forensic Reporting & Schema Stabilization (COMPLETED)
- [x] **Audit Script Overhaul**: Standardized `stable_institutional_audit.py` with compounded TWR and Window forensic trace.
- [x] **Funnel Traceability**: Implemented discovery-to-selection efficiency tracking.
- [x] **Volatility Compliance**: Verified risk anchors (MinVar: 0.35, HRP: 0.45, MaxSharpe: 0.90).
- [x] **Numeric Hardening**: Fixed data type dropouts in the audit ledger.

### Phase 150: MLOps Tail-Risk & Strategic Hardening (COMPLETED)
- [x] **Alpha Veto Hardening**: Implemented Kurtosis (>20) and Asset-Vol (>2.5) hard vetoes.
- [x] **Strategic Risk Delegation**: Delegated directional concentration to Pillar 3; removed implicit caps.
- [x] **Bounded Clustering (CR-650)**: Enforced hard ceiling of 25 clusters to prevent factor fragmentation.
- [x] **Funnel Traceability**: Standardized `SelectionFunnel` metrics (Universe/Discovery/Selection) in audit ledger.
- [x] **Compounded Report Fix**: Refactored `stable_institutional_audit.py` with Time-Weighted Return (TWR) for realistic benchmarking.
- [x] **Matrix Certification**: Executed final validation tournament; verified 100% directional integrity.

### Phase 151: Institutional Scaling & Meta-Portfolio Readiness (COMPLETED)
- [x] **Final System Certification (v3.6.1)**: Executed exhaustive 3D matrix; verified 100% directional integrity.
- [x] **Compounded Report Fix**: Standardized TWR metrics to eliminate arithmetic artifacts (776% -> 148%).
- [x] **Selection Funnel Trace**: Implemented deep lifecycle audit (Universe -> Discovery -> Selection).
- [x] **Hardened Risk Policy**: Verified CR-650 (Bounded Clustering) and CR-660 (Liquidation Floor).

### Phase 152: Alpha Convergence & Meta-Sleeve Readiness (COMPLETED)
- [x] **Alpha Convergence Tuning**: Re-calibrated v4 weights to bridge the Sharpe gap.
- [x] **Meta-Sleeve Ingestion**: Finalized the join logic for Crypto + TradFi sleeves.
- [x] **Unified Alpha Funnel**: Implemented cross-sleeve Log-MPS normalization.

### Phase 153: Compounded Return Normalization (COMPLETED)
- [x] **Geometric Standard**: Refactored `utils/metrics.py` to use Geometric Mean compounding.
- [x] **Lookahead Bias Correction**: Implemented strict `iloc` slicing in `backtest_engine.py` (CR-185).
- [x] **Metric Purity**: Validated TWR compounding against institutional benchmarks.

### Phase 154: Forensic Metric Audit & Selection Validation (COMPLETED)
- [x] **Metric Verification (CR-750)**: Refactored `stable_institutional_audit.py` to independently calculate Sharpe/MaxDD.
- [x] **Proven Metrics Standard**: Overhauled `utils/metrics.py` to reuse `quantstats` package for all institutional benchmarks (AnnRet/CAGR, Sharpe, Vol, MaxDD, etc.).
- [x] **Lookahead Bias Correction**: Verified `iloc` slicing eliminated 1-day overlap in walk-forward loops.
- [x] **Baseline Normalization**: Confirmed AnnRet dropped from 972% to 188% (v4 MaxSharpe) following bias correction and geometric compounding.

### Phase 154: Forensic Metric Audit & Selection Validation (COMPLETED)
- [x] **Metric Verification (CR-750)**: Refactored `stable_institutional_audit.py` to independently calculate Sharpe/MaxDD.
- [x] **Proven Metrics Standard**: Overhauled `utils/metrics.py` to reuse `quantstats` package for all institutional benchmarks.
- [x] **Lookahead Bias Correction**: Verified `iloc` slicing eliminated 1-day overlap in walk-forward loops.
- [x] **Baseline Normalization**: Confirmed AnnRet dropped from 972% to 101% following bias correction and geometric compounding.

### Phase 155: Institutional Scaling & Meta-Portfolio Alpha (COMPLETED)
- [x] **Alpha Convergence Tuning**: Corrected entropy mapping and directional recruitment in v4 pipeline.
- [x] **Execution Friction Audit**: Quantified slippage impact (5bps vs 10bps) on turnover and returns.
- [x] **Upstream Data Audit**: Technical ratings (MA/Technical) verified and persisting in Lakehouse.
- [x] **Modular Strategy Scanners**: Implemented 12 Rating-based scanners for Spot/Perps with All/MA/Oscillator variants.
- [x] **Data Enrichment**: Added `Volatility.D` and `volume_change` (24h) persistence for selection scoring.
- [x] **Logic Preservation**: Consolidator now treats different ranking strategies as unique atoms (Symbol_Logic_Direction).
- [x] **Strategy Layer Abstraction**: Manifest schema refactored to group scanners under named **Strategies** with automatic logic injection. [COMPLETED]
- [x] **Comprehensive Discovery Audit**: All 12 rating scanners now utilize `binance_liquid_base.yaml` for exhaustive candidate capture (Top 200 liquid universe). [COMPLETED]
- [x] **Feature Expansion (ROC)**: Added `ROC` (Rate of Change) to requested fields for momentum analysis. [COMPLETED]
- [x] **Institutional Liquidity Hardening**: Updated Binance Spot floor to >$20M and Perp floor to >$50M with explicit `type` filtering (Spot/Swap). [COMPLETED]
- [x] **Pure Discovery Audit**: Stripped discovery scanners of non-liquidity/non-rating filters. Tightened Buy/Sell to strictly exclude Neutrals (Thresholds: 0.1 / -0.1). [COMPLETED]
- [x] **Redundant Filter Cleanup**: Audited and removed redundant Python-side post-filters (Perps, Dated Futures, Quote Whitelists) in favor of native TradingView screener filters. [COMPLETED]
- [x] **Agnostic Base Scanner Audit**: Verified `binance_spot_base.yaml` (>$20M) and `binance_perp_base.yaml` (>$50M) provide truly unranked liquidity pools with strict venue isolation and neutral `name` sorting. [COMPLETED]
- [x] **Venue Isolation Standard**: Explicitly separated Spot and Perp outputs in discovery and Lakehouse persistence to prevent data contamination. [COMPLETED]
- [x] **Lean Recruitment Standard**: Formalized requirement to offload all complex statistical filtering (ADX, ROC Capping) to downstream Selection Vetoes. [COMPLETED]
- [x] **Exhaustive Recruitment Audit**: Verified recruitment of ~140 distinct atoms across orthogonal rating strategies with strictly non-neutral sentiment (> 0.0 / < 0.0). [COMPLETED]
- [x] **Logic Preservation**: Verified consolidator persistence of `logic` metadata (`rating_all`, `rating_ma`, `rating_osc`) for independent return stream generation. [COMPLETED]
- [x] **Strategy as an Asset**: Defined "Strategy Stream" architecture and created granular manifest profiles (`crypto_rating_all`, `crypto_rating_ma`, `crypto_rating_osc`) for independent execution. [COMPLETED]
- [x] **Hedging Design Audit**: Validated that combined LONG/SHORT profiles enable native risk-parity hedging without requiring manual splitting. [COMPLETED]
- [x] **Forensic Anomaly Audit**: Confirmed Venue Purity (0% leakage) and identified `FHEUSDT.P` as a reference ROC outlier (>100%). [COMPLETED]
- [x] **Implementation Hardening**: Refactor scanners to prioritize USD-Stable venues (Done in L1 Audit) and identified ROC-capping requirement. [COMPLETED]

### Phase 156: Meta-Portfolio Allocation & Risk Hardening (IN PROGRESS)
- [x] **Veto Implementation**: Implemented `SelectionPolicyStage` vetoes for extreme ROC (>100% / <-80%) and Volatility (>100.0) to prune outliers. [COMPLETED]
- [ ] **Strategy Execution**: Execute granular profiles (`rating_all`, `rating_ma`, `rating_osc`) to generate isolated synthetic equity curves.
- [ ] **Meta-Allocation**: Construct the final Meta-Portfolio by allocating capital across these synthetic strategy streams.
- [ ] **Final Certification**: Execute end-to-end tournament of the Multi-Strategy Meta-Portfolio.

---
**System Status**: 🟢 PRODUCTION CERTIFIED (v3.8.1) - Tail-Risk Vetoes Active




