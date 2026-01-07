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

### Phase 13: Riskfolio Remediation
**Goal**: Address the -0.95 correlation divergence in Riskfolio HRP.
- [x] **Fix Applied**: Updated `engines.py` to force `linkage="ward"` (matching Custom/Skfolio) and added experimental warning.
- [x] **Validation**: Verified API signature supports `linkage` parameter.

### Phase 14: Validation & Rerun
**Goal**: Execute the full production pipeline to validate the scanner expansion and Riskfolio remediation.
- [x] **Execution**: Ran `make flow-production PROFILE=institutional_etf` (Run ID: `20260107-193807`).
- [x] **Scanner Verification**: Confirmed discovery of new assets (`RKLX`, `SDIV`) and expanded raw pool (>100 candidates).
- [x] **Riskfolio Audit**: Confirmed warning log presence in `12_validation.log`.

### Phase 15: Final Deep Audit
**Goal**: Forensic analysis of the final validation run to confirm all subsystems are synchronized.
- [x] **Audit Report**: Created `docs/audit/audit_run_20260107_193807.md`.
- [x] **Findings**: Validated `Liquid Winners` logic (ASTX, KOLD), `Cluster Battles` (SLV vs AGQ), and `Barbell` risk scaling.

## Conclusion
The **Institutional ETF Scanner Expansion** project is complete.
The system now features 9 verified scanners, a robust "Liquid Winners" discovery architecture, and a validated multi-engine backtesting capability.
