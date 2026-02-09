---
title: "feat: Full Strategy Specs (MTF & Exit Rules)"
type: feat
date: 2026-02-09
---

# feat: Full Strategy Specs (MTF & Exit Rules)

## Enhancement Summary

**Deepened on:** 2026-02-09
**Sections enhanced:** 4
**Research agents used:** repo-research-analyst, vectorbt-expert, architecture-strategist

### Key Improvements
1.  **Hybrid Simulation**: Adopted a `from_orders` + `sl_stop` hybrid approach. VectorBT's `from_orders` *can* accept stop parameters if configured correctly, or we fallback to `from_signals` by converting weight deltas to signals.
2.  **Lazy MTF Ingestion**: Defined a "Just-In-Time" data hook in `BacktestEngine` that triggers `IngestionService` for the top N candidates *before* the simulation stage.
3.  **Schema Hardening**: Standardized `exit_rules` in `manifest.json` to be passed down to `SimulationStage`.

---

## Overview

This plan upgrades the `Discovery` and `Simulation` pillars to support **Multi-Timeframe (MTF)** strategies and **Discrete Trade Specifications** (Entry/SL/TP). It moves the platform from a pure "Portfolio Rebalance" model to a hybrid model that can execute precise trade instructions using `VectorBT`'s advanced signal engine.

## Problem Statement / Motivation

1.  **Execution Gap**: The current system only supports daily rebalancing. It cannot simulate intraday Stop Loss or Take Profit events, leading to unrealistic drawdown estimates for volatile crypto assets.
2.  **Information Gap**: Alpha signals are restricted to daily resolution. We miss "Trend in Trend" opportunities (e.g., 4h pullback within 1d trend).
3.  **Complexity Trap**: Previous attempts to "overlay" signals on weights led to "split-brain" state management.

## Proposed Solution

We will adopt a **"Winner-Takes-All"** strategy for MTF and a **"Native Delegation"** strategy for Simulation:
1.  **Lazy MTF Ingestion**: Only fetch 4h/1h data for the *selected winners* (post-ranking), not the entire universe. This respects YAGNI and API limits.
2.  **Native VectorBT Support**: Refactor `VectorBTSimulator` to accept `exit_rules` and pass them to the underlying engine.
3.  **Orthogonal Logic**: Keep "Target Allocation" (Alpha) separate from "Exit Rules" (Risk).

## Technical Approach

### Architecture

- **Manifest Schema**: Update `backtest` config to accept `exit_rules: { sl_stop: 0.05, tp_stop: 0.1 }` and `timeframes: ["4h"]`.
- **`VectorBTSimulator`**: Update `simulate` signature to accept `**kwargs` and pass `sl_stop`/`tp_stop` to `from_orders`.
- **`IngestionService`**: Add `fetch_mtf_for_candidates(candidates, intervals)` to lazy-load high-res data.

### Implementation Phases

#### Phase 1: Schema & Simulator Hardening
- Update `manifest.json` schema to allow `exit_rules`.
- Update `SimulationStage.execute` to extract `exit_rules` from the profile config.
- Refactor `VectorBTSimulator` to pass these rules to `vbt.Portfolio.from_orders`.

#### Phase 2: Lazy MTF Ingestion
- Implement `IngestionService.fetch_mtf` using the existing `CCXT`/`TV` clients but targeting specific intervals.
- Update `BacktestEngine._run_window_step` to call this service for the `winners` list before calling `_run_simulation`.
- Store MTF data in `data/lakehouse/mtf/{interval}/{symbol}.parquet`.

#### Phase 3: Strategy Config
- Update `crypto_rating_*` profiles to include `exit_rules` (e.g., SL 5%, TP 15%).

## Acceptance Criteria

### Functional Requirements
- [ ] `VectorBTSimulator` respects `sl_stop` parameter (verified by test).
- [ ] MTF data is only fetched for the top N selected assets.
- [ ] `audit.jsonl` records the `exit_rules` used in the simulation context.

### Quality Gates
- [ ] **Type Safety**: `exit_rules` validated via Pydantic in `SelectionContext` (or `AllocationContext`).
- [ ] **Parity**: Running without `exit_rules` yields identical results to the legacy rebalance mode.

## References & Research
- `docs/brainstorms/2026-02-08-full-strategy-specs-brainstorm.md`
- `vectorbt` documentation (Portfolio.from_orders supports `sl_stop` in recent versions)
