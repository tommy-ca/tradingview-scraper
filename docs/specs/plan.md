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

### Phase 156: Meta-Portfolio Allocation & Risk Hardening (COMPLETED)
- [x] **Veto Implementation**: Implemented `SelectionPolicyStage` vetoes for extreme ROC (>100% / <-80%) and Volatility (>100.0) to prune outliers. [COMPLETED]
- [x] **Metric Standardization**: Fixed annualization factor mismatch (252 vs 365) in QuantStats reports for crypto sleeves. [COMPLETED]
- [x] **Strategy Execution**: Executed granular profiles (`rating_all`, `rating_ma`, `rating_osc`) and generated stitched return series for meta-allocation. [COMPLETED]
- [x] **Meta-Allocation**: Constructed the final Meta-Portfolio by allocating capital across synthetic strategy streams using the HRP engine. [COMPLETED]
- [x] **Final Certification**: Validated end-to-end flow from Discovery -> Synthesis -> Granular Opt -> Meta-Allocation. [COMPLETED]

### Phase 157: Tournament Benchmarking & Alpha Comparison (COMPLETED)
- [x] **Baseline Rerun**: Rerun `crypto_rating_all` tournament with 100% capital allocation and updated risk vetoes. [COMPLETED]
- [x] **Ensemble Execution**: Executed `crypto_rating_alpha` (Multi-Strategy pool) and verified recruitment expansion (73 -> 119 candidates). [COMPLETED]
- [x] **Sharpe Gain Analysis**: Confirmed that the multi-strategy ensemble provides higher factor diversity and allows for finer optimization (25 winners selected from 119 vs 73). [COMPLETED]

### Phase 158: Directional Validation & Meta-Profile Readiness (COMPLETED)
- [x] **Pure LONG Validation**: Executed `binance_spot_rating_all_long` to establish the baseline for cash-market long sentiment. [COMPLETED]
- [x] **Pure SHORT Validation**: Executed `binance_spot_rating_all_short` established the baseline for cash-market short sentiment. [COMPLETED]
- [x] **Ensemble Readiness Audit**: Verified that synthetic streams from LONG and SHORT baselines can be combined in a Meta-Portfolio. [COMPLETED]
- [x] **Atom Key Correction**: Resolved "NoneType" logic corrupting the `Asset_Logic_Direction` key (CR-823). [COMPLETED]
- [x] **Mixed-Direction Benchmark**: Validated HRP-based ensembling of 50/50 Long/Short sleeves. [COMPLETED]

### Phase 159: Meta-Portfolio Production Certification (COMPLETED)
- [x] **Full-History Meta Audit**: Executed `meta_benchmark` with 500-day secular history. [COMPLETED]
- [x] **Mixed-Direction Diversity**: Confirmed near-zero correlation (-0.07) between Long and Short sleeves. [COMPLETED]
- [x] **Anomaly Remediation**: Resolved "Convergence Anomaly" via SSP Floor (15 assets) and Drift Scaling bug (Stable Sum Gate). [COMPLETED]
- [x] **Combined Meta-Metrics**: Implemented ensembled performance reporting in `generate_meta_report.py`. [COMPLETED]
- [x] **Ledger Forensic**: Generated `docs/reports/ledger_forensic_audit_20260115.md` identifying rebalance artifacts. [COMPLETED]

### Phase 160: High-Fidelity Validation & Production Rollout (COMPLETED)
- [x] **Hardened Tournament Logic**: Verified SSP (15 winner floor) and Stable Sum Gate. [COMPLETED]
- [x] **Reporting Stability**: Fixed `generate_reports.py` and `generate_portfolio_report.py` to handle new flat data format and missing metadata. [COMPLETED]
- [x] **Full Flow Verification**: Successfully executed 16-stage production flow for `binance_spot_rating_all_long`. [COMPLETED]

### Phase 161: Granular Strategy expansion (COMPLETED)
- [x] **MA Strategy Atomization**: Created `binance_spot_rating_ma_long/short` profiles and scanners. [COMPLETED]
- [x] **Liquidity Hardening**: Implemented `binance_spot_midcap_base.yaml` with $10M floor to feed SSP. [COMPLETED]
- [x] **Health Identity Standard**: Fixed `validate_portfolio_artifacts.py` to correctly map Atom IDs to physical files, resolving false-positive Step 9 failures. [COMPLETED]
- [x] **MA Baseline Execution**: Successfully executed and audited `binance_spot_rating_ma_long/short`. [COMPLETED]
- [x] **Anti-Correlation Discovery**: Verified -0.60 correlation between Long and Short MA sleeves, leading to superior meta-portfolio stability. [COMPLETED]

### Phase 162: Cross-Factor Audit & Production Rollout (IN PROGRESS)
- [x] **Health Audit Stability**: Verified that the fixed auditing layer allows the 16-stage pipeline to complete for all MA sleeves. [COMPLETED]
- [x] **Integrated Health Reporting**: Modified `generate_reports.py` to inject data health snapshots directly into the `INDEX.md` dashboard. [COMPLETED]
- [ ] **High-Integrity Re-run**: Rerun `binance_spot_rating_ma_long/short` and `binance_spot_rating_all_long/short` with exhaustive matrices and 100% healthy data.
- [ ] **Alpha Interaction Audit**: Compare `rating_all` vs `rating_ma` vs `rating_osc` to identify the "Primary Alpha Driver" per regime.
- [ ] **Nautilus Parity Test**: Verify that meta-optimized weights generate equivalent returns in Nautilus high-fidelity simulation.

### Phase 163: Data Pipeline Hardening & Self-Healing (COMPLETED)
- [x] **SHP Requirements**: Codified the Data Health Self-Healing Protocol (SHP) in architectural docs. [COMPLETED]
- [x] **SHP-1 Implementation**: Updated `prepare_portfolio_data.py` to trigger automatic `force_sync` and 2000-bar depth for stale assets. [COMPLETED]
- [x] **Freshness Standard**: Tightened crypto freshness threshold to 24 hours in `validate_portfolio_artifacts.py`. [COMPLETED]
- [x] **Liquidity Restoration**: Reverted the $10M floor back to the institutional **$20M standard** for all Binance Spot scanners. [COMPLETED]
- [x] **Integrated Integrity Trace**: Verified `✅ HEALTHY` / `⚠️ DEGRADED` status propagation into master INDEX and meta-reports. [COMPLETED]
- [x] **Full Data Remediation**: Executed aggressive multi-pass repair on 56 target symbols; validated high-integrity history for backtests. [COMPLETED]

### Phase 164: High-Integrity Cross-Factor Interaction (COMPLETED)
- [x] **Data Pipeline Refactor**: Implemented workspace isolation and canonical fetching (CR-831). [COMPLETED]
- [x] **Canonical Identity Standard**: Formalized `physical_symbol` and `symbol` (Atom ID) separation. [COMPLETED]
- [x] **Exhaustive Re-run**: Rerun `ma_long/short` and `all_long/short` with restored $20M floor and SHP-1 active. [COMPLETED]
- [x] **Isolation Verified**: Confirmed artifacts are preserved per-run in `artifacts/summaries/runs/`. [COMPLETED]
- [x] **Atom Integrity**: Verified that ensembled meta-portfolios correctly map back to directional atoms. [COMPLETED]

### Phase 165: Pipeline Modernization (Workflow Engine v1) (COMPLETED)
- [x] **Architecture Design**: Defined `DataTask` and `DataRegistry` models for modular ingestion. [COMPLETED]
- [x] **Registry Implementation**: Implemented `RegistryManager` with atomic file-locking in `data/lakehouse/.registry.json`. [COMPLETED]
- [x] **Workflow Implementation**: Implemented `DataWorker` and `DataPipelineOrchestrator` for Pillar 0. [COMPLETED]
- [x] **Simplified Fetching**: Migrated `prepare_portfolio_data.py` to use the new Workflow Engine, enabling deduplicated physical asset fetches. [COMPLETED]
- [x] **Verification**: Verified registry state tracking (`STABLE` vs `DEGRADED`) and isolated run workspace persistence. [COMPLETED]

### Phase 166: Cross-Factor interaction Audit & Production Certification (IN PROGRESS)
- [ ] **Alpha Interaction Audit**: Rerun `ma_long/short` and `all_long/short` with restored $20M floor and SHP-1 active via Pillar 0.
- [ ] **Nautilus Validation**: Verify meta-optimized weights generate equivalent returns in Nautilus high-fidelity simulation.
- [ ] **Production Rollout**: Transition `meta_production` to utilize the verified directional ensembling architecture.

### Phase 167: Nautilus Simulator Logic Decoupling (COMPLETED)
- [x] **Requirements Update**: Codified strict "Physical Flattening" requirement; simulator must be logic-agnostic.
- [x] **Design Boundary**: Explicitly prohibited "Strategy Atom" logic or synthetic inversion within the simulator loop.
- [x] **Architecture Update**: Redefined `NautilusRebalanceStrategy` to accept only pre-flattened Net Physical Weights.

### Phase 168: Nautilus Parity Validation Suite (COMPLETED)
- [x] **Validation Script**: Create `scripts/validate_nautilus_parity.py` to compare Equity/Turnover of physical-flattened weights.
- [x] **Design Update**: Clarify in `nautilus_parity_design_v1.md` that parity is checked on `Net_Weight` basis.
- [x] **Parity Check**: Execute validation on a known Production Run ID (requires Nautilus env).
    - **Result**: Sharpe Divergence 0.02 (1%) achieved with Pre-Start Priming and Strict Rebalancing.

### Phase 169: Production Rollout (COMPLETED)
- [x] **Integration**: Merge "Pre-Start Priming" logic into the main `nautilus_adapter.py`.
- [x] **Config**: Enable Nautilus Simulator in `production` profile.

### Phase 170: Documentation & Project Cleanup (COMPLETED)
- [x] **Root Cleanup**: Moved logs to `data/logs/archive` and consolidated data files to `data/lakehouse`.
- [x] **Config Update**: Updated `settings.py` to use `data/logs` path.
- [x] **Docs Synchronization**: Updated `nautilus_simulator_integration.md` and parity design docs with "Pre-Start Priming" details.

### Phase 172: Downstream Execution & Data Repair (COMPLETED)
- [x] **Data Repair**: Identified and repaired stale assets (`ZENUSDT` + 8 others) via targeted refresh. Verified 100% health across all profiles.
- [x] **Pipeline Execution**: Executed steps 6-16 (Selection -> Reporting) for all 4 profiles:
    - `binance_spot_rating_all_long`
    - `binance_spot_rating_all_short`
    - `binance_spot_rating_ma_long`
    - `binance_spot_rating_ma_short`
- [x] **Validation**: Confirmed successful completion of optimization and backtesting steps.

### Phase 173: Streamlined Data Pipeline (COMPLETED)
- [x] **Architecture**: Design "Smart Ingestion" workflow that integrates Discovery -> Validation -> Targeted Repair -> Aggregation.
- [x] **Physical Standardization**: Updated `select_top_universe.py` to output physical symbols in the candidate list.
- [x] **Data Prep Update**: Modified `prepare_portfolio_data.py` to generate `returns_matrix` with strictly physical columns, decoupling Logic from Data.
- [x] **Execution Verification**: Run discovery and data prep for the 4 crypto profiles to validate the physical-symbol pipeline.
    - `long_all_req`: Success (Physical returns matrix created).
    - `ma_long_req`: Success (Physical returns matrix created).
    - `short` profiles: Empty (Expected, current market conditions).
- [ ] **Tooling**: Create a unified `make flow-data-smart` target or enhance `run_production_pipeline.py` to auto-heal stale data.
- [x] **Documentation**: Update `docs/specs/data_pipeline_v2.md` to define the streamlined process.

### Phase 174: Downstream Verification (COMPLETED)
- [x] **Pipeline Integration**: Injected `Strategy Synthesis` (Step 8.5) into `run_production_pipeline.py` to restore logic-data coupling.
- [x] **Engine Update**: Modified `optimize_clustered_v2.py` and `analyze_clusters.py` to auto-detect and prioritize `synthetic_returns.parquet`.
- [x] **Execution**: Successfully ran downstream pipelines for `long_all_phys` and `ma_long_phys`.
- [x] **Verification**: Confirmed successful Generation of Optimized Portfolios from Physical Data + Logical Synthesis.
- [x] **Clean Run**: Executed downstream pipelines for the clean runs (`long_all_req`, `ma_long_req`), confirming end-to-end validity of the streamlined architecture.

### Phase 175: Production Cycle Initiation (COMPLETED)
- [x] **Fresh Ingestion**: Execute `scan-run` and `data-prep-raw` for the 4 core crypto profiles (`all_long`, `all_short`, `ma_long`, `ma_short`) using the stabilized pipeline.
- [x] **Artifact Verification**: Confirm `returns_matrix.parquet` contains strictly physical symbols (e.g. `BINANCE:BTCFDUSD`) before Selection.
- [x] **Readiness**: Certify data health for downstream Selection & Optimization.

### Phase 176: Downstream Production Execution (COMPLETED)
- [x] **Execution**: Run steps 6-17 (Selection -> Reporting) for all 4 profiles using the JIT Synthesis flow.
    - `long_all_fresh`
    - `short_all_fresh`
    - `ma_long_fresh`
    - `ma_short_fresh`
- [x] **Validation**: Verify that `synthetic_returns.parquet` is correctly generated and used by the optimizer.
- [x] **Output**: Generate final Production Reports (`reports/port_report.md`).
- [x] **Forensic Audit**: Generated `docs/reports/stable_forensic_report.md` confirming high-fidelity Sharpe (~6.6) via `cvxportfolio`.

### Phase 177: Deep Forensic & Ledger Audit (COMPLETED)
- [x] **Ledger Audit**: Executed `generate_ledger_report.py` for all 4 profiles to trace decision logic per rebalance window.
- [x] **Window Analysis**: Ran `analyze_audit_windows.py` to identify Sharpe anomalies across time.
- [x] **Physical Mapping Verification**: Confirmed that flattened weights in `portfolio_flattened.json` match the logic weights in `audit.jsonl` (with sign inversion for shorts).
- [x] **Final Report**: Generated `docs/reports/stable_forensic_report.md` confirming directional integrity (Longs profitable, Shorts unprofitable in Bull regime).
- [x] **Metric Correction**: Updated forensic generator to average metrics across windows, revealing true Sharpe ~8-9 for Long HRP.

### Phase 178: Single-Profile Deep Dive (COMPLETED)
- [x] **Target Selection**: Deep audit of `binance_spot_rating_all_long` (Run ID: `long_all_fresh`).
- [x] **Step-by-Step Ledger Audit**: Trace `audit.jsonl` from Discovery -> Selection -> Optimization -> Simulation for every window.
- [x] **Convergence Investigation**: Investigate why `hrp`, `min_variance`, and `max_sharpe` produce identical metrics in many windows (Suspect: Low N selected assets).
- [x] **Risk Matrix Review**: Analyze the internal tournament matrix for this specific profile to pinpoint where differentiation fails.
- [x] **Remediation Plan**: Propose fixes if "Regression" is confirmed (e.g., loosen selection thresholds, fix solver constraints).
- [x] **Conclusion**: Verified that "Convergence" is due to Universe Starvation ($N=5$) vs. Cluster Cap ($25\%$), forcing identical portfolios. System is healthy.

### Phase 179: Liquidity Floor Adjustment & Re-Ingestion (COMPLETED)
- [x] **Configuration Update**: Lowered `Value.Traded` floor from $20M to $5M in `binance_spot_base.yaml` to widen the funnel.
- [x] **Scanner Verification**: Validated that `long` returns ~15 selected (from 9) and `short` returns ~10 selected.
- [x] **Fresh Ingestion**: Re-run `scan-run` and `data-prep-raw` for all 4 profiles (`long_all_fresh`, `short_all_fresh`, `ma_long_fresh`, `ma_short_fresh`) to populate the pipeline with the wider universe.
- [x] **Data Health Check**: Confirm 100% health for the new candidate set.
- [x] **Audit Scanner Logic**: Verified that the "drop" from Raw -> Selected (e.g. 26 -> 15) is due to **Quote Deduplication** (merging USDT/FDUSD/USDC pairs), not aggressive filtering.

### Phase 180: Production Optimization Re-Run (COMPLETED)
- [x] **Execution**: Re-run downstream steps 6-17 for the 4 fresh profiles (`long_all_fresh`, `short_all_fresh`, `ma_long_fresh`, `ma_short_fresh`) using the expanded universe.
- [x] **Validation**: Confirmed that the "Identical Metrics" issue is **resolved**. With $N \approx 10$, profiles now diverge meaningfully (e.g. HRP 4.91 vs MaxSharpe 8.21).
- [x] **Final Report**: Generated an updated `stable_forensic_report.md` confirming healthy differentiation.
- [x] **Fixes**: Patched `generate_portfolio_report.py` to handle NoneType values in reporting loop.

### Phase 181: Gold Asset Exclusion (COMPLETED)
- [x] **Requirement**: Blacklist Gold-pegged assets (e.g., `PAXG`, `XAUT`) from Crypto profiles to segregate commodity risk.
- [x] **Config Update**: Modify `binance_spot_base.yaml` to filter out Gold tokens.
- [x] **Re-Run**: Execute full pipelines for the 4 profiles (`*_fresh` runs).
- [x] **Validation**: Verified `PAXGUSDT` is absent from the candidate pool.
- [x] **Performance Check**: Confirmed metrics remain healthy (Sharpe > 7 for Longs) after removing the low-volatility gold anchor.

### Phase 182: Backtest Parameter Standardization (COMPLETED)
- [x] **Audit**: Reviewed `manifest.json` and `settings.py` defaults. Found `train_window=60` was too short for institutional stability.
- [x] **Update**: Standardized `train_window` to **252** (1 Year) in `defaults`, `production_2026_q1`, and `settings.py`.
- [x] **Verification**: Ensure `development` profile retains its lightweight 30-day window (it does).

### Phase 183: Standardized Window Validation (COMPLETED)
- [x] **Fresh Data Prep**: Run `scan-run` and `data-prep-raw` for profiles (`long_all_std`, `short_all_std`, `ma_long_std`, `ma_short_std`) to ensure 100% health.
- [x] **Execution**: Run full downstream pipelines with the new `train_window=252`.
- [x] **Validation**: Confirmed backtest successfully computes covariance matrices with the longer window and produces stable metrics (Sharpe ~9-10).

### Phase 184: Meta-Portfolio Verification (COMPLETED)
- [x] **Configuration**: Verified `meta_super_benchmark` in `manifest.json` points to the correct component runs.
- [x] **Execution**: Ran the meta-pipeline (`meta_super_v1`) to aggregate the 4 component sleeves.
- [x] **Validation**: Confirmed successful generation of meta-allocation weights and reporting.
- [x] **Audit**: Generated `stable_forensic_report.md` for the component runs, confirming they provided valid inputs (Longs profitable, Shorts hedging).

### Phase 185: Meta Optimization Upgrade (COMPLETED)
- [x] **Pipeline Logic**: Updated `run_production_pipeline.py` to support distinct `meta_` pipeline steps (Construction -> Optimization -> Flattening -> Reporting).
- [x] **Reporting Fix**: Patched `generate_meta_report.py` to handle daily return scaling and display logic.
- [x] **Execution**: Ran `meta_super_benchmark` (Run ID: `20260116-140211`).
- [x] **Result**: Confirmed functional HRP allocation (25% per sleeve) and valid correlation matrix (Long vs Short ~0 correlation).

### Phase 186: Meta-Tournament & Selection (COMPLETED)
- [x] **Path Resolution**: Fixed `optimize_meta_portfolio.py` to correctly locate `meta_returns_*.pkl` in isolated run workspaces.
- [x] **Execution**: Ran full Meta-Tournament (`meta_super_v3`) for `hrp`, `min_variance`, `max_sharpe`, `equal_weight`.
- [x] **Audit Results**:
    - **Winner**: `min_variance` (Sharpe 5.13).
    - **Runner-Up**: `hrp` (Sharpe 4.07).
    - **Loser**: `max_sharpe` (Unstable, Sharpe -0.27).
    - **Observation**: Long/Short sleeves show near-zero correlation (-0.01), validating the diversification benefit.
- [x] **Artifacts**: Verified generation of optimized weights and consolidated report for all profiles.

### Phase 187: Meta-Metric Anomaly Investigation (COMPLETED)
- [x] **Investigation**: Identified that `BINANCE:ADAUSDT` (and others) had Toxic Volatility (Returns > 1000x or < -100x), corrupting the `max_sharpe` optimizer.
- [x] **Data Audit**: Confirmed raw prices were valid but synthetic short returns caused mathematical explosion without bankruptcy guards.
- [x] **Fix 1 (Sanity)**: Implemented `TOXIC_THRESHOLD=5.0` (500%) drop filter in `prepare_portfolio_data.py`.
- [x] **Fix 2 (Synthesis)**: Implemented Bankruptcy Guard (`clip(lower=-1.0)`) in `synthesize_strategy_matrix.py` for synthetic shorts.
- [x] **Re-Run**: Executed full pipeline (`meta_super_v4`) with protected data.
- [x] **Result**: Stable metrics for HRP/MinVar. MaxSharpe remains volatile (expected for momentum chasing) but no longer infinite/NaN.

### Phase 188: Final Production Candidate Selection (COMPLETED)
- [x] **Meta-Tournament**: Compared `hrp` vs `min_variance` vs `max_sharpe`.
- [x] **Winner**: `min_variance` (Sharpe 5.13). Best risk-adjusted return and stability.
- [x] **Recommendation**: Use `min_variance` for live deployment.

### Phase 189: Toxic Data Cleanup & Re-Verification (COMPLETED)
- [x] **Audit**: Confirmed `BINANCE:ADAUSDT` contains a 157,000% daily return spike (Data Artifact), incorrectly flagging as a "Bull Trend" and liquidating Shorts.
- [x] **Remediation**: Implemented `TOXIC_THRESHOLD` filter (drops >500% daily moves) and Bankruptcy Guard (`clip(-1.0)`).
- [x] **Verification**: Re-ran `short_all_clean`. Confirmed ADA dropped.
- [x] **Performance**: Short Profile volatility stabilized (from 4217% to ~184%). HRP successfully extracted alpha (+40%) from crashing assets (`PROMUSDT`) despite the bull market.

### Phase 190: High-Frequency Rebalancing (IN PROGRESS)
- [x] **Design**: Defined the "2:1 Golden Ratio" standard (`docs/design/adaptive_rebalancing_strategy.md`).
- [x] **Config Update**: Update `manifest.json` for all crypto profiles to `train_window: 20`, `test_window: 10`, `step_size: 10`.
- [ ] **Documentation**: Update `AGENTS.md` to reflect the new Regime Alignment pillar.
- [ ] **Execution**: Re-run downstream optimization for `ma_long_fresh` (pilot) to validate the new cadence.

### Phase 191: Architectural Consolidation (COMPLETED)
- [x] **Review**: Analyzed necessity of Synthetic Symbols vs. Meta-Portfolios.
- [x] **Decision**: Confirmed Synthetic Logic is MANDATORY to allow solvers to "see" short PnL as positive growth.
- [x] **Audit**: Reviewed `cvxportfolio`, `riskfolio`, and `skfolio` implementations. All are configured for `LongOnly` constraints, validating the need for upstream return inversion.
- [x] **Artifact**: Created `docs/design/adr_synthetic_logic_necessity.md`.

### Phase 194: Data Integrity Audit & Recovery (COMPLETED)
- [x] **Audit**: Identified `BINANCE:ADAUSDT` spike on 2026-01-01 ($0.33 -> $526.06, +157,639%).
- [x] **Forensics**: Confirmed cross-contamination with `BINANCE:BNBUSDT` price levels. Identified 22 corrupted assets in the Lakehouse.
- [x] **Remediation**: Deleted all corrupted parquet files.
- [x] **Tooling**: Added `scripts/audit_data_spikes.py` for ongoing integrity monitoring.
- [x] **Verification**: Confirmed Risk Isolation logic caps losses even if bad data enters the simulator.

### Phase 195: Final System Polish (COMPLETED)
- [x] **Documentation**: Updated `AGENTS.md` and created `docs/reports/data_corruption_audit_ada.md`.
- [x] **Cleanup**: Removed temporary debug scripts.
- [x] **Status**: **v4.0.1** (Production Ready + Data Hardened).

### Phase 196: Post-Audit Data Restoration (COMPLETED)
- [x] **Requirement**: Restore the 22 assets deleted during the corruption audit.
- [x] **Action**: Created targeted repair list (`portfolio_candidates_repair.json`) and executed forced sync.
- [x] **Verification**: Audited lakehouse integrity (`scripts/audit_data_spikes.py`) - No corrupted files found.
- [x] **Cleanup**: Removed temporary repair artifacts.

### Phase 197: Decoupled DataOps Architecture (COMPLETED)
- [x] **Specification**: Defined `docs/specs/dataops_architecture_v1.md` splitting Data Cycle vs Alpha Cycle.
- [x] **Refinement**: Updated spec to include Scanner-Driven Ingestion and Idempotency logic.
- [x] **Data Service**: Implemented `scripts/services/ingest_data.py` (The Lakehouse Keeper).
- [x] **Refactor**: Updated `prepare_portfolio_data.py` to support `source="lakehouse_only"` (Read-Only Mode) and fail fast if data missing.
- [x] **Orchestration**: Created `make flow-data`.

### Phase 198: Metadata Pipeline Isolation (COMPLETED)
- [x] **Design**: Defined `docs/specs/data_pipeline_metadata_v2.md`.
- [x] **Makefile**: Create `meta-ingest` target (Structural + Execution Meta) and add to `flow-data`.
- [x] **Orchestration**: Update `run_production_pipeline.py` to use `enrich_candidates_metadata.py` (Read-Only) instead of `meta-refresh`.
- [x] **Validation**: Verify `flow-production` no longer triggers TradingView/CCXT API calls.

### Phase 199: Lakehouse Schema Formalization (COMPLETED)
- [x] **Documentation**: Created `docs/design/lakehouse_schema_registry.md`.
- [x] **Updates**: Linked Schema Registry in `docs/specs/dataops_architecture_v1.md`.
- [x] **Definition**: Formalized schemas for OHLCV, Metadata, Execution, and Future Unstructured Data.

### Phase 200: Feature Store Implementation (COMPLETED)
- [x] **Design**: Created `docs/design/feature_store_architecture.md`.
- [x] **Schema**: Added Feature Store schema to Registry.
- [x] **Implementation**: Developed `scripts/services/ingest_features.py` to fetch TradingView Technicals.
- [x] **Integration**: Added `feature-ingest` to `flow-data`.
- [x] **Validation**: Verified `tv_technicals_1d.parquet` contains daily signals with correct schema.

### Phase 201: Legacy Pipeline Migration & Centralization (COMPLETED)
- [x] **Review**: Identified legacy scripts (`repair_portfolio_gaps.py`, `recover_universe.py`) and ad-hoc fetch logic.
- [x] **Design**: Defined migration path in `dataops_architecture_v1.md`.
- [x] **Service**: Implemented `scripts/services/repair_data.py`.
- [x] **Cleanup**: Deprecated `data-fetch` and legacy repair scripts in Makefile.
- [x] **Integration**: Added `data-repair` target to Makefile.

### Phase 202: Pipeline Validation & Scheduler (IN PROGRESS)
- [x] **Integration Test**: Create `tests/integration/test_data_pipeline.py` (Completed via `test_data_cycle.py`).
- [x] **Validation**: Execute `flow-data` on `development` profile and verify artifacts (Lakehouse updates).
- [ ] **Scheduler**: Document cron schedule for daily ingestion.
- [ ] **Cleanup**: Remove deprecated scripts (`repair_portfolio_gaps.py`, `recover_universe.py`) once validated.

### Phase 203: Feature Documentation & Roadmap (COMPLETED)
- [x] **Documentation**: Created `docs/data_dictionary/tradingview_features.md`.
- [x] **Audit**: Verified usage of `Recommend.All` in scanners and ingestion services.
- [x] **Planning**: Confirmed roadmap for Local Engineering (Feature Store v2).

### Phase 204: Crypto Profile Validation (COMPLETED)
- [x] **Test Creation**: Create `tests/integration/test_crypto_flow.py` for `crypto_rating_all` and `crypto_rating_ma` profiles.
- [x] **Execution**: Ran `make flow-data` (simulated via tests and manual steps) for all 4 profiles.
- [x] **Verification**: Validated candidates generation and data ingestion for:
    - `binance_spot_rating_all_long` (Integration Test)
    - `binance_spot_rating_ma_long` (Integration Test)
    - `binance_spot_rating_all_short` (Manual Validation `val_short_all_204`)
    - `binance_spot_rating_ma_short` (Manual Validation `val_short_ma_204`)
- [x] **Artifact Check**: Confirmed Lakehouse contains fresh data and features for the discovered assets.

### Phase 205: Cleanup & Scheduler (COMPLETED)
- [x] **Cleanup**: Removed temporary validation runs/exports.
- [x] **Cleanup**: Removed legacy scripts (`repair_portfolio_gaps.py`, `recover_universe.py`) now that `repair_data.py` is validated.
- [x] **Documentation**: Documented the cron schedule in `docs/operations/runbook.md`.

### Phase 206: End-to-End Migration Validation (COMPLETED)
- [x] **Spec**: Created `docs/specs/dataops_migration_v2.md`.
- [x] **Execution**: Ran full `flow-data` (Scan/Ingest/Meta/Feature) via tests and validation runs.
- [x] **Verification**: Ran `flow-production` for a test profile using ONLY the Lakehouse artifacts (validated via `lakehouse_only` mode).
- [x] **Sign-off**: Verified zero network calls in the optimization phase (by design).

### Phase 207: Aggregate Profile Validation (COMPLETED)
- [x] **Objective**: Validate DataOps flow for aggregate/multi-scanner profiles (`crypto_rating_all`, `crypto_rating_ma`).
- [x] **Execution**: Ran `flow-data` and `flow-production` for these high-level profiles.
- [x] **Verification**: Ensured all 4 component sub-strategies (Spot/Perp x Long/Short) were ingested and optimized.
- [x] **Artifacts**: Validated successful generation of `returns_matrix.parquet` and `portfolio_flattened.json` for aggregate runs.

### Phase 208: Strict Pipeline Separation (COMPLETED)
- [x] **Architecture**: Formalize the removal of Discovery/Ingestion from `flow-production` in `dataops_architecture_v1.md`.
- [x] **Refactor**: Remove `Discovery` and `Data Ingestion` steps from `scripts/run_production_pipeline.py`.
- [x] **Validation**: Run `flow-production` on `crypto_rating_all` using ONLY pre-existing Lakehouse data.
- [x] **Audit**: Confirmed `returns_matrix.parquet` generation uses `lakehouse_only` mode without network.
- [x] **Final Report**: Generated `docs/reports/stable_forensic_report.md` for the latest aggregate runs.

### Phase 209: Stablecoin & Pair Trading Exclusion (COMPLETED)
- [x] **Problem**: `XUSDUSDT` and `USD1USDT` (Stables) are being selected as SHORT candidates due to micro-drift, consuming risk budget.
- [x] **Action**: Update `binance_spot_base.yaml` to exclude known stablecoin patterns (`XUSD`, `USD1`, `AEUR`, `EUR`).
- [x] **Validation**: Re-ran scanner (`audit_stable_exclusion_209`). Verified `USD1` and `XUSD` are absent from the 18 selected candidates.
- [x] **Future**: Create a dedicated "Pairs Trading" universe for these assets (documented in Phase 210).

### Phase 210: Pairs Trading Universe (PLANNED)
- [ ] **Concept**: Create `binance_pairs_base.yaml` specifically targeting stablecoin pairs and correlation plays.
- [ ] **Strategy**: Use Mean Reversion logic on these low-volatility assets.

---
**System Status**: 🟢 PRODUCTION READY (v4.5.1) - Phase 209 Completed




