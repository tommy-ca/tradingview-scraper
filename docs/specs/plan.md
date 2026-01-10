# Platform Specification, Requirements & Development Plan

## 1. Executive Summary
This document codifies the institutional requirements and design specifications for the TradingView Scraper quantitative platform, incorporating recent learnings from crypto production and institutional ETF strategy validation (Q1 2026).

## 2. Requirements & Standards

### 2.1 Data Integrity & Health (The Forensic Pillar)
- **Secular History**: Production runs require 500 days of history for assets.
- **Strict Health Policy**: 100% gap-free alignment required for implementation.
- **Institutional Gaps**: 1-session gaps are ignored (market-day normalization).
- **Crypto Precision**: 15-day step size alignment (Median $T=19d$) to minimize drawdown.
- **Normalization**: +4h shift for market-day alignment (20:00-23:59 UTC).

### 2.2 Selection Architecture (The Alpha Core)
- **Primary Model (v3.2)**: Log-Multiplicative Probability Scoring (Log-MPS).
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

### 3.2 Production Sequence (15-Step)
1. Cleanup -> 2. Discovery -> 3. Aggregation -> 4. 60d Prep -> 5. Selection -> 6. Enrichment -> 7. 500d Prep -> 8. Health Audit -> 9. Self-Healing -> 10. Persistence Research -> 11. Factor Analysis -> 12. Regime Detection -> 13. Optimization -> 14. Validation -> 15. Reporting.

## 4. Development Plan (Current Sprint)

### Phase 1: Requirement Updates (COMPLETED)
- [x] Update `docs/specs/plan.md` (this file).
- [x] Align `docs/production_workflow.md` with 15-step sequence.

### Phase 2: Pipeline Optimization (IN PROGRESS)
- [x] Update `scripts/optimize_clustered_v2.py` for regime-aware allocation.
- [x] Update `scripts/research_regime_v3.py` for advanced tail-risk metrics.
- [x] Integrate Persistence Analysis into the optimization decision loop.

### Phase 64: Selection Audit & Universe Evolution (COMPLETED)
- [x] **Audit**: Compared Run `20260109-164834` (Current) with `20260109-152110` (Previous).
- [x] **Discovery**: Current run discovered 62 assets (+11 shift) due to targeted data recovery.
- [x] **Veto Rotation**: Log-MPS v3.2 successfully rotated out of "Meme noise" and into "Blue Chip anchors" (BTC, SOL, XRP).
- [x] **Rationale**: Portfolio difference is attributed to **Data Freshness** enabling risk engines to see improved momentum.

### Phase 65: Comprehensive Pipeline Validation (COMPLETED)
- [x] **Selection TDD**: Created `tests/test_selection_evolution.py`; verified "Blue Chip" prioritization.
- [x] **Workflow TDD**: Verified end-to-end audit ledger continuity and data freshness.
- [x] **Final Flow**: Executed `make flow-crypto` with `TV_STRICT_HEALTH=1` (Run ID: `20260109-175648`).

### Phase 66: Risk Profile Deep Audit & Fidelity Analysis (COMPLETED)
- [x] **Ledger Audit**: Analyzed `audit.jsonl` across 7 windows; confirmed Regime-Specific winners.
- [x] **Engine Divergence**: Identified critical HRP performance gap (CVX +1.98 vs PyPort -1.32).
- [x] **Fidelity Standard**: Codified Risk Profile Diversification Floors (CR-120).
- [x] **Reporting**: Generated `docs/reports/2026_q1_crypto_signoff.md`.

### Phase 67: Final Configuration & Freeze (COMPLETED)
- [x] **Root Cause Analysis**: Identified Single vs. Ward Linkage as potential cause of HRP divergence.
- [x] **Policy Update**: Enforced "Open Benchmarking" standard (keep all engines in tournament) to gather statistical significance.
- [x] **Cleanup**: Archive all audit logs and analysis scripts.

### Phase 69: Engine Flexibility (COMPLETED)
- [x] **Experiment**: Confirmed PyPortfolioOpt supports linkage configuration.
- [x] **Grand Tournament**: Executed 4-way Linkage Tournament (Single/Ward/Complete/Average).
- [x] **Findings**: Custom HRP (Ward) wins with 1.307 Sharpe. PyPort (Single) follows with 1.264. PyPort (Ward) lags at 1.260.
- [x] **Policy**: Recommended `Custom` engine for HRP while keeping tournament open for data collection.

### Phase 71: Deep Window Audit (COMPLETED)
- [x] **Audit Script**: Created `scripts/research/audit_window_matrix.py` for granular Engine x Profile x Window analysis.
- [x] **Findings**:
    -   Confirmed engine divergence in Window 3: Skfolio (+0.20) > Custom (-0.24) > PyPort (-1.10).
    -   Verified that "Window 6" characteristics shifted due to data updates, emphasizing the need for dynamic engine selection.
- [x] **Policy**: Reinforced "Open Benchmarking" to capture these regime-specific engine advantages.

### Phase 73: Selection Funnel Audit (COMPLETED)
- [x] **Audit Script**: Created `scripts/research/audit_selection_funnel.py`.
- [x] **Funnel Analysis**: Confirmed 20.6% retention rate (102 -> 21).
- [x] **Veto Logic**: Validated "High Friction" (22) as the primary filter for speculative noise.
- [x] **Integrity**: Verified selection matches data health report.

### Phase 74: Documentation Synchronization (COMPLETED)
- [x] **Requirements**: Added CR-130 (Retention) and CR-131 (Friction Filter).
- [x] **Design**: Documented Funnel Dynamics and Veto Architecture.
- [x] **State**: System documentation is now fully aligned with Q1 2026 audit findings.

### Phase 75: Final System Freeze (COMPLETED)
- [x] **State**: System worktree cleaned and atomic commits applied.
- [x] **Verification**: All TDD tests passed (7/7).
- [x] **Documentation**: All artifacts synchronized.

### Phase 76: Deployment & Monitoring (COMPLETED)
- [x] **Release**: Push `develop` to `main` tag `v1.0.0-crypto`.
- [x] **Cron**: Configure daily `make flow-production` schedule (recommended: 00:05 UTC).
- [x] **Maintenance**: Enable `make clean-archive` in monthly housekeeping (e.g., 1st of month).
- [x] **Monitoring**: Set up alerts for `strict_health` failures in the production log.

### Phase 77: Scanner Matrix Expansion (COMPLETED)
- [x] **Specs**: Updated Requirements (CR-150) and Design (Matrix).
- [x] **Config**: Created symmetric Spot/Perp Long/Short configuration matrix.
- [x] **Refactor**: Renamed all scanners to `binance_[asset]_[direction]_[strategy].yaml` for consistency.

### Phase 78: Robust Selection Upgrade (COMPLETED)
- [x] **Logic**: Implemented **Top-3 per direction** intra-cluster selection.
- [x] **Robustness**: Added **NaN-safe scoring** to Log-MPS 3.2 engine.
- [x] **Hygiene**: Relaxed `min_days_floor` to 30 days to capture new alpha (PIPPIN, MYX).
- [x] **Verification**: Confirmed funnel retention (18%) and veto integrity (Operation Darwin).
- [x] **Significance**: Implemented linear Significance Multiplier for Antifragility scores.

### Phase 79: Final Deployment & Audit (COMPLETED)
- [x] **Verification**: Confirmed `PIPPIN` (497M vol) inclusion in Top 100 universe.
- [x] **Symmetry**: Verified 2L/4S selection from new symmetric matrix.
- [x] **Grounding**: Confirmed `MYX` rejection ($N < 180$) and `PIPPIN` AF adjustment (0.95x).
- [x] **Infra**: Patched Makefile and Orchestrator for robust parameter promotion.

### Phase 80: Base Universe Hardening & Normalization (COMPLETED)
- [x] **Specs**: Refined CR-151 to enforce three-stage "Prefetch -> Normalization -> Liquidity" filter.
- [x] **Audit**: Identified non-normalized fiat volume (IDR, TRY) as a primary discovery bottleneck.
- [x] **Config**: Updated `binance_perp_top100.yaml` and `binance_spot_top100.yaml` with explicit USD-stable match filters and 5000-deep prefilters.
- [x] **Validation**: Reached the Top 50 target for Perps and 9 institutional anchors for Spot.
- [x] **Infra**: Patched Makefile to ensure correct profile-based rebalancing and veto parameters.

### Phase 81: Robust Production Validation (COMPLETED)
- [x] **Workflow**: Executed full `make scan-run` -> `data-prep` -> `port-select` sequence.
- [x] **Symmetry**: Verified 15L/8S selection from finalized symmetric matrix build on hardened base.
- [x] **Audit**: Confirmed institutional retention standard (20.7%) and veto integrity.
- [x] **State**: System validated for high-fidelity Q1 2026 production.

### Phase 82: System Sign-Off (COMPLETED)
- [x] **Docs**: Updated Design, Requirements, and Plan for v3.1 Standards.
- [x] **State**: System worktree cleaned and atomic commits applied.
- [x] **Freeze**: Release tagged `v1.1.0-discovery-hardened`.


