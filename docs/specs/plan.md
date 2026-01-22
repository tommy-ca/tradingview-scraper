# Plan: Documentation Update & Workflow Streamlining

## 1. Documentation Updates
- [x] **Create `docs/specs/requirements_v3.md`**: Formalize the 3-Pillar Architecture (Universe Selection, Strategy Synthesis, Portfolio Allocation) and Selection Standards (HTR v3.4, Selection v3.2).
- [x] **Create `docs/specs/crypto_sleeve_v2.md`**: Document Crypto Sleeve Operations, Exchange Strategy, and Production Pillars.
- [x] **Create `docs/specs/numerical_stability.md`**: Document Numerical Stability & Reporting standards (Stable Sum Gate, SSP Minimums, Reporting Purity).
- [x] **Update `docs/specs/production_workflow_v2.md`**: reflect the current `flow-production` and `flow-meta-production` workflows.

## 2. Review and Audit
- [x] **Audit `Makefile`**: Check for parallelism opportunities and fragile dependencies.
- [x] **Audit `scripts/run_production_pipeline.py`**: Check for bottleneck and error handling.
- [x] **Audit `scripts/run_meta_pipeline.py`**: Check for recursive/fractal logic efficiency.
- [x] **Verify `manifest.json`**: Ensure profiles match the documentation (e.g., `crypto_production` parameters).

## 3. Streamlining & Optimization
- [x] **Optimize `flow-data`**:
    - Parallelize `data-ingest` and `feature-ingest` in Makefile.
    - Suggest `xargs -P` usage.
- [x] **Analyze `flow-production`**:
    - Identify sequential bottlenecks in the python pipeline.
- [x] **Identify Fragility**:
    - Check for "fail-fast" mechanisms in long-running jobs.
    - Verify "Data Guard" implementation (toxic data drops).

## 4. Final Report
- [x] Summary of changes and recommendations.

## 5. Elimination of Bottlenecks (Phase 2)
- [x] **Makefile Refactoring**:
    - Split `port-analyze` into `port-pre-opt` (Critical: Clusters, Stats, Regime) and `port-post-analysis` (Optional: Visuals, Deep Dive).
- [x] **Orchestrator Update (`scripts/run_production_pipeline.py`)**:
    - Use `port-pre-opt` before Optimization.
    - Move `port-post-analysis` to the end of the pipeline.
    - Add `--skip-analysis` flag to skip heavy visualization steps.
    - Add `--skip-validation` flag to skip Backtesting (`port-test`) for rapid iteration.
- [x] **Documentation**:
    - Update `docs/specs/production_workflow_v2.md` with the optimized Critical Path.

## 6. Completion
- [x] All tasks completed. System is streamlined for both Production (Full Integrity) and Development (Fast Iteration) workflows.
- [x] Documentation fully aligned with codebase.

## 7. Post-Refactor Audit & Fixes
- [x] **Fix `scripts/research_regime_v3.py`**:
    - Current implementation has hardcoded paths (`data/lakehouse/...`).
    - Needs to respect `RETURNS_MATRIX` env var and output to `data/runs/<ID>/data/`.

## 8. Phase 219: Dynamic Historical Backtesting (SDD & TDD)
- [x] **Design**: Create `docs/design/dynamic_backtesting_v1.md`.
    - Spec for `features_matrix.parquet` (Point-in-Time features).
    - Spec for `BacktestEngine` integration (Ranking at rebalance time).
- [x] **Test (TDD)**: Create `tests/test_backfill_features.py` defining expected behavior.
- [x] **Implementation**: Create `scripts/services/backfill_features.py`.
- [x] **Integration**: Update `BacktestEngine` to consume feature matrix.
- [x] **Automation**: Added `feature-backfill` target to Makefile.

## 9. Phase 246: Production Validation (Binance Spot Ratings)
- [x] **Data Ops**: Execute `make feature-backfill` to populate `data/lakehouse/features_matrix.parquet` (Verified).
- [x] **Atomic Runs**: Execute Production Flow for profile `binance_spot_rating_ma_long` (Verified Dynamic Filter active).
- [x] **Meta-Orchestration (Auto)**:
    - Execute `meta_ma_benchmark` with `--execute-sleeves` (Runs `ma_long` + `ma_short`).
    - Execute `meta_benchmark` with `--execute-sleeves` (Runs `all_long` + `all_short`).
- [x] **Forensic Audit**:
    - Generated Deep Reports (`port-deep-audit`) for atomic sleeves (`final_prod_v2_ma_long`, `final_prod_v2_all_long`).
    - Validated Lookahead Bias elimination via `features_matrix` usage in logs (see `13_validation.log` inspection).
    - **Meta-Audit**: Updated `generate_deep_report.py` to support "Meta-Fractal" ledger entries. Generated reports for `meta_benchmark_final_v1` and `meta_ma_benchmark_final_v1`.

## 10. Phase 250: Regime Detector Audit & Upgrade (SDD & TDD)
- [x] **Design**: Create `docs/design/regime_detector_upgrade_v1.md`.
    - Focus: Spectral Intelligence (DWT/Entropy) & Point-in-Time usage.
- [x] **Test (TDD)**: Create `tests/test_regime_detector.py`.
    - Test basic detection (CRISIS vs NORMAL).
    - Test spectral metrics (Turbulence).
- [x] **Refactor**: Update `MarketRegimeDetector` in `tradingview_scraper/regime.py`.
    - Added absolute volatility dampeners to fix "Flatline" classification.
    - Robustness improvements.
- [x] **Validation**: All TDD tests passed.

## 11. Final Sign-off
- [x] **Documentation**: All artifacts synchronized.
- [ ] **Archive**: Clean up test runs (Optional).
- [ ] **Complete**: System is fully validated for Production v3.5.3.

## 12. Phase 255: Regime Directional Research (SDD & TDD)
- [x] **Design**: Create `docs/design/regime_directional_filter_v1.md`.
    - Objective: Explore regime detector utility for confirming LONG/SHORT bias.
    - Metrics: Accuracy of regime vs subsequent 5d/10d return direction.
- [x] **Test (TDD)**: Create `tests/test_regime_direction.py`.
    - Define expected predictive capability or at least correlation structure.
- [x] **Research Script**: Implement `scripts/research/research_regime_direction.py`.
    - Load full history.
    - Compute rolling regime scores.
    - Calculate forward returns (next 5, 10, 20 days).
    - Analyze conditional distribution of returns given Regime/Quadrant.
- [x] **Analysis**: Generate a report summarizing findings.
    - **Result**: Initial research on Top 10 assets shows `CRISIS` quadrant has 53% win rate (Long), while `EXPANSION` has 33% (potentially counter-intuitive or mean-reverting data). `QUIET` regime has negative expectancy.
    - **Action**: Further tuning of `EXPANSION` thresholds required, or strategy should be Mean Reversion in Expansion?

## 13. Phase 260: HMM Regime Detector Research & Optimization (SDD & TDD)
- [x] **Design**: Create `docs/design/hmm_regime_optimization_v1.md`.
    - Objective: Evaluate stability and performance of `_hmm_classify`.
    - Hypothesis: 2-state Gaussian HMM on absolute returns effectively captures Volatility Regimes but may be unstable or slow.
- [x] **Test (TDD)**: Create `tests/test_hmm_detector.py`.
    - Test stability (does it return same state for same data?).
    - Test state separation (High Vol vs Low Vol).
- [x] **Research/Refactor**: Update `tradingview_scraper/regime.py`.
    - Tested `GMM` (4ms) vs `HMM` (30ms).
    - Found `GMM` fails to detect Crisis if the latest point is near zero (common in high-variance Gaussian).
    - **Optimization**: Kept `GaussianHMM` for correctness but reduced `n_iter=50` -> `10`. Speed improved to ~16ms.
- [x] **Benchmark**: Compare execution time and accuracy. HMM with `n_iter=10` is the winner.

## 14. Phase 265: Regime-Risk Integration & Portfolio Engine Audit
- [x] **Design**: Create `docs/design/regime_risk_integration_v1.md`.
    - Objective: Hook up `MarketRegimeDetector` to `BacktestEngine`.
    - Logic: Map `(Regime, Quadrant)` -> `EngineRequest(regime, market_environment)`.
- [x] **Test (TDD)**: Create `tests/test_regime_risk_integration.py`.
    - Verified `CustomClusteredEngine` adapts L2/Aggressor weights based on regime.
- [x] **Integration**: Update `scripts/backtest_engine.py`.
    - Instantiated `MarketRegimeDetector`.
    - Implemented per-window detection logic.
    - Fixed `EngineRequest` to use dynamic `regime` and `market_environment` instead of hardcoded "NORMAL".

## 15. Phase 270: Strategy-Specific Regime Ranker (SDD & TDD)
- [x] **Design**: Create `docs/design/strategy_regime_ranker_v1.md`.
    - Objective: Score assets based on their "fit" for a specific strategy (Trend vs MeanRev) given their current regime.
- [x] **Test (TDD)**: Create `tests/test_strategy_ranker.py`.
    - Verified Trend strategies prioritize positive AR/High Hurst.
    - Verified MeanRev strategies prioritize oscillating/Low Hurst.
- [x] **Implementation**: Create `tradingview_scraper/selection_engines/ranker.py`.
- [x] **Integration**: Updated `SelectionEngineV3` and `BacktestEngine` to use the ranker.
    - Strategy inferred from profile names (e.g. 'ma_long' -> trend, 'mean_rev' -> mean_reversion).

## 16. Final Sign-off (v3.5.3)
- [x] **Documentation**: All artifacts synchronized.
- [ ] **Archive**: Clean up test runs (Optional).
- [x] **Complete**: System is fully validated for Production v3.5.3 with Dynamic Regime-Aware Strategy Selection.
 
 ## 29. Phase 400: Telemetry & Ray Lifecycle (SDD & TDD)
- [x] **Design**: Create `docs/design/telemetry_standard_v1.md`.
    - Define OTel provider setup (Tracing, Metrics, Logging).
    - Define `trace_id` propagation rules for Ray workers.
- [x] **Design**: Create `docs/design/ray_lifecycle_v2.md`.
    - Graceful shutdown (`ray.shutdown`) via context manager.
    - Signal handling for cleanup.
- [x] **Test (TDD)**: Create `tests/test_telemetry_provider.py`.
    - Verify trace spans are emitted and linked.
    - Verify log injection of trace IDs.
- [x] **Test (TDD)**: Create `tests/test_ray_lifecycle.py`.
    - Verify `ray.shutdown()` is called on exit/failure.
- [x] **Implementation**:
    - Create `tradingview_scraper/telemetry/` package.
    - Refactor `tradingview_scraper/orchestration/compute.py` for context management.
    - Instrument `QuantSDK.run_stage` and `ProductionPipeline.run_step`.

## 30. Phase 410: Telemetry Hardening & Context Propagation (SDD & TDD)
- [x] **Design**: Update `docs/design/telemetry_standard_v1.md`.
    - Specify Trace Context propagation mechanism for Ray (Injection/Extraction).
    - Define standard metrics for `@trace_span`.
- [x] **Test (TDD)**: Create `tests/test_distributed_tracing.py`.
    - Verify `trace_id` is preserved across Ray actor boundaries.
- [x] **Test (TDD)**: Create `tests/test_telemetry_metrics.py`.
    - Verify `stage_duration_seconds` is emitted.
- [x] **Implementation**:
    - Add `tradingview_scraper/telemetry/context.py` for propagation helpers.
    - Update `RayComputeEngine` and `SleeveActorImpl` for context crossing.
    - Update `@trace_span` to emit metrics.
    - Refactor pipeline entry points to establish root traces.

 ---
 
 # Phase 300+: Fractal Framework Consolidation (Audit 2026-01-21)


## 17. Architecture Audit Summary

### 17.1 Existing Patterns (Preserve)
The following patterns are **already implemented** and should be preserved:

| Pattern | Location | Status |
| :--- | :--- | :--- |
| `BasePipelineStage` | `pipelines/selection/base.py` | **Production** |
| `SelectionContext` | `pipelines/selection/base.py` | **Production** |
| `BaseSelectionEngine` | `selection_engines/base.py` | **Production** |
| `BaseRiskEngine` | `portfolio_engines/base.py` | **Production** |
| HTR Loop Orchestration | `pipelines/selection/pipeline.py` | **Production** |
| Stage Composition | `pipelines/selection/stages/` | **Production** |
| Ranker Factory | `pipelines/selection/rankers/factory.py` | **Production** |

### 17.2 Identified Gaps (Address)
| Gap | Priority | Phase |
| :--- | :--- | :--- |
| `StrategyRegimeRanker` misplaced in `selection_engines/` | High | 305 |
| No formal `discovery/` module (scanners in `scripts/`) | Medium | 310 |
| Filters scattered across selection engines | Medium | 315 |
| No `MetaContext` for sleeve aggregation | High | 320 |
| No declarative pipeline composition from JSON | Low | 330 |

### 17.3 Proposed Consolidation (NOT New Architecture)
**Principle**: Extend existing patterns, do NOT create parallel structures.

```
tradingview_scraper/
├── pipelines/                       # EXISTING (Extend)
│   ├── selection/                   # EXISTING
│   │   ├── base.py                  # SelectionContext, BasePipelineStage
│   │   ├── pipeline.py              # SelectionPipeline (HTR Orchestrator)
│   │   ├── rankers/                 # EXISTING
│   │   │   ├── base.py
│   │   │   ├── mps.py
│   │   │   ├── signal.py
│   │   │   ├── regime.py            # NEW: Migrate StrategyRegimeRanker
│   │   │   └── factory.py
│   │   ├── stages/                  # EXISTING
│   │   │   ├── ingestion.py
│   │   │   ├── feature_engineering.py
│   │   │   ├── inference.py
│   │   │   ├── clustering.py
│   │   │   ├── policy.py
│   │   │   └── synthesis.py
│   │   └── filters/                 # NEW: Extract from policy.py
│   │       ├── base.py              # BaseFilter protocol
│   │       ├── darwinian.py         # Health vetoes
│   │       ├── spectral.py          # Entropy/Hurst vetoes
│   │       └── friction.py          # ECI filter
│   ├── discovery/                   # NEW: Migrate from scripts/scanners/
│   │   ├── base.py                  # BaseDiscoveryScanner
│   │   ├── tradingview.py
│   │   └── binance.py
│   └── meta/                        # NEW: Formalize meta-portfolio
│       ├── base.py                  # MetaContext, MetaStage
│       ├── aggregator.py            # SleeveAggregator
│       └── flattener.py             # Weight projection
├── portfolio_engines/               # EXISTING (Stable)
│   ├── base.py                      # BaseRiskEngine
│   └── impl/                        # EXISTING
│       ├── custom.py
│       ├── riskfolio.py
│       ├── skfolio.py
│       └── ...
└── selection_engines/               # EXISTING (Legacy, Freeze)
    ├── base.py                      # BaseSelectionEngine
    └── impl/                        # EXISTING
        ├── v3_4_htr.py              # HTR v3.4 (Active)
        └── v3_mps.py                # MPS v3.2 (Active)
```

## 18. Phase 305: Migrate StrategyRegimeRanker (SDD & TDD)
- [x] **Design**: Update `docs/design/strategy_regime_ranker_v1.md` with new location.
- [x] **Test (TDD)**: Ensure `tests/test_strategy_ranker.py` passes with new import path.
- [x] **Migration**:
    - Move `selection_engines/ranker.py` → `pipelines/selection/rankers/regime.py`.
    - Update imports in `selection_engines/impl/v3_mps.py`.
- [x] **Validation**: Run `make port-select` to verify.

## 19. Phase 310: Discovery Module (SDD & TDD)
- [x] **Design**: Create `docs/design/discovery_module_v1.md`.
- [x] **Test (TDD)**: Create `tests/test_discovery_scanners.py`.
- [x] **Implementation**:
    - Create `pipelines/discovery/base.py` with `BaseDiscoveryScanner`.
    - Create `pipelines/discovery/binance.py`.
    - Create `pipelines/discovery/tradingview.py`.
- [x] **Integration**: Update `DiscoveryPipeline` to register scanners and register as stage.

## 20. Phase 315: Filter Module Extraction (SDD & TDD)
- [x] **Design**: Create `docs/design/filter_module_v1.md`.
- [x] **Test (TDD)**: Create `tests/test_filters.py`.
- [x] **Implementation**:
    - Create `pipelines/selection/filters/base.py`.
    - Create `pipelines/selection/filters/darwinian.py`.
    - Create `pipelines/selection/filters/predictability.py`.
    - Create `pipelines/selection/filters/friction.py`.
- [x] **Refactor**: Update `PolicyStage` to delegate to filter chain.
- [x] **Registration**: Register filters in `StageRegistry`.

## 21. Phase 320: Meta-Portfolio Module (SDD & TDD)
- [x] **Design**: Create `docs/design/meta_portfolio_v1.md`.
- [x] **Test (TDD)**: Create `tests/test_meta_pipeline.py`.
- [x] **Implementation**:
    - Create `pipelines/meta/base.py` with `MetaContext`.
    - Create `pipelines/meta/aggregator.py` with `SleeveAggregator`.
    - Create `pipelines/meta/flattener.py` with `WeightFlattener`.
- [x] **Integration**: Refactor `scripts/run_meta_pipeline.py` to use new modules and register stages.

## 22. Phase 330: Declarative Pipeline Composition (Optional, Low Priority)
- [ ] **Design**: Create `docs/design/declarative_pipeline_v1.md`.
    - JSON schema for pipeline definition.
    - Factory to build `SelectionPipeline` from config.
- [ ] **Test (TDD)**: Create `tests/test_pipeline_factory.py`.
- [ ] **Implementation**: Create `pipelines/factory.py`.

---

# Phase 340+: Orchestration Layer (Audit 2026-01-21)

## 23. Orchestration Layer Overview

### 23.1 Design Document
See `docs/design/orchestration_layer_v1.md` for full specification.

### 23.2 Architecture Layers
```
┌────────────────────────────────────────────────────────────┐
│                   CLAUDE SKILL LAYER                       │
│  Addressable stage invocation via CLI/SDK                  │
│  quant://selection/ingestion?run_id=abc&profile=crypto     │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│               WORKFLOW ENGINE (Prefect/DBOS)               │
│  DAG orchestration, retries, observability, scheduling     │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│                  COMPUTE ENGINE (Ray)                      │
│  Parallel execution, actor isolation, distributed compute  │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│                   STAGE LOGIC LAYER                        │
│  BasePipelineStage, BaseRiskEngine, BaseFilter             │
└────────────────────────────────────────────────────────────┘
```

### 23.3 Current Ray Usage (Preserve & Extend)
| File | Pattern | Status |
| :--- | :--- | :--- |
| `scripts/parallel_orchestrator_ray.py` | `@ray.remote` task | Production |
| `scripts/parallel_orchestrator_native.py` | `@ray.remote` actor | Production |
| `scripts/run_meta_pipeline.py` | Sleeve parallelization | Production |

## 24. Phase 340: Stage Registry & SDK (SDD & TDD)
- [x] **Design**: See `docs/design/orchestration_layer_v1.md` Section 3.
- [x] **Test (TDD)**: Create `tests/test_stage_registry.py`.
- [x] **Test (TDD)**: Create `tests/test_quant_sdk.py`.
- [x] **Implementation**:
    - Create `tradingview_scraper/orchestration/__init__.py`.
    - Create `tradingview_scraper/orchestration/registry.py` with `StageRegistry`, `StageSpec`.
    - Create `tradingview_scraper/orchestration/sdk.py` with `QuantSDK`.
- [x] **CLI**: Create `scripts/quant_cli.py` with `stage` subcommand.
- [x] **Migration**: Add `SPEC` attribute or registration to existing stages.

## 25. Phase 345: Ray Compute Layer (SDD & TDD)
- [x] **Design**: See `docs/design/orchestration_layer_v1.md` Section 4.
- [x] **Test (TDD)**: Create `tests/test_ray_compute.py`.
- [x] **Implementation**:
    - Create `tradingview_scraper/orchestration/compute.py` with `RayComputeEngine`.
    - Create `tradingview_scraper/orchestration/sleeve_executor.py` with `SleeveActor`.
- [x] **Migration**: Update `scripts/run_meta_pipeline.py` to use `execute_sleeves_parallel()`.

## 26. Phase 350: Prefect Workflow Integration (SDD & TDD)
- [x] **Design**: See `docs/design/orchestration_layer_v1.md` Section 5.
- [x] **Test (TDD)**: Create `tests/test_prefect_flows.py`.
- [x] **Implementation**:
    - Create `tradingview_scraper/orchestration/flows/__init__.py`.
    - Create `tradingview_scraper/orchestration/flows/selection.py`.
    - Create `tradingview_scraper/orchestration/flows/meta.py`.
- [ ] **Integration**: Add Prefect deployment configs in `configs/prefect/`.

## 27. Phase 355: Claude Skill Integration (SDD & TDD)
- [x] **Design**: Create `docs/design/claude_skills_v1.md` with Agent Skills specification.
- [x] **Test (TDD)**: Create `tests/test_claude_skills.py`.
- [x] **Implementation**:
    - Create `.claude/skills/quant-select/SKILL.md` and scripts.
    - Create `.claude/skills/quant-backtest/SKILL.md` and scripts.
    - Create `.claude/skills/quant-discover/SKILL.md` and scripts.
    - Create `.claude/skills/quant-optimize/SKILL.md` and scripts.
- [x] **CLI Integration**: Ensure `scripts/quant_cli.py` supports skill script invocations.
- [x] **Documentation**: Update AGENTS.md with skill usage examples.

### Skill Structure (Agent Skills Standard)
```
.claude/skills/quant-select/
├── SKILL.md                    # Instructions + frontmatter (required)
└── scripts/
    └── run_pipeline.py         # Executable script
```

### SKILL.md Format
```markdown
---
name: quant-select                # 1-64 chars, lowercase, hyphens
description: Run selection...     # 1-1024 chars, when to use
allowed-tools: Bash(python:*) Read
---

# Instructions for Claude to follow...
```

## 28. Phase 360: Observability & Monitoring (Optional)
- [ ] **Design**: OpenTelemetry integration spec.
- [ ] **Implementation**:
    - Add tracing spans to stages.
    - Prometheus metrics export.
    - Grafana dashboard templates.

---

## Continuation Prompt (Updated 2026-01-21)

```
You are continuing work on a quantitative portfolio management platform located at:
/home/tommyk/projects/quant/data-sources/market-data/tradingview-scraper

## Context
This is a production-grade quantitative trading system with:
- 3-Pillar Architecture: Universe Selection → Strategy Synthesis → Portfolio Allocation
- Fractal Meta-Portfolio construction (Atomic sleeves aggregate into Meta portfolios)
- Dynamic regime detection with HMM-based volatility classification
- Point-in-time feature backfill to eliminate lookahead bias

## Completed Phases
- Phases 1-7: Workflow Streamlining
- Phase 219: Dynamic Historical Backtesting
- Phase 246-270: Regime Detection, Integration, Strategy-Specific Ranker

## Current Phase: 305-360 Framework & Orchestration Layer

### Phase Groups
1. **Phases 305-330**: Framework Consolidation (Module migrations, Meta-Portfolio)
2. **Phases 340-360**: Orchestration Layer (Ray, Prefect, Claude Skills)

### Key Design Principles
1. EXTEND existing patterns, do NOT create parallel structures
2. Every stage is callable/addressable via `quant://pipeline/stage/params`
3. Ray for compute, Prefect/DBOS for workflow orchestration
4. All stages emit structured audit events
5. Claude Skills follow Agent Skills open standard (SKILL.md files, not Python)

### Architecture Layers
```
CLAUDE SKILL LAYER (SKILL.md files following Agent Skills standard)
        ↓
WORKFLOW ENGINE (Prefect/DBOS - DAG, Retry, Observability)
        ↓
COMPUTE ENGINE (Ray - Parallel Execution)
        ↓
STAGE LOGIC (BasePipelineStage, BaseRiskEngine, BaseFilter)
```

### Existing Patterns to Preserve
- `BasePipelineStage` in `pipelines/selection/base.py`
- `SelectionContext` in `pipelines/selection/base.py`
- `BaseRiskEngine` in `portfolio_engines/base.py`
- Ray patterns in `scripts/parallel_orchestrator_*.py`

### Key Files to Read
1. `docs/specs/plan.md` - Master tracking
2. `docs/specs/requirements_v3.md` - Architecture with orchestration layer
3. `docs/design/fractal_framework_v1.md` - Module consolidation design
4. `docs/design/orchestration_layer_v1.md` - Ray/Prefect design
5. `docs/design/claude_skills_v1.md` - Claude Skills (Agent Skills standard)
6. `pipelines/selection/base.py` - Core abstractions

### Immediate Next Steps
Follow SDD/TDD flow for Phase 340 (Stage Registry & SDK):
1. Create `tests/test_stage_registry.py` with TDD tests
2. Implement `tradingview_scraper/orchestration/registry.py`
3. Create `tests/test_quant_sdk.py` with TDD tests
4. Implement `tradingview_scraper/orchestration/sdk.py`
5. Create `scripts/quant_cli.py` with stage subcommand

Track all progress in `docs/specs/plan.md`.
```

---

# Appendix A: Document Inventory (Updated 2026-01-21)

## A.1 Core Specifications

| Document | Purpose | Status |
| :--- | :--- | :--- |
| `docs/specs/requirements_v3.md` | 3-Pillar Architecture, Modular Pipeline, Orchestration Layer | **Active** |
| `docs/specs/production_workflow_v2.md` | Production workflow phases and optimization | **Active** |
| `docs/specs/numerical_stability.md` | Stable Sum Gate, SSP Minimums | **Active** |
| `docs/specs/crypto_sleeve_v2.md` | Crypto-specific operations and parameters | **Active** |

## A.2 Design Documents (Recent)

| Document | Phase | Purpose |
| :--- | :--- | :--- |
| `docs/design/claude_skills_v1.md` | 355 | Agent Skills standard, SKILL.md format, quant skills |
| `docs/design/orchestration_layer_v1.md` | 340-360 | Ray compute, Prefect workflow, Stage Registry, SDK |
| `docs/design/fractal_framework_v1.md` | 305-330 | Module consolidation, Meta-Portfolio abstractions |
| `docs/design/strategy_regime_ranker_v1.md` | 270 | Strategy-specific asset scoring |
| `docs/design/regime_risk_integration_v1.md` | 265 | Regime detection → Portfolio engine integration |
| `docs/design/hmm_regime_optimization_v1.md` | 260 | HMM vs GMM comparison, n_iter optimization |
| `docs/design/regime_directional_filter_v1.md` | 255 | Regime → directional bias research |
| `docs/design/regime_detector_upgrade_v1.md` | 250 | Absolute volatility dampeners |
| `docs/design/dynamic_backtesting_v1.md` | 219 | Point-in-time features_matrix.parquet |

## A.3 Implementation Status by Phase

### Completed Phases

| Phase | Description | Key Deliverables |
| :--- | :--- | :--- |
| 1-7 | Workflow Streamlining | Parallelized flow-data, split port-analyze |
| 219 | Dynamic Historical Backtesting | features_matrix.parquet, BacktestEngine |
| 246 | Production Validation | meta_benchmark runs, forensic audits |
| 250 | Regime Detector Upgrade | Flatline fix, absolute dampeners |
| 255 | Regime Directional Research | CRISIS 53% win rate analysis |
| 260 | HMM Optimization | n_iter=10 (50% speedup) |
| 265 | Regime-Risk Integration | Dynamic L2/Aggressor in BacktestEngine |
| 270 | Strategy-Specific Ranker | StrategyRegimeRanker |

### Pending Phases

### Phase Roadmap: Architecture & Integration (300-360)

| Phase | Description | Status | Dependencies |
| :--- | :--- | :--- | :--- |
| 345 | **Ray Compute Layer (Sleeves)** | **Completed** | 340 |
| 346 | **Ray Integration Validation (Meta)** | **Completed** | 345 |
| 347 | **SDK-Driven Meta Orchestration** | **Completed** | 340, 346 |
| 348 | **Orchestration Hardening** | **Completed** | 347 |
| 350 | **Prefect Workflow Integration** | Planned | 340, 345 |
| 351 | **Orchestration Forensic Audit** | **Completed** | 347, 350 |
| 352 | **Ray Production Re-Validation** | **Completed** | 348, 351 |
| 353 | **Full Ray Production Run** | In Progress | 352 |
| 355 | Claude Skills | **Completed** | 340 |


| 360 | Observability & Monitoring | Planned | 350 |

| 360 | Observability | Planned (Optional) | 350 |

---

# Appendix B: Session Audit Log (2026-01-21)

## B.1 This Session's Work

### Audit Performed
1. Reviewed continuation plan vs codebase reality
2. Identified redundancies (BasePipelineStage, SelectionContext already exist)
3. Identified valid gaps (Discovery, Filters, MetaContext)
4. Researched Claude Code skills best practices
5. Discovered Agent Skills open standard

### Documents Created
- `docs/design/fractal_framework_v1.md` - Module consolidation
- `docs/design/orchestration_layer_v1.md` - Ray/Prefect/SDK
- `docs/design/claude_skills_v1.md` - Agent Skills compliant skills

### Documents Updated
- `docs/specs/plan.md` - Added Phases 300-360
- `docs/specs/requirements_v3.md` - Added Sections 4 (Modular Architecture) and 5 (Orchestration Layer)

### Critical Corrections
1. **Skills are NOT Python functions** - They are SKILL.md files with Markdown instructions
2. **Agent Skills standard** - Portable across Claude Code, OpenCode, etc.
3. **EXTEND don't duplicate** - Use existing BasePipelineStage, SelectionContext

## B.2 Key Decisions Made

| Decision | Rationale |
| :--- | :--- |
| Use existing `BasePipelineStage` | Already production, avoid duplication |
| Skills as SKILL.md files | Agent Skills standard compliance |
| Ray for compute, Prefect for workflow | Separation of concerns |
| Progressive disclosure for skills | Minimize context usage |
| Addressable stages via CLI/SDK | Enable Claude skill integration |

## B.3 Open Questions (For Future Sessions)

1. **Prefect vs DBOS**: Which workflow engine to prioritize?
2. **Stage Registry granularity**: Register every stage or just entry points?
3. **Skill bundled scripts**: Python only or also Bash/Make?

---

# Appendix C: Full Data + Meta Pipeline Audit Plan (2026-01-22)

This appendix is the **active checklist** for reviewing and auditing:
1) the **DataOps** pipeline (`flow-data`) and
2) the **Meta-Portfolio** pipeline (`flow-meta-production`)

Goal: produce a high-integrity “contract-level” understanding of the platform’s end-to-end behavior, surface defects, and define a prioritized remediation backlog.

## C.1 Scope & Non-Negotiables

### In Scope
- Data cycle: discovery → ingestion → metadata → feature ingestion → feature backfill → repair/audit.
- Alpha cycle touchpoints that consume lakehouse outputs (read-only contract enforcement).
- Meta-portfolio: sleeve aggregation → meta optimization → recursive flattening → reporting/audit gates.

### Out of Scope (For This Pass)
- Live trading / OMS / MT5 execution (unless meta/atomic artifacts rely on these paths).
- Strategy research changes (signal design), unless required for correctness (e.g., SHORT inversion semantics).

### Non-Negotiables (Institutional Standards)
- **No padding weekends for TradFi**: never zero-fill to align calendars (inner-join only for crypto↔tradfi correlation/meta).
- **Point-in-time fidelity**: backtests must not use future features / “latest ratings” for historical decisions.
- **Replayability**: every production decision must be reconstructable from `audit.jsonl` + `resolved_manifest.json`.
- **Isolation**: the Alpha cycle must not make outbound network calls; only DataOps can mutate the lakehouse.

## C.2 Pipeline Map (Entry Points + Artifact Contracts)

### Data Cycle (“flow-data”)
- **Entry**: `make flow-data`
- **Stages / Commands**
  - Discovery: `make scan-run` → `scripts/compose_pipeline.py` → `tradingview_scraper/pipelines/discovery/`
  - Price ingestion: `make data-ingest` → `scripts/services/ingest_data.py` → `PersistentDataLoader` → `data/lakehouse/*_1d.parquet`
  - Metadata: `make meta-ingest` → `scripts/build_metadata_catalog.py`, `scripts/fetch_execution_metadata.py`
  - Feature ingestion: `make feature-ingest` → `scripts/services/ingest_features.py` → `data/lakehouse/features/tv_technicals_1d/`
  - PIT features: `make feature-backfill` → `scripts/services/backfill_features.py` → `data/lakehouse/features_matrix.parquet`
  - Repair: `make data-repair` → `scripts/services/repair_data.py`

### Alpha Cycle (“flow-production”)
- **Entry**: `make flow-production PROFILE=<profile>`
- **Orchestrator**: `scripts/run_production_pipeline.py`
- **Contract**: assumes DataOps already produced a clean lakehouse; Alpha flow is read-only and snapshots into `data/artifacts/summaries/runs/<RUN_ID>/`.

### Meta Cycle (“flow-meta-production”)
- **Entry**: `make flow-meta-production PROFILE=<meta_profile>`
- **Orchestrator**: `scripts/run_meta_pipeline.py`
- **Stages (SDK)**
  - Build meta returns: `QuantSDK.run_stage("meta.returns", ...)` → `scripts/build_meta_returns.py`
  - Optimize meta: `QuantSDK.run_stage("meta.optimize", ...)` → `scripts/optimize_meta_portfolio.py`
  - Flatten: `QuantSDK.run_stage("meta.flatten", ...)` → `scripts/flatten_meta_weights.py`
  - Report: `QuantSDK.run_stage("meta.report", ...)` → `scripts/generate_meta_report.py`

## C.3 Audit Checklist (What “PASS” Looks Like)

### C.3.1 Settings / Manifest / Override Precedence
- Confirm the precedence chain is stable:
  - `configs/manifest.json` defaults
  - profile overrides
  - `TV_*` env overrides (including `MAKE` wrappers)
  - resolved snapshot: `data/artifacts/summaries/runs/<RUN_ID>/config/resolved_manifest.json`
- PASS if:
  - `make env-check` passes.
  - `resolved_manifest.json` contains the effective values (no missing blocks, no “mystery defaults”).

### C.3.2 Discovery → Export Contract
- Verify discovery produces export files at:
  - `data/export/<RUN_ID>/*.json`
- Verify candidate schema contains at least:
  - `symbol` (string, ideally `EXCHANGE:SYMBOL`)
  - optional: `exchange`, `type/profile`, `metadata.logic` / strategy tag
- PASS if:
  - `make scan-run` produces ≥1 export JSON file.
  - `make data-ingest` can parse and ingest without schema errors.

### C.3.3 Ingestion / Lakehouse Integrity
- Verify each ingested symbol produces:
  - `data/lakehouse/<SAFE_SYMBOL>_1d.parquet`
- Verify ingestion guardrails:
  - freshness skip works (mtime-based)
  - toxicity checks run on newly ingested files (|r| bounds as spec’d)
  - no silent “write elsewhere” mismatch between fetcher and validator
- PASS if:
  - `make data-audit` reports zero missing bars in strict mode for production profiles.
  - repair can fill gaps and does not introduce duplicates/out-of-order candles.

### C.3.4 Feature Store / PIT Feature Fidelity
- Verify `feature-ingest` writes snapshot partitions under:
  - `data/lakehouse/features/tv_technicals_1d/date=YYYY-MM-DD/part-*.parquet`
- Verify `feature-backfill` produces:
  - `data/lakehouse/features_matrix.parquet` (point-in-time correct)
- PASS if:
  - backtests and selection stages that claim PIT actually read from `features_matrix.parquet` (and audit ledger records the hash).

### C.3.5 Alpha Cycle (“flow-production”) Read-Only Enforcement
- Verify Alpha pipeline does NOT call network APIs (no TradingView/CCXT/WebSocket).
- Verify Alpha pipeline snapshots lakehouse inputs into `run_dir/data/`.
- PASS if:
  - a run can be replayed using only artifacts in `data/artifacts/summaries/runs/<RUN_ID>/`.

### C.3.6 Meta Cycle (“flow-meta-production”) Forensic Integrity
- Verify meta aggregation joins sleeve returns via **inner join** on dates.
- Verify sleeve health guardrail is applied (>= 75% success for consumed streams).
- Verify directional sign test gate behavior:
  - meta-level gate (`feat_directional_sign_test_gate`)
  - atomic-level gate (`feat_directional_sign_test_gate_atomic`)
- PASS if:
  - meta artifacts exist in isolated meta run dir, and `latest/meta_portfolio_report.md` is updated.
  - flattened weights sum and sign conventions are sane (short weights negative at physical layer).

## C.4 Initial Issues Spotted (From Repo Recon)

These are concrete, code-level items worth addressing early because they can silently corrupt “truth” in the audit chain.

### High Priority (Correctness / Reproducibility)
1. **Duplicate `selection_mode` in settings**
   - Location: `tradingview_scraper/settings.py`
   - Observation: `FeatureFlags` defines `selection_mode` twice (two different defaults). In Python/Pydantic, the latter declaration wins, which can silently override manifest defaults and CLI overrides.
   - Risk: non-deterministic or surprising selection behavior across environments.

2. **Discovery validation path mismatch**
   - Location: `scripts/run_production_pipeline.py`
   - Observation: `validate_discovery()` checks `export/<RUN_ID>` but DataOps writes to `data/export/<RUN_ID>`.
   - Risk: false “0 discovery files” metrics in audit ledger / progress output.

3. **Lakehouse path injection mismatch in ingestion**
   - Location: `scripts/services/ingest_data.py`, `tradingview_scraper/symbols/stream/persistent_loader.py`
   - Observation: ingestion can be given a custom `lakehouse_dir`, but `PersistentDataLoader()` is created without that path; validator then checks a different directory than the writer.
   - Risk: toxicity checks can silently validate the wrong file (or miss newly written data).

4. **Meta pipeline manifest path hardcode (sleeve execution)**
   - Location: `scripts/run_meta_pipeline.py`
   - Observation: when `--execute-sleeves` is enabled, the manifest is opened via a hard-coded `configs/manifest.json`, rather than `settings.manifest_path` (or a CLI arg).
   - Risk: meta runs become non-replayable when alternative manifests are used.

### Medium Priority (Schema / Maintainability)
1. **Discovery scanner interface mismatch**
   - Location: `tradingview_scraper/pipelines/discovery/base.py`, `tradingview_scraper/pipelines/discovery/tradingview.py`, `tradingview_scraper/pipelines/discovery/pipeline.py`
   - Observation: base scanner API expects a dict of params, but `DiscoveryPipeline` calls `discover(str(path))` and also creates but doesn’t use a params dict.
   - Risk: future scanners will diverge or break composition.

2. **Candidate identity double-prefix risk**
   - Location: `tradingview_scraper/pipelines/discovery/base.py`, `tradingview_scraper/pipelines/discovery/tradingview.py`
   - Observation: if `symbol` is already `EXCHANGE:SYMBOL`, `CandidateMetadata.identity` can become `EXCHANGE:EXCHANGE:SYMBOL`.
   - Risk: downstream consumers that rely on `identity` for uniqueness will behave incorrectly.

3. **Legacy “fill NaNs with 0” pipeline remains**
   - Location: `tradingview_scraper/pipeline.py`
   - Observation: returns alignment uses `fillna(0.0)` which violates the platform’s “No Padding” standard for TradFi calendars.
   - Risk: an unused-but-present orchestrator can be mistakenly used as reference or invoked by accident.

## C.5 Remediation Backlog (Proposed)

### Phase 370: Correctness Hardening (High Priority)
- Remove duplicate `selection_mode` field in settings; add a single authoritative default.
- Fix `validate_discovery()` to use `data/export/<RUN_ID>` (or read `settings.export_dir`).
- Ensure ingestion and validation share the same lakehouse base path (plumb through `PersistentDataLoader(lakehouse_path=...)`).
- Un-hardcode manifest path usage in meta pipeline sleeve execution path.

### Phase 380: Contract Tightening (Medium Priority)
- Standardize discovery output schema and enforce with a validator (fail fast in DataOps).
- Normalize `CandidateMetadata` identity rules and document expected symbol formats.
- Move or clearly mark legacy orchestrators to avoid accidental use.

### Phase 390: Meta Pipeline Robustness (Medium Priority)
- Treat meta cache artifacts as a first-class, auditable dependency:
  - include cache key + underlying sleeve run IDs in the meta run’s audit ledger.
- Strengthen invariants on flattening:
  - enforce stable sum gate at meta layer
  - verify sign conventions after recursion

## C.6 SDD / TDD Worklist (Phase 370)

- Primary TODO list (live checklist): `docs/specs/phase370_correctness_hardening_todo.md`
- Design reference (how-to): `docs/design/correctness_hardening_phase370_v1.md`
- Requirements reference (what/why): `docs/specs/requirements_v3.md` (Section 6)

---

# Appendix D: Full Data + Meta Pipeline Audit Plan (SDD Edition) (2026-01-22)

This appendix is the **living, specs-driven** plan to review and audit:
- the **full DataOps pipeline** (Discovery → Ingestion → Metadata → Features → PIT Backfill → Repair/Audit)
- the **full Meta-Portfolio pipeline** (Sleeves → Meta Returns → Meta Optimize → Flatten → Report)

The goal is to keep the audit work **tightly coupled** to SDD:
1) update specs/requirements (what/why),
2) update design docs (how),
3) add tests (TDD),
4) implement changes,
5) validate via forensic artifacts.

## D.1 References (SDD Source of Truth)
- SDD process: `docs/specs/sdd_flow.md`
- Requirements (incl. Phase 370 invariants): `docs/specs/requirements_v3.md`
- DataOps contract: `docs/specs/dataops_architecture_v1.md`
- Meta pipeline streamlining: `docs/specs/meta_streamlining_v1.md`
- Reproducibility/determinism: `docs/specs/reproducibility_standard.md`
- Phase 370 design: `docs/design/correctness_hardening_phase370_v1.md`
- Phase 370 checklist: `docs/specs/phase370_correctness_hardening_todo.md`

## D.2 Audit Execution Runbook (What to Run)

### D.2.1 Preflight (Always)
- `make env-check`
- `make scan-audit`
- `make data-audit STRICT_HEALTH=1` (production-integrity check)

### D.2.2 DataOps (Mutates lakehouse; allowed network)
- `make flow-data PROFILE=<profile>`
- `make feature-backfill` (when PIT backtests are required)
- `make data-repair` (when health audit indicates gaps/staleness)

### D.2.3 Atomic Alpha (Must be read-only)
- `make flow-production PROFILE=<profile>`
- Optional: `make atomic-audit RUN_ID=<RUN_ID> PROFILE=<profile>`

### D.2.4 Meta (Fractal)
- `make flow-meta-production PROFILE=<meta_profile>`
- Optional gates:
  - `uv run scripts/audit_directional_sign_test.py --meta-profile <meta_profile>`
  - `uv run scripts/validate_sleeve_health.py --run-id <RUN_ID>`

## D.3 Audit Gates (PASS/FAIL Criteria)

### DataOps Gates
- Export path is correct and non-empty: `data/export/<RUN_ID>/*.json`
- Lakehouse ingestion is consistent: `data/lakehouse/<SAFE_SYMBOL>_1d.parquet` created and health-auditable
- Toxic data is dropped before optimizer exposure (|daily return| threshold)
- Metadata is present for all symbols used downstream (tick size / pricescale / timezone / session)

### Alpha Gates
- Alpha run is replayable from:
  - `data/artifacts/summaries/runs/<RUN_ID>/config/resolved_manifest.json`
  - `data/artifacts/summaries/runs/<RUN_ID>/audit.jsonl`
  - `data/artifacts/summaries/runs/<RUN_ID>/data/*`
- Alpha run does not make outbound network calls (TradingView/CCXT/WebSocket)

### Meta Gates
- Meta uses inner join on dates; never zero-fill calendar gaps
- Meta artifacts live inside the meta run’s isolated dir (not in lakehouse unless explicitly intended)
- Meta uses active manifest (no hard-coded `configs/manifest.json`)

## D.4 Issues & Improvements (Current Findings)

These are the next high-value items to audit/remediate after Phase 370 correctness hardening.

### D.4.1 Alpha/Prep: Default network behavior is unsafe
- File: `scripts/prepare_portfolio_data.py:80`
- Current: `PORTFOLIO_DATA_SOURCE` defaults to `"fetch"`.
- Risk: if invoked without the Makefile guardrail, it can pull network data during an “Alpha” run, violating the read-only contract.
- SDD action: change default to `"lakehouse_only"` and require explicit opt-in to network ingestion.

### D.4.2 Alpha/Prep: Dead import path for ingestion orchestrator
- File: `scripts/prepare_portfolio_data.py:83`
- Current: imports `tradingview_scraper.pipelines.data.orchestrator.DataPipelineOrchestrator` but no such module exists.
- Risk: any run with `PORTFOLIO_DATA_SOURCE != lakehouse_only` will fail at runtime.
- SDD action: either implement the missing module or remove/replace this code path (and document the supported ingestion entrypoints).

### D.4.3 Alpha/Prep: Hard-coded lakehouse candidate fallback
- File: `scripts/prepare_portfolio_data.py:42`
- Current: falls back to `"data/lakehouse/portfolio_candidates.json"` (string literal).
- Risk: violates determinism/path invariants; bypasses `settings.lakehouse_dir`.
- SDD action: use `settings.lakehouse_dir` when fallback is permitted, and deny fallback when `TV_STRICT_ISOLATION=1`.

### D.4.4 Modular Selection Pipeline: Hard-coded lakehouse defaults
- Files:
  - `tradingview_scraper/pipelines/selection/stages/ingestion.py:22`
  - `tradingview_scraper/pipelines/selection/pipeline.py:22`
- Current: default candidates/returns paths are `data/lakehouse/...`.
- Risk: modular pipeline is easier to accidentally call; defaults should be settings-driven and/or require explicit paths.
- SDD action: accept paths from settings or require caller-provided paths in constructors.

### D.4.5 Meta/Validation: Wrong artifacts root + calendar padding
- File: `scripts/validate_meta_parity.py:21`
- Current: uses `artifacts/summaries/...` (missing `data/` prefix) and fills missing returns with `0.0` (`scripts/validate_meta_parity.py:72`).
- Risk: validation tool can silently point to the wrong run dir and violates “No Padding”.
- SDD action: resolve run dir via `get_settings().summaries_runs_dir` and align returns via inner join / dropna.

### D.4.6 Meta scripts still contain lakehouse hard-coded fallbacks
- Files:
  - `scripts/optimize_meta_portfolio.py:135`
  - `scripts/flatten_meta_weights.py:40`
- Risk: conflicts with the determinism standard (“derive paths from settings”), and makes multi-env runs brittle.
- SDD action: replace `Path("data/lakehouse")` with `settings.lakehouse_dir` and log the resolved paths to the audit ledger.

## D.5 Next SDD Phases (Proposed)

### Phase 371: Path Determinism Sweep (High Priority)
- Replace literal `data/lakehouse` / `artifacts/summaries` strings with settings-derived paths across core scripts.
- Add targeted tests for the most invoked entrypoints (prep, validate, meta).

### Phase 372: Alpha Read-Only Enforcement (High Priority)
- Make read-only the default for any “alpha” entrypoint (`prepare_portfolio_data`).
- Add a “deny network” guardrail that fails fast unless an explicit DataOps mode is enabled.

### Phase 373: Modular Pipeline Safety (Medium Priority)
- Ensure `pipelines/selection/*` cannot silently read stale shared lakehouse artifacts without the run-dir context.

### Phase 374: Validation Tools “No Padding” Compliance (Medium Priority)
- Update parity/validation tools to use calendar-safe joins (inner join / dropna) and log alignment stats.

## D.6 Active SDD/TDD Checklist (Phases 371–374)
- TODO list: `docs/specs/phase371_374_sdd_todo.md`
- Design docs:
  - `docs/design/path_determinism_phase371_v1.md`
  - `docs/design/alpha_readonly_enforcement_phase372_v1.md`
  - `docs/design/modular_pipeline_safety_phase373_v1.md`
  - `docs/design/validation_no_padding_phase374_v1.md`

## D.7 Status Update (Phases 371–374)

As of **2026-01-22**, Phases **371–374** are implemented and tracked via:
- Checklist: `docs/specs/phase371_374_sdd_todo.md`
- Tests:
  - `tests/test_phase371_374_sdd.py`
  - `tests/test_phase373_modular_pipeline_safety.py`

## D.8 Next Phase: 380 Contract Tightening (Candidate Schema Gate)

Focus: tighten the **DataOps discovery→lakehouse boundary** so candidates are canonical and fail-fast in strict runs.

References:
- Requirements: `docs/specs/requirements_v3.md` (Section 8)
- Design: `docs/design/contract_tightening_phase380_v1.md`
- TODO checklist: `docs/specs/phase380_contract_tightening_todo.md`

Primary gate:
- DataOps MUST normalize and validate candidate exports before writing `data/lakehouse/portfolio_candidates.json`.
