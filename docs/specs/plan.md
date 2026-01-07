# Plan: Institutional ETF Scanner Audit & Expansion

## Objective
Audit and expand the institutional ETF scanners to capture high-alpha niche/thematic opportunities currently filtered out by strict liquidity or category constraints. We aim to identify "Alpha Pockets" in thematic equities, high-yield bonds, and alternative strategies.

## Context
Current scanners use a $10M liquidity floor and a limited set of TradingView category IDs. Initial research suggests we are missing categories (e.g., Buffer ETFs, Longevity, specific thematic buckets) and potentially filtering out high-quality niche ETFs that trade between $2M-$10M.

## Execution Phases

### Phase 1: Deep Mapping (Research)
**Goal**: Decode the TradingView "Category ID" map to understand the full spectrum of available assets.
- [x] **Script Upgrade**: Modify `scripts/research_etf_params.py` to fetch a broad sample (N=500) without category filters.
- [x] **Data Analysis**: Group results by `category` ID to generate a `ID -> Description` map.
- [x] **Gap Analysis**: Identify high-performing categories (High `Perf.1M` + Acceptable Liquidity) not currently targeted by L4 scanners.

### Phase 2: Scanner Expansion (Implementation)
**Goal**: Create new targeted scanners and relaxed-constraint universes to capture missed alpha.
- [x] **New Scanner**: `etf_thematic_momentum` (Equities/Alternatives).
- [x] **New Scanner**: `etf_yield_alpha` (Credit/Fixed Income).
- [x] **New Base Universe**: `dynamic_etf_discovery_niche` ($2M Floor).

### Phase 3: Validation (Audit)
**Goal**: Ensure new sources are tradeable, distinct, and additive.
- [x] **Run Scanners**: Execute the new scanners.
- [x] **Overlap Check**: Ensure `etf_thematic_momentum` isn't just duplicating `etf_equity_momentum`.
- [x] **Liquidity Audit**: Verify that the $2M-$10M cohort has sufficient liquidity.
- [x] **Attribute Verification**: Validated new fields (`aum`, `expense_ratio`, `dividend_yield_recent`) and integrated them into columns.
- [x] **Sorting Logic**: Implemented "Volume First, Alpha Second" logic with `prefilter_limit: 300` to solve selection starvation.
- [x] **Documentation**: Update `docs/specs/institutional_etf_scanners.md`.

### Phase 4: Architecture & Audit Documentation
**Goal**: Codify the "Liquid Winners" architecture and debugging tools.
- [x] **Filter Architecture**: Documented the 3-layer split (API -> Client -> Rank) in `etf_dynamic_discovery.md`.
- [x] **Audit Object**: Documented the `passes` object structure and interpretation in `institutional_etf_scanners.md`.

### Phase 5: Final Audit & Cleanup
**Goal**: Ensure 1:1 parity between Specification and Configuration.
- [x] **Core Audit**: Verified 9/9 scanners match specs (`filters`, `columns`, `logic`).
- [x] **Pruning**: Removed orphan config `etf_alternative_alpha.yaml`.
- [x] **Completion**: Project "Institutional ETF Scanner Expansion" is fully delivered.

### Phase 6: Standardization (Layer B Upgrade)
**Goal**: Upgrade Layer B scanners ($10M floor) to the "Liquid Winners" pattern to prevent API starvation and enrich metadata.
- [x] **Commodity Upgrade**: Update `etf_commodity_supercycle.yaml`.
    - Apply `sort_by: Value.Traded` / `final_sort_by: Perf.3M`.
    - Add Context Columns (`Perf.Y`, `Volatility.M`).
- [x] **Equity Upgrade**: Update `etf_equity_momentum.yaml`.
    - Apply `sort_by: Value.Traded` / `final_sort_by: Perf.1M`.
    - Add Context Columns.
- [x] **Bond Upgrade**: Update `etf_bond_yield_trend.yaml`.
    - Apply `sort_by: Value.Traded` / `final_sort_by: ADX`.
    - Add Context Columns.
- [x] **Validation**: Verify output for Layer B scanners.

### Phase 7: Final Production Verification
**Goal**: Run the complete suite of 5 Dynamic Scanners to produce a verified "Alpha Basket" for user inspection.
- [x] **Unified Execution**: Run all Layer B & C scanners in a single batch.
- [x] **Consolidation Tool**: Create `scripts/inspect_etf_candidates.py` to aggregate JSON exports into a ranked Markdown report.
- [x] **Alpha Report**: Generate a final table of "Top Picks" (High Perf/Yield) and "Warnings" (Low AUM).

### Phase 8: Tournament Audit & Optimization
**Goal**: Analyze backtest results to select the optimal engine configuration.
- [x] **Deep Dive**: Analyzed `comparison.md` from Run `20260107-180738`.
- [x] **Findings**:
    - **Adaptive Engine** is superior (Sharpe 2.65 vs 2.54 static).
    - **Dynamic Switching** correctly toggles between `hrp` (Turbulent) and `max_sharpe` (Normal).
    - **Simulator Validity**: `cvxportfolio` confirmed as reliable.
- [x] **Action**: (Reverted) Keep `engine: "skfolio"` for now to stabilize baselines.
- [x] **Reporting**: Generated `benchmark_audit_summary.md`.

### Phase 9: Selection Logic Audit
**Goal**: Verify "Natural Selection" decisions for top portfolios.
- [x] **Deep Dive**: Created `audit_deep_dive.md` analyzing Cluster Battles.
- [x] **Verification**: Confirmed "One Bet Per Factor" logic correctly prioritized `SLV` over `AGQ` and `GDX` over `NUGT`.
- [x] **Liquid Winners**: Validated that `RKLX`, `SHLD`, `SDIV` won their clusters.
- [x] **Spec Finalization**: Promoted `universe_selection_v3_fp.md` to `universe_selection_v3.md` (Final Spec) incorporating Audit findings.

### Phase 10: Documentation Synchronization
**Goal**: Ensure high-level architecture docs reflect the new capabilities.
- [x] **Workflow Spec**: Updated `quantitative_workflow_v1.md` with "Liquid Winners" logic.
- [x] **Roadmap**: Updated `production_pipeline_status...md` marking ETF Expansion as COMPLETED.
- [x] **Lessons Learned**: Created `lessons_learned_etf_expansion.md` synthesizing findings.

### Phase 11: Deep Audit & Closure
**Goal**: Final forensic audit and project closure.
- [x] **Audit Report**: Created `docs/audit/audit_run_20260107_180738.md`.
- [x] **Verification**: Validated all system components (Scanner, Selection, Engine, Simulator).
- [x] **Closure**: Project formally closed.

### Phase 12: Spec Refinement
**Goal**: Synchronize technical specifications with empirical lessons learned.
- [x] **Optimization Spec**: Updated `optimization_engine_v2.md` with Adaptive regime mappings and Barbell constraints.
- [x] **Benchmark Spec**: Updated `multi_engine_optimization_benchmarks.md` with Riskfolio caveats and latest tournament data.

### Phase 16: Final Spec Synchronization
**Goal**: Capture deep audit findings in long-term documentation.
- [x] **Selection**: Documented `SLV` vs `AGQ` case study in `universe_selection_v3.md`.
- [x] **Riskfolio**: Confirmed persistent divergence in `multi_engine_optimization_benchmarks.md`.
- [x] **Extreme Momentum**: Documented `ASTX` case in `lessons_learned_etf_expansion.md`.

### Phase 17: HRP & Risk Profile Audit
**Goal**: Ensure spec parity for HRP Linkage and Barbell logic.
- [x] **HRP Linkage**: Updated `hrp_implementation_parity.md` to reflect `Custom` engine's upgrade to **Ward Linkage** (matching Code).
- [x] **Barbell**: Verified `cluster_adapter.py` forces Aggressors before Core HRP.

### Phase 18: Multi-Sleeve Meta-Portfolio Design
**Goal**: Design the architecture for cross-universe (Instruments + ETFs) meta-portfolios.
- [x] **Requirement**: Defined the 2-layer optimization model (Intra-sleeve -> Inter-sleeve).
- [x] **Specification**: Created `multi_sleeve_meta_portfolio_v1.md`.
- [ ] **Implementation**: Build aggregation scripts and meta-allocation logic.

### Phase 19: Meta-Portfolio Implementation (Sleeve Aggregation)
**Goal**: Implement the scripts for building meta-return matrices.
- [x] **Script**: `scripts/build_meta_returns.py` to join return series.
- [x] **Validation**: Verified TradFi alignment and intersection logic.
- [x] **Meta-Manifest**: Created `data/lakehouse/meta_manifest.json` to track sleeve runs.

### Phase 20: Meta-Portfolio Optimization & Flattening
**Goal**: Execute top-level HRP across sleeves and generate final asset weights.
- [x] **Script**: `scripts/optimize_meta_portfolio.py` for sleeve-level HRP.
- [x] **Script**: `scripts/flatten_meta_weights.py` for asset-level weight reconciliation.
- [x] **Flow Integration**: Added `make flow-meta-production` to the Makefile.
- [x] **Validation**: Successfully generated `portfolio_optimized_meta.json` (10 assets from 2 sleeves).
- [x] **Reporting**: Created `scripts/generate_meta_report.py` for meta-layer visibility.

### Phase 21: Meta-Portfolio Spec Finalization
**Goal**: Formalize the multi-sleeve architecture in the system documentation.
- [x] **Workflow Spec**: Updated `quantitative_workflow_v1.md` with Stage 5: Meta-Portfolio.
- [x] **Manifest Spec**: Updated `workflow_manifests.md` with `sleeves` schema.

### Phase 22: Production Hardening & Audit
**Goal**: Verify multi-sleeve integrity in real-world conditions.
- [x] **Audit (Integrity)**: Verified no weekend padding and correct intersection logic in Meta-Returns.
- [x] **Audit (Traceability)**: Reconciled sleeve-level weights to asset-level weights.
- [x] **Audit (Ledger)**: Confirmed meta-optimization decisions are recorded in `audit.jsonl`.
- [x] **Spec Synchronization**: Updated `multi_sleeve_meta_portfolio_v1.md` and `artifact_hierarchy.md` with audit findings.

## Conclusion
The **Institutional ETF Scanner Expansion** project and the **Multi-Sleeve Meta-Portfolio** infrastructure are complete.
The system now supports cross-universe risk management with high-fidelity diversification alpha, backed by a transparent audit ledger.
The pipeline is production-ready.

