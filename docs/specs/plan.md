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
- [ ] **Design**: Update `docs/design/strategy_regime_ranker_v1.md` with new location.
- [ ] **Test (TDD)**: Ensure `tests/test_strategy_ranker.py` passes with new import path.
- [ ] **Migration**:
    - Move `selection_engines/ranker.py` → `pipelines/selection/rankers/regime.py`.
    - Update imports in `selection_engines/impl/v3_mps.py`.
    - Deprecate old path with import alias.
- [ ] **Validation**: Run `make port-select` to verify.

## 19. Phase 310: Discovery Module (SDD & TDD)
- [ ] **Design**: Create `docs/design/discovery_module_v1.md`.
    - Define `BaseDiscoveryScanner` protocol: `discover(params) -> List[CandidateMetadata]`.
    - Inventory existing scanners in `scripts/scanners/`.
- [ ] **Test (TDD)**: Create `tests/test_discovery_scanners.py`.
    - Mock network calls.
    - Verify candidate schema compliance.
- [ ] **Implementation**:
    - Create `pipelines/discovery/base.py` with `BaseDiscoveryScanner`.
    - Migrate `scripts/scanners/binance_spot_scanner.py` → `pipelines/discovery/binance.py`.
    - Migrate `scripts/scanners/tradingview_scanner.py` → `pipelines/discovery/tradingview.py`.
- [ ] **Integration**: Update `scan-run` Makefile target.

## 20. Phase 315: Filter Module Extraction (SDD & TDD)
- [ ] **Design**: Create `docs/design/filter_module_v1.md`.
    - Define `BaseFilter` protocol: `apply(context) -> context` (veto candidates).
    - Extract filter logic from `PolicyStage`.
- [ ] **Test (TDD)**: Create `tests/test_filters.py`.
    - Test Darwinian filter (health vetoes).
    - Test Spectral filter (entropy/hurst vetoes).
- [ ] **Implementation**:
    - Create `pipelines/selection/filters/base.py`.
    - Create `pipelines/selection/filters/darwinian.py`.
    - Create `pipelines/selection/filters/spectral.py`.
    - Create `pipelines/selection/filters/friction.py`.
- [ ] **Refactor**: Update `PolicyStage` to delegate to filter chain.

## 21. Phase 320: Meta-Portfolio Module (SDD & TDD)
- [ ] **Design**: Create `docs/design/meta_portfolio_v1.md`.
    - Define `MetaContext` (extends `SelectionContext` with sleeve-level data).
    - Define `SleeveAggregator` (builds meta-returns matrix).
    - Define `WeightFlattener` (projects meta-weights to atoms).
- [ ] **Test (TDD)**: Create `tests/test_meta_pipeline.py`.
    - Test sleeve aggregation (3 sleeves → 1 meta-returns matrix).
    - Test weight flattening (meta-weights × sleeve-weights = atom-weights).
- [ ] **Implementation**:
    - Create `pipelines/meta/base.py` with `MetaContext`.
    - Create `pipelines/meta/aggregator.py` with `SleeveAggregator`.
    - Create `pipelines/meta/flattener.py` with `WeightFlattener`.
- [ ] **Integration**: Refactor `scripts/run_meta_pipeline.py` to use new modules.

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
- [ ] **Design**: See `docs/design/orchestration_layer_v1.md` Section 3.
- [ ] **Test (TDD)**: Create `tests/test_stage_registry.py`.
    - Test stage registration via decorator.
    - Test stage lookup by ID.
    - Test listing stages by tag.
- [ ] **Test (TDD)**: Create `tests/test_quant_sdk.py`.
    - Test `QuantSDK.run_stage()` invocation.
    - Test `QuantSDK.run_pipeline()` invocation.
- [ ] **Implementation**:
    - Create `tradingview_scraper/orchestration/__init__.py`.
    - Create `tradingview_scraper/orchestration/registry.py` with `StageRegistry`, `StageSpec`.
    - Create `tradingview_scraper/orchestration/sdk.py` with `QuantSDK`.
- [ ] **CLI**: Create `scripts/quant_cli.py` with `stage` subcommand.
    - `quant stage list [--tag TAG]`
    - `quant stage schema STAGE_ID`
    - `quant stage run STAGE_ID --run-id ID --param KEY=VALUE`
- [ ] **Migration**: Add `SPEC` attribute to existing stages in `pipelines/selection/stages/`.

## 25. Phase 345: Ray Compute Layer (SDD & TDD)
- [ ] **Design**: See `docs/design/orchestration_layer_v1.md` Section 4.
- [ ] **Test (TDD)**: Create `tests/test_ray_compute.py`.
    - Test `execute_stage_remote` function.
    - Test `RayComputeEngine.map_stages()` parallel execution.
    - Test `SleeveActor` isolation.
- [ ] **Implementation**:
    - Create `tradingview_scraper/orchestration/compute.py` with `RayComputeEngine`.
    - Create `tradingview_scraper/orchestration/sleeve_executor.py` with `SleeveActor`.
- [ ] **Migration**: Update `scripts/run_meta_pipeline.py` to use `execute_sleeves_parallel()`.
- [ ] **Deprecation**: Mark `scripts/parallel_orchestrator_*.py` as deprecated.

## 26. Phase 350: Prefect Workflow Integration (SDD & TDD)
- [ ] **Design**: See `docs/design/orchestration_layer_v1.md` Section 5.
- [ ] **Test (TDD)**: Create `tests/test_prefect_flows.py`.
    - Test `selection_flow` execution.
    - Test retry behavior on failure.
    - Test task caching.
- [ ] **Implementation**:
    - Create `tradingview_scraper/orchestration/flows/__init__.py`.
    - Create `tradingview_scraper/orchestration/flows/selection_flow.py`.
    - Create `tradingview_scraper/orchestration/flows/meta_flow.py`.
    - Create `tradingview_scraper/orchestration/flows/discovery_flow.py`.
- [ ] **Integration**: Add Prefect deployment configs in `configs/prefect/`.
- [ ] **Alternative**: Create `tradingview_scraper/orchestration/flows/dbos_flow.py` for lightweight option.

## 27. Phase 355: Claude Skill Integration (SDD & TDD)

**Standard**: [Agent Skills](https://agentskills.io) open standard (portable across Claude Code, OpenCode, etc.)

**Key Insight**: Skills are NOT Python functions. They are **SKILL.md files** with Markdown instructions.

- [x] **Design**: Create `docs/design/claude_skills_v1.md` with Agent Skills specification.
- [ ] **Test (TDD)**: Create `tests/test_claude_skills.py`.
    - Test SKILL.md frontmatter validation (name, description format).
    - Test bundled script syntax validity.
    - Test skill directory structure compliance.
- [ ] **Implementation**:
    - Create `.claude/skills/quant-select/SKILL.md` and scripts.
    - Create `.claude/skills/quant-backtest/SKILL.md` and scripts.
    - Create `.claude/skills/quant-discover/SKILL.md` and scripts.
    - Create `.claude/skills/quant-optimize/SKILL.md` and scripts.
- [ ] **CLI Integration**: Ensure `scripts/quant_cli.py` supports skill script invocations.
- [ ] **Documentation**: Update AGENTS.md with skill usage examples.

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

| Phase | Description | Status | Dependencies |
| :--- | :--- | :--- | :--- |
| 305 | Migrate StrategyRegimeRanker | **Completed** | None |
| 310 | Discovery Module | **Completed** | None |
| 315 | Filter Module Extraction | **Completed** | None |
| 320 | Meta-Portfolio Module | **Completed** | 305, 315 |
| 330 | Declarative Pipeline | Planned (Low) | 310-320 |
| 340 | Stage Registry & SDK | **Completed** | 305-320 |
| 345 | Ray Compute Layer | Planned | 340 |
| 350 | Prefect Workflow | Planned | 340, 345 |
| 355 | Claude Skills | **Completed** | 340 |

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
