# Plan: Market Benchmark & Ledger Audit Analysis

**Status**: Planned
**Date**: 2026-01-01
**Goal**: Validate simulator fidelity using the "Market" baseline and audit the decision ledger for transparency and reproducibility.

## 1. Market Benchmark Analysis
The "Market" engine (specifically `MARKET_EW` or `MARKET_HOLD`) serves as the control group. Deviations in its performance across simulators reveal pure simulation artifacts (slippage, cost, rebalancing frequency) without the noise of optimizer variance.

- **Action**: Extract `MIN_VARIANCE` (often used as proxy for EW/Market in reports if `market` engine is used) or `EQUAL_WEIGHT` profile results for the `market` engine from the latest tournament.
- **Comparison**:
    - `market` | `custom`: Idealized frictionless return.
    - `market` | `cvxportfolio`: Friction-aware return.
    - `market` | `vectorbt`: Vectorized return (Fresh Buy-In).
- **Deliverable**: `docs/research/market_simulator_benchmark.md` table showing variances.

## 2. Outlier Identification
Identify engines or simulators that deviate > 2 standard deviations from the group mean for the "Market" profile.
- **Focus**: `vectorbt` turnover (expected >100%), `cvxportfolio` costs.

## 3. Audit Ledger Review
The system uses an audit ledger (likely `data/audit.jsonl` or similar) to record rebalancing events.
- **Action**: Inspect the ledger for the latest run `20260101-000918`.
- **Verify**:
    - Are `target_weights` recorded?
    - Are `rebalance_events` logged?
    - Can we link a specific row in `audit.jsonl` to a specific backtest window?

## 4. Reconstruction Test
- **Concept**: Select one window from the ledger.
- **Check**: Do we have `prices` (snapshot or reference), `weights`, and `parameters` to reproduce the simulator result exactly?

## 5. Execution Steps
1.  Parse `artifacts/summaries/runs/20260101-000918/tournament_results.json` to extract Market data.
2.  Read `data/ledger/audit.jsonl` (verify path).
3.  Generate `docs/research/audit_reconstruction_analysis.md`.
