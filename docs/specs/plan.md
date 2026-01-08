# Plan: Institutional ETF Scanner Audit & Expansion

## Objective
Audit and expand the institutional ETF scanners to capture high-alpha niche/thematic opportunities currently filtered out by strict liquidity or category constraints. We aim to identify "Alpha Pockets" in thematic equities, high-yield bonds, and alternative strategies.

## Crypto Scanner Standardization & Uplift (2026-01-08)
- [x] **Base Universes**: Created `binance_spot_top50.yaml`, `binance_perp_top50.yaml`, and multi-exchange `global_perp_top50.yaml`.
- [x] **Discovery Uplift**: Increased `prefilter_limit` to 200 and relaxed scanner gates (ADX 10-15, Rec >= 0) to ensure a larger candidate pool.
- [x] **Hygiene**: Strict stablecoin quote whitelist implemented for Binance Spot (`USDT`, `USDC`, `USD`, `FDUSD`, `BUSD`).
- [x] **Natural Selection (Path A)**: Relaxed `entropy_max_threshold` to **0.995** and narrowed Hurst random-walk zone (0.48-0.52) in Log-MPS v3.2.
- [x] **Natural Selection (Path B)**: Verified `selection_mode: v2.1` availability as a rank-sum fallback.
- [x] **Validation**: Run `20260108-130948` successfully identified 17 candidates and selected 5 high-conviction winners (XAUT, BCH, RIVER, PIEVERSE, PAXG).
- [x] **Experiment A (Volume Funnel)**: Confirmed that `Stage 1: Value.Traded` surfaces high-momentum survivors (BCH, RIVER, PIEVERSE) effectively; recommended for "Dynamic Discovery" bases.
- [x] **Experiment B (Category Discovery)**: Probed for sector-specific metadata; confirmed TV crypto screener fields are currently limited to `type`/`subtype`, making sector-based scanning dependent on external metadata enrichment.
- [x] **Experiment C (Acceleration)**: Implemented `binance_acceleration_trend` targeting assets with strong intraday moves (>2% 24h change); successfully surfaced high-momentum candidates like `UBUSDT.P` (14% change).

## High Entropy in Crypto
Crypto markets exhibit high permutation entropy (typically 0.98–0.99) due to microstructure noise, fragmented liquidity, and rapid sentiment pricing. The system now adopts a 0.995 threshold for crypto to permit high-alpha momentum while still filtering absolute noise.

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

### Phase 23: Instruments Sleeve Isolation
**Goal**: Decouple Crypto from the primary TradFi production sleeve to prepare for multi-sleeve meta-portfolio scaling.
- [x] **Configuration**: Removed `crypto` markets and `binance_trend` scanner from the `production` profile.
- [x] **Hygiene**: Filtered out 4 stale symbols (`AMD`, `CSCO`, `ISRG`, `LRCX`) to ensure high-integrity production returns.
- [x] **Execution**: Rerun the production pipeline for the sanitized TradFi sleeve (Run `20260107-203840`).
- [x] **Verification**: Confirmed zero crypto assets in the TradFi sleeve returns and candidates.

### Phase 24: Institutional Parity Alignment
**Goal**: Harmonize sub-sleeve execution parameters to ensure statistical validity in Meta-Portfolio allocation.
- [x] **Alignment**: Updated `institutional_etf` and `production` manifests with 500d lookback and Selection v3.2 parity.
- [x] **Execution**: Rerun both sleeves with aligned temporal and risk parameters.
- [x] **Integration**: Execute meta-portfolio HRP across Instruments and ETF sleeves.

### Phase 25: Total Parity Alignment & Resolver Hardening
**Goal**: Eliminate "Resolution Drift" by locking selection modes in the features block and standardizing conviction parameters.
- [x] **Hardening**: Moved `selection_mode` to `features` block in `manifest.json`.
- [x] **Standardization**: Applied `threshold: 0.4`, `top_n: 10`, and `min_momentum: -0.1` to both Instrument and ETF sleeves.
- [x] **Validation**: Verified identical `resolved_manifest.json` parameter blocks across sleeves.

### Phase 26: Sleeve Hardening & Integrity Remediation
**Goal**: Fix essential pipeline bugs discovered during the parity audit and focus on single-sleeve performance.
- [x] **Fix (Resolver)**: Ensured `selection_mode` in `features` block correctly overrides global defaults.
- [x] **Fix (Archival)**: Ensured `portfolio_optimized_v2.json` is archived in the run `data/metadata/` directory.
- [x] **Uplift (Risk)**: Implemented a "Diversity Floor" (min 5 assets) in the custom risk engine.
- [x] **Optimization (Sleeve)**: Executed `production` (Instruments) sleeve with optimized conviction parameters (`threshold: 0.35`).

### Phase 27: Fractal Risk Architecture & Deep Audit
**Goal**: Transition to a recursive risk multiverse where sleeves are treated as profile-matrices and meta-allocation is philosophy-consistent.
- [x] **Spec Update**: Formalized Fractal Risk Architecture and Outlier Detection standards.
- [x] **Recursive Flow**: Updated `build_meta_returns.py`, `optimize_meta_portfolio.py`, and `flatten_meta_weights.py` for profile-matrix support.
- [x] **Deep Audit**: Executed `audit_meta_outliers.py` to verify top winner transitions, data integrity, and sleeve orthogonality.
- [x] **Outlier Mitigation**: Implemented "Concentration Entropy" metrics in the audit ledger and risk optimization stage.

### Phase 28: Stale Asset Remediation
**Goal**: Close the 5-day data lag for `JNJ` and `LLY` to ensure high-fidelity volatility estimation.
- [x] **Targeted Refresh**: Executed high-intensity targeted refresh for `JNJ` and `LLY`.
- [x] **Verification**: Verified Parquet files reach `2026-01-07`.

### Phase 29: Crypto Sleeve Integration & Meta-Tournament
**Goal**: Integrate the dedicated Crypto sleeve into the Fractal Meta-Portfolio and evaluate the Grand Champion.
- [x] **Crypto Profile**: Created `crypto_production` profile in `manifest.json`.
- [x] **Parallel Execution**: Completed `instruments_hardened_v2`, `etf_hardened_v2`, and `crypto_hardened_v1`.
- [x] **Fractal Build**: Executed the Meta-Matrix flow with 3 orthogonal sleeves.
- [x] **Audit**: Confirmed high efficiency in TradFi/Crypto (High Entropy vetoes) leading to a high-conviction "Value/Gold" meta-portfolio.

### Phase 30: Short-Cycle Discovery Optimization (2026-01-08)
**Goal**: Transition crypto scanners to a "Short-Cycle Momentum" framework to improve capture rates in high-velocity markets.
- [x] **Philosophy**: Prioritize recency (Daily/Weekly/Monthly) over secular stability (3M/6M) to accommodate compressed market cycles.
- [x] **Standardization**: Remove `Perf.3M` gates from all active crypto scanners.
- [x] **Benchmarks**: Implement dual-benchmark tracking using `BINANCE:BTCUSDT` and `AMEX:SPY`.
- [x] **Validation**: Run `20260108-150623` successfully identified 78 raw hits → 44 unique candidates → 5 final winners. Confirmed that removing 3M anchors surfaced high-velocity candidates like `UBUSDT.P` and `BROCCOLI714USDT.P` earlier in their respective trend cycles.
- [x] **Audit**: Confirmed Log-MPS v3.2 correctly handles increased crypto entropy (0.995 threshold) while filtering random-walk Hurst values (0.48-0.52).

### Phase 31: Forensic Selection & Risk Audit (2026-01-08)
**Goal**: Deep analyze the selection funnel and risk profile metrics for crypto portfolios.
- [x] **Veto Traceability**: Audited Run `20260108-150623`. Identified Entropy (0.995) and Hurst (0.50) as primary arbiters of crypto signal vs noise.
- [x] **Risk Profile Analysis**: Verified that the **Barbell Profile** successfully de-risks the crypto sleeve (Vol 38%) by anchoring in Gold-pegged assets (`PAXG`, `XAUT`) while permitting 10% weight in high-momentum aggressors (`RIVER`, `PIEVERSE`).
- [x] **HCA Audit**: Analyzed Ward Linkage clustering. Confirmed the system correctly identified orthogonal risk units and used "Gold Redundancy" to meet the Diversity Floor.
- [x] **Validation**: Confirming that while "Short-Cycle" relaxation increased discovery hits (78), the risk engine (Log-MPS v3.2) remains the final arbiter of statistical integrity.

### Phase 33: Multi-Candidate Scaling & Engine Trust Validation (2026-01-08)
**Goal**: Expand the candidate universe by delegating alpha-filtering to portfolio risk engines.
- [x] **Quantification**: Benchmarked selection tiers (Strict vs Broad vs Raw) over a 342-day lookback.
- [x] **Findings**: **Broad Selection (Top 25)** outperformed Strict Selection (Top 5) in risk-adjusted terms (Sharpe 1.76 vs 1.47; Max DD -23% vs -35%).
- [x] **Philosophy Shift**: Transitioned Natural Selection from an "Alpha Gate" to a **"Noise Floor"**. Selection now removes purely erratic noise (Entropy > 0.999), while the **Barbell/HRP** engines handle allocation across high-signal candidates.
- [x] **Scaling**: Increased `top_n` to 25 for crypto production sleeves.

### Phase 34: Gold Peg Fidelity & Anchor Hardening (2026-01-08)
**Goal**: Audit the tracking quality of "Safe Haven" crypto anchors to prevent "Noise Alpha" contamination.
- [x] **Audit**: Compared `BINANCE:PAXGUSDT.P` and `OKX:XAUTUSDT.P` against direct Gold (`XAUUSDT.P`).
- [x] **Findings**: `OKX:XAUT` is a high-fidelity tracker (0.985 corr), whereas `BINANCE:PAXG` has detached (0.44 corr), providing misleadingly high returns (67% vs 39% for gold).
- [x] **Action**: Blacklisted `BINANCE:PAXGUSDT.P` for institutional use-cases. Standardized the Barbell "Core" anchor to prioritize `XAUT` or direct `XAU` perps.

### Phase 35: Predictability & Cohesion Audit (2026-01-08)
**Goal**: Integrate Autocorrelation and Lead-Lag analysis to detect self-predictability and cluster leaders.
- [x] **Self-Predictability**: Implemented Ljung-Box and ACF utilities in `predictability.py`.
- [ ] **Cohesion**: Analyze intra-cluster cross-correlation to verify factor homogeneity.
- [ ] **Lead-Lag**: Identify "Factor Leaders" within clusters to optimize entry/exit timing.

## Conclusion

The **Institutional Multi-Sleeve Meta-Portfolio** infrastructure is now fully operational.
The system successfully manages 3 orthogonal capital sleeves (Instruments, ETFs, Crypto) using a Fractal Risk Architecture that preserves risk philosophy from asset to meta-allocation.
The platform is in a high-integrity, production-ready state.
