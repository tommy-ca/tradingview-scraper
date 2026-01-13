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
- **Primary Model (v3.4)**: Stabilized HTR Standard.
- **Secondary Model (v2.1)**: Additive Rank-Sum (CARS 2.1) for drawdown protection.
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

### 3.2 Refinement Funnel (5-Stage)
1. Discovery -> 2. Normalization -> 3. Metadata Enrichment -> 4. Identity Deduplication -> 5. Statistical Selection.

## 4. Development Plan (Current Sprint)

### Phases 100-117: (Archived - See docs/specs/archive/phases_100_117.md)
*Includes Refactor, HTR v3.4 implementation, Numerical Hardening, and Master Tournament Calibration.*

### Phase 118: Regime Sensitivity & Directional Alignment Audit (COMPLETED)
- [x] **Regime Metric Audit**: Verified `MarketRegimeDetector` internal weighting.
- [x] **Directional Purity**: Implemented **Synthetic Long Normalization (CR-260)**.
- [x] **Alignment Analysis**: Confirmed return inversion allows solvers to correctly treat falling-price assets as alpha contributors.

### Phase 119: Synthetic Directional Hardening & Strategy Synthesis (COMPLETED)
- [x] **Simulated Directional Mapping**: Updated `backtest_simulators.py` to correctly report "Net Exposure" for Synthetic Longs.
- [x] **Atomic Strategy Interface**: Defined `synthesis.py` for "Synthesized Return Streams".
- [x] **Optuna Regime Calibration**: Implemented `scripts/calibrate_regime_detector.py`.
- [x] **Multi-Scale Composing**: Standardized logic to compose atom strategies into a unified matrix.

### Phase 120: Strategy-Centric Architectural Pivot (COMPLETED)
- [x] **Architecture Reorg**: Decoupled decision logic from engines; moved to `BacktestOrchestrator`.
- [x] **Purified Portfolio Engines**: All engines are now "decision-naive," operating on synthesized streams.
- [x] **Strategy Synthesis Layer**: Initial implementation in `synthesis.py` and `BacktestOrchestrator`.
- [x] **Meta-Orchestrator**: Controller now manages regime-to-profile mapping.
- [x] **Validation Run**: Run `v3_4_strategy_pivot` verified 100% solver stability in the new 3-pillar design.

### Phase 121: Strategy Composition & Atomic Ensembles (COMPLETED)
- [x] **Complex Strategy Definition**: Defined schemas for Strategy Atoms (Asset, Logic, TimeScale).
- [x] **Architecture Reorg**: Split selection layer into `impl/` modules.
- [x] **Purified Backtest Engine**: Orchestrator now manages the 3-pillar workflow (Selection -> Synthesis -> Allocation).

### Phase 122: Constraint-Based Allocation & Synthetic Clustering (COMPLETED)
- [x] **Market Neutral Constraint (CR-290)**: Refactored `market_neutral` from a Profile into a native Allocation Constraint in `custom.py`.
- [x] **Synthetic Hierarchical Clustering (CR-291)**: Implemented hierarchical clustering on synthesized return streams in `backtest_engine.py`.
- [x] **3-Pillar Orchestration**: Fully decoupled Selection, Synthesis, and Allocation.

### Phase 123: Logic Integrity & Forensic Verification (COMPLETED)
- [x] **Selection Stage Purification**: Refactored `_select_v3_core` to strictly separate HTR stages.
- [x] **Constraint Stress Test**: Verified beta-neutrality enforcement in `custom.py`.
- [x] **Baseline Universe Audit**: Confirmed `baseline` engine passes raw universe correctly.
- [x] **Unified Documentation Sync**: Finalized design docs for v3.4.2.

### Phase 124: Pillar Hardening & Atom Purity Standard (COMPLETED)
- [x] **Atom Purity Audit**: Enforced "One Logic per Atom" in `synthesis.py`.
- [x] **Recursive Weight Trace**: Verified the mapping from Strategy Weights -> Atom Weights -> Physical Weights.
- [x] **Barbell Rationale Codification**: Formally defined `barbell` as a **Pillar 3 Risk Profile** (Capital Segmentation).
- [x] **Dual-Layer Clustering Audit**: Confirmed synthetic hierarchical clustering identifies uncorrelated alpha factors.

### Phase 125: Strategy Atom Hardening & Directional Integrity (COMPLETED)
- [x] **Directional Atom Interface**: Standardize `(Asset, Logic, Direction)` as the atomic return stream.
- [x] **Weight Flattening Guard**: Implement a verification step in the orchestrator to ensure $\sum w_{net} \approx \text{Target Exposure}$ after asset aggregation.
- [x] **Barbell Rationale**: Verified `barbell` remains a Pillar 3 Risk Profile (Capital Segmentation).
- [x] **Market Neutral Constraint Hardening**: Finalized the beta-tolerance scaling ($0.15 \rightarrow 0.05$) based on universe density.
- [x] **Comprehensive Pillar Audit**: Traced a single trade from Scanner Signal -> Selection Veto -> Strategy Synthesis -> Portfolio Weight -> Simulator Realization.

### Phase 126: Forensic Audit & Guardrail Enforcement (COMPLETED)
- [x] **Feature Flag Guardrail**: Gated `Market Neutral` constraints behind `feat_market_neutral` flag (default=OFF).
- [x] **Institutional Documentation Sync**: Updated all spec and design docs to reflect 3-pillar strategy atom standards.
- [x] **Hardened toxicity tests**: Verified 0.999 entropy ceiling in `test_selection_hardening.py`.
- [x] **Address linting issues**: Cleaned up bare excepts and type diagnostics.

### Phase 127: Selection Funnel & Clustering Audit (COMPLETED)
- [x] **Discovery Stage Audit**: Reviewed `select_top_universe.py` for identity grouping accuracy; implemented iterative quote stripping.
- [x] **Clustering Logic Review**: Audited hierarchical clustering in `SelectionEngineV3` (Ward linkage, multi-lookback averaging).
- [x] **Top N Selection Purity**: Verified Top N per cluster prioritizes Log-MPS conviction while maintaining factor diversity.
- [x] **Scanned Universe Selection**: Trace how L4 scanner outputs are filtered before entering the "Raw Pool."
- [x] **Requirements Update**: Codified the "Canonical Consolidation" and "Top-N Cluster Purity" standards.

### Phase 128: Baseline Standards & Benchmarking (COMPLETED)
- [x] **Baseline Engine Audit**: Reviewed `BaselineSelectionEngine` for interface purity.
- [x] **Structural Baseline Implementation**: Created `liquid_htr` selection engine (HTR clustering + Liquidity Top-N).
- [x] **Dimensionality Bias Audit**: Solvers now have multiple baselines to differentiate between "Pool Size effect" and "Alpha quality effect."
- [x] **Requirements Update**: Defined "Pass-through" vs "Structural" baseline standards.

### Phase 129: Final Forensic Verification & Alpha Attribution (COMPLETED)
- [x] **Comprehensive Master Tournament**: Executed light audit (`v3.4`, `liquid_htr`) and audited `baseline` behavior.
- [x] **Anomaly Detection**: Identified "Mixed Direction Bias" in raw baseline pools; refined Weight Guard warning thresholds in `BacktestOrchestrator`.
- [x] **Alpha Attribution**: Verified HTR Stage 3/4 successfully prevents "Factor Sparsity" in restrictive regimes.
- [x] **Final Certification**: System hardened for Q1 2026 Production.

### Phase 130: End-to-End Pipeline Integration Audit (COMPLETED)
- [x] **Discovery-to-Optimization Trace**: Audited ticker `SOL` from L4 signal -> Discovery -> Log-MPS -> Portfolio Weight; verified 100% traceability.
- [x] **Cross-Layer Data Integrity**: Integrated `ADX` into Pillar 1 Log-MPS scoring; verified preservation of `Value.Traded` metadata.
- [x] **Clustering Purity Audit**: Confirmed hierarchical clustering correctly partitions factor space before conviction-based recruitment.
- [x] **Full-Scale Tournament**: Executed production-grade tournament across all modes (`baseline`, `liquid_htr`, `v3.2`, `v3.4`).
- [x] **Documentation Sync**: Standardized the six-stage selection funnel in architecture docs.

### Phase 131: MLOps-Centric Pipeline Foundation (v4) (COMPLETED)
- [x] **Infrastructure Definition**: Implemented `BasePipelineStage` and `SelectionContext` schemas (Pydantic).
- [x] **Data Ingestion Stage**: Created `IngestionStage` to fetch L4 artifacts into the v4 context.
- [x] **Feature Engineering Stage**: Implemented `FeatureEngineeringStage` for stateless alpha factor calculation.
- [x] **Shadow Execution Test**: Verified v4 foundation via `scripts/test_v4_foundation.py`.

### Phase 132: Modular Inference & Clustering (v4) (COMPLETED)
- [x] **Conviction Scorer**: Implemented stateless `InferenceStage` using `utils.scoring` logic.
- [x] **Factor Bucketizer**: Implemented unsupervised `ClusteringStage` wrapping Ward Linkage logic.
- [x] **Parity Audit Script**: Validated 100% Score Parity between v3.4 and v4 using `audit_v4_parity.py`.
- [x] **Forensic Fix**: Patched `SelectionEngineV3_2` to correctly report all calculated metrics for auditability.

### Phase 133: Policy Controller & HTR v4 (COMPLETED)
- [x] **Selection Controller**: Implemented `SelectionPolicyStage` for Top-N recruitment and veto application.
- [x] **Pipeline Orchestrator**: Implemented `SelectionPipeline` to manage the HTR relaxation loop and stage execution.
- [x] **Strategy Atom Synthesis**: Implemented `SynthesisStage` to finalize Pillar 2 handover.
- [x] **Integration Test**: Verified full pipeline execution via `scripts/test_v4_pipeline.py`.

### Phase 134: Champion/Challenger Production Rollout (COMPLETED)
- [x] **Dual-Run Config**: Updated `run_master_tournament.py` to include `v4` in the selection lineup.
- [x] **Adapter Layer**: Created `SelectionPipelineAdapter` to bridge `SelectionContext` to `SelectionResponse` for seamless integration.
- [x] **Shadow Mode**: Enabled `v4` shadow execution in production tournaments.
- [x] **Deprecation**: Identified `selection_engines/impl` legacy code for future deprecation.

### Phase 135: Deep Audit Integration & Telemetry (COMPLETED)
- [x] **Requirement**: Formalized CR-420 for granular telemetry segregation.
- [x] **Design Update**: Added Global Ledger Mapping specs to v4 design docs.
- [x] **Orchestrator Update**: Refactored `backtest_engine.py` to move audit trails to the `data` blob.
- [x] **Integration Test**: Verified end-to-end telemetry flow via `tests/test_audit_v4_integration.py`.

### Phase 136: Legacy Deprecation & v4 Cutover (PLANNED)
- [ ] **Validation Period**: Confirm v4 stability and alpha parity after 1 week of shadow runs.
- [ ] **Cutover**: Promote `v4` pipeline to be the default selection engine.
- [ ] **Cleanup**: Remove `v3.x` legacy engines from the codebase.

---
**System Status**: 🟢 PRODUCTION CERTIFIED (v3.4.5) - Phase 134 Complete (v4 Shadow Mode Active)
