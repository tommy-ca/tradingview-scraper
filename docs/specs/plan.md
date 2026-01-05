# Plan: Benchmark Baseline & Selection Specs

## Objectives
- **Baseline stability**: Ensure `market`, `benchmark`, and `raw_pool_ew` are deterministic and usable as backtest baselines for risk profiles.
- **Selection specs alignment**: Keep selection-mode behavior isolated from baselines when the universe source is unchanged.
- **Workflow guardrails**: Enforce metadata coverage, baseline invariance checks, and report integrity as first-class pipeline steps.

## Context: Recently Completed
- [x] **Baseline Taxonomy Decommissioning**: Standardized on `market`, `benchmark`, and `raw_pool_ew`.
- [x] **Selection Metadata Enrichment**: Automated institutional metadata detection and gap-filling.
- [x] **CVXPortfolio Simulator Fidelity**: Strictly aligned weight indices and cash modeling to prevent solver drift.
- [x] **Institutional Safety (Scoreboard)**: Implemented `tournament_scoreboard.py` with temporal fragility, friction alignment, and quantified antifragility gates.
- [x] **Sleeve-Aware Gating**: Implemented detection and relaxation for commodity proxy ETFs (Tail 3.0x / Parity 5.0%).
- [x] **Friction Alignment Fix**: Resolved cash-leg cost double-counting in simple simulators.

## Current Focus
- **Full Production Sweep (Q1 2026)**: Execute the first official multi-dimensional tournament with sleeve-aware gating and high-fidelity friction alignment.
- **Institutional Reporting**: Finalize the unified tearsheet and alpha audit for the Q1 candidate list.
- **Guardrail sentinel readiness**: Keep canonical and selected guardrail pairs re-run quarterly.

## Next Steps Tracker (Rescheduled Queue)

### Now (Jan 2026): Production Operations
- [ ] **Q1 2026 Institutional Scoreboard**: Launch full Grand 4D tournament (`LOOKBACK=500`, full dimension grid).
- [ ] **Downstream consumer migration**: Update forensics/reporting to use explicit `decision_*` regime keys (avoid implicit `windows[].regime`).
- [x] **Stabilization Audit**: Completed the Q1 2026 strict-scoreboard issue backlog (ISS-001 to ISS-008). See `docs/specs/audit_q1_2026_scoreboard_stabilization.md` for resolution history.

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
