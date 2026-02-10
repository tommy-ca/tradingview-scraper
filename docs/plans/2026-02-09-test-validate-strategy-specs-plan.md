---
title: "chore: Test & Validate Strategy Specs (MTF & Exit Rules)"
type: chore
date: 2026-02-09
---

# chore: Test & Validate Strategy Specs (MTF & Exit Rules)

## Overview

This plan validates the recently implemented Multi-Timeframe (MTF) ingestion and Discrete Exit Rules (SL/TP) using a Specs-Driven Development (SDD) and Test-Driven Development (TDD) approach. We will focus on the `crypto_rating_all` and `crypto_rating_ma` profiles (Long/Short).

## Problem Statement

We have implemented the "Full Strategy Specs" feature, but we need to verify:
1.  **Correctness**: Do the Stop Loss/Take Profit rules actually reduce drawdown in volatile periods compared to the baseline?
2.  **Stability**: Does MTF ingestion work reliably for a live universe of ~20 assets without API errors?
3.  **Integrity**: Does the "Hybrid Simulation" (from_orders + stops) produce logical results (e.g., more trades, higher turnover)?

## Validation Strategy

We will use a **Differential Testing** strategy:
1.  **Baseline Run**: Run the profiles *without* exit rules (or with relaxed rules).
2.  **Challenger Run**: Run the profiles *with* active exit rules (SL 5%, TP 15%).
3.  **Comparison**: Verify that the Challenger run has higher turnover and (ideally) lower Max Drawdown.

## Technical Approach

### Phase 1: Unit Test Expansion (TDD)
- Create `tests/integration/test_full_strategy_specs.py`.
- Mock `IngestionService` to return synthetic MTF data.
- Verify `BacktestEngine` correctly orchestrates the flow: Selection -> MTF Ingestion -> Simulation (with stops).

### Phase 2: Live Validation (Canary)
- Run `crypto_rating_all` (Long) with `4h` data fetching enabled.
- Verify `data/lakehouse/mtf/4h/` is populated with *only* the winner symbols.
- Audit `audit.jsonl` to confirm `exit_rules` were logged.

### Phase 3: Performance Analysis
- Compare metrics (Sharpe, Turnover) between `crypto_rating_all` (Long) vs `crypto_rating_ma` (Long).

## Acceptance Criteria

### Functional
- [x] `make flow-production PROFILE=crypto_rating_all` completes successfully.
- [x] `data/lakehouse/mtf/4h` contains parquet files for selected assets.
- [x] Simulation logs show `sl_stop` being passed to VectorBT (verified via `test_vbt_sl.py` and audit ledger).

### Quality Gates
- [x] Unit tests pass.
- [x] No regression in core pipeline speed (verified by execution logs).

## Resources
- `feat/full-strategy-specs` branch.
