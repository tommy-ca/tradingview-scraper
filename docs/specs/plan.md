# Plan: Benchmark Baseline & Selection Specs

## Objectives
- **Baseline stability**: Ensure `market`, `benchmark`, and `raw_pool_ew` are deterministic and usable as backtest baselines for risk profiles.
- **Selection specs alignment**: Keep selection-mode behavior isolated from baselines when the universe source is unchanged.
- **Workflow guardrails**: Enforce metadata coverage, baseline invariance checks, and report integrity as first-class pipeline steps.

## Context: Recently Completed
- [x] **Grand Tournament Consolidation**: Merged research and production tournament orchestrators into a unified `grand_tournament.py` suite.
- [x] **Selection Alpha Parity Audit**: Certified `v3.2` (+2.97%) as the superior precision engine over `v2.1` (+1.75%) under fixed institutional baseline.
- [x] **Live Adapter Phase 1-3**: Established real-time connectivity (Binance), implemented strict rebalance order submission, and verified position state persistence to lakehouse.
- [x] **Rebalance Logic Alignment**: Unified backtest and live rebalance logic with strict lot-size, step-size, and minimum notional enforcement.
- [x] **Full Institutional ETF Audit**: Certified Q1 2026 winners (**JNJ, LQD, GOOG**) and verified high-fragility outlier insulation (**PLTR, CPER**).
- [x] **Baseline Taxonomy Decommissioning**: Standardized on `market`, `benchmark`, and `raw_pool_ew`.
- [x] **Selection Metadata Enrichment**: Automated institutional metadata detection and gap-filling.
- [x] **CVXPortfolio Simulator Fidelity**: Strictly aligned weight indices and cash modeling to prevent solver drift.

## Current Focus
- **Dynamic ETF Expansion**: Implementing momentum and trend-based scanners to expand the institutional discovery pool. (Active)

## Next Steps Tracker (Rescheduled Queue)

### Now (Jan 2026): Execution & Production Scaling
- [x] **Dynamic ETF discovery**: Implemented `etf_equity_momentum`, `etf_bond_yield_trend`, and `etf_commodity_supercycle` scanners. (Completed)
- [x] **Screener Research Guide**: Created `docs/guides/screener_research.md` documenting the reverse-engineering process for TV API fields.
- [ ] **Live Adapter (Phase 4)**: Final production "Hard-Sleeve" deployment (Binance/Live). (Active)


### Recently Completed: Pipeline Correctness & Backtest Parity
- [x] **Nautilus Execution Engine (Research Phase)**: 
    - [x] **Parity Smoke Test**: Automate validate_parity.py with failure gates.
    - [x] **Parity Scale-Up**: Validated with 300d lookback and multi-asset classes.
    - [x] **Metadata Service**: Fetch Lot Sizes/Min Notionals via CCXT for all winners.
    - [x] **Shadow Loop (L5.5)**: Automated Drift + Paper Fill Simulation.
- [x] **E2E Pipeline Audit (ETF Core)**: 
    - [x] **Profile Definition**: Created `institutional_etf` profile.
    - [x] **Robustness Fixes**: Resolved NaN alpha scores and missing metadata.
    - [x] **Selection Reporting**: Fixed abnormal Selection Alpha logic (+1.86% verified).
    - [x] **Dual Selection Audit**: Integrated `v2.1` (Stability Anchor) alongside `v3.2` (Champion).
    - [x] **Risk-Parity Correctness**: Fixed HRP implementation (Ward linkage + Recursive Bisection).
    - [x] **Tournament Correctness**: Verified HPO and cluster-aware allocation stability.
- [x] **Workflow Optimization**:
    - [x] **Manifest-Driven Configuration**: Standard production runs now strictly follow manifest defaults.
    - [x] **Fast Production Flow**: Standardized `flow-production` to use fast vectorized simulators.
    - [x] **Pre-Live Verification**: Introduced `flow-prelive` for full validation via Nautilus.
- [x] **Grand Tournament Orchestration**:
    - [x] **Grand Tournament Script**: Created `scripts/grand_tournament.py` for multi-pass production validation.
    - [x] **Execution Completed**: Validated `v3.2` vs `v2.1` across the full institutional ETF pipeline.
- [x] **Final Institutional ETF Validation (Audit Phase)**: Completed. Q1 2026 ETF strategy certified with **JNJ, LQD, and GOOG** as top winners.

### Deferred Scopes
- [ ] **Phase 4 (Native MT5 Adapter)**: Completed but execution path deferred in favor of Nautilus.
- [ ] **Phase 5 (MT5 Deployment)**: Deployment of native MT5 bridge is on hold.

### Next (Feb 2026): Universe & Strategy Expansion
- [ ] **Scanner expansion (breadth-first)**: Expand discovery universes by asset type (FX Majors, Crypto Top-50, Commodity Proxies).
- [ ] **Promotion to live trading**: Define the gated path from validated portfolios → orders → paper trading → live execution.

## Risk Profile Matrix
| Profile | Category | Universe | Weighting / Optimization | Notes |
| --- | --- | --- | --- | --- |
| `market` | Baseline | Benchmark symbols | Equal-weight long-only; no optimizer | Institutional hurdle. |
| `benchmark` | Baseline | Natural-selected | Asset-level equal weight over winners | Research baseline for alpha tracking. |
| `raw_pool_ew` | Baseline | Canonical or selected | Asset-level equal weight across raw pool | Diagnostic signal for universe-level fragility. |
| `equal_weight` | Risk profile | Natural-selected | Hierarchical equal weight (HE + HERC 2.0) | Neutral, low-friction comparison. |
| `min_variance` | Risk profile | Natural-selected | Cluster-level minimum variance (solver) | Defensive target; beta-gated (< 0.5). |
| `hrp` | Risk profile | Natural-selected | Hierarchical risk parity (HRP) | Structural robustness baseline. |
| `max_sharpe` | Risk profile | Natural-selected | Cluster-level max Sharpe mean-variance | Growth regime focus; cluster-capped. |
| `barbell` | Strategy | Natural-selected | Core HRP sleeve + aggressor sleeve | Convexity-seeking tail-risk capture. |

## Status Sync (Jan 2026)

### High-Integrity Validation (Resolved & Scale-Ready)
- **Run 20260106-020000 (Beta & Antifragility)**: Confirmed `min_variance` beta stability (0.35) and benchmark antifragility (+0.8). Validated relaxation of `min_af_dist` to -0.20.
- **Run 20260106-010000 (Friction Alignment)**: Verified near-zero friction decay for baselines after isolating non-cash trades.
- **Run 20260106-000000 (Simulator Parity)**: Confirmed 0.4% equity parity gap and 4-6% commodity divergence (handled by sleeve-aware relaxation).
- **Run 20260105-214909 (Commodity Gating)**: Implemented and validated sleeve-aware thresholds (Tail 3.0x / Parity 5.0%) for commodity proxy ETFs.

## Issue Backlog (Strict Scoreboard)
**Resolved & Archived**: The Q1 2026 strict-scoreboard issue backlog has been completed and moved to the historical log.
- See `docs/specs/audit_q1_2026_scoreboard_stabilization.md`.
