---
title: "feat: Unified Backtesting Events & Re-entry Paradox Fix"
type: feat
date: 2026-02-10
---

# feat: Unified Backtesting Events & Re-entry Paradox Fix

## Overview

This plan implements a unified, event-driven backtesting architecture that treats rebalance windows as discrete instructions. It replaces the current "polling" state-map model with a **Sparse Instruction Matrix** approach, solving the "Re-entry Paradox" (where stopped-out assets are immediately re-bought) and aligning weight-based simulators (VectorBT) with high-fidelity event engines (Nautilus).

## Problem Statement

1.  **Re-entry Paradox**: In `VectorBTSimulator`, assets that hit a Stop Loss (SL) are immediately re-entered on the next bar because the target weight matrix is continuous/dense. This violates the intended risk management logic.
2.  **Architectural Drift**: Nautilus polls a weight matrix in backtests but reacts to events in live trading. This creates a "split-brain" between simulation and reality.
3.  **Inconsistent Stops**: Stop rules are implemented differently (or not at all) across simulators, leading to divergent results.

## Proposed Solution: The Sparse Instruction Pattern

We will unify the architecture by moving to a **Sparse Matrix** model where `NaN` values represent "No Action / Maintain State (including Stops)" and non-NaN values represent explicit rebalance targets.

### 1. VectorBT Refactor (Approach A)
- Gut the "daily" rebalance mode in `VectorBTSimulator`.
- Instead of repeating weights for every timestamp, generate a matrix where only the rebalance timestamps contain the target weights.
- VectorBT natively handles `NaN` as "Maintain current position," which allows internal stops to stay closed until the next explicit rebalance event.

### 2. Nautilus Unification
- Refactor `NautilusRebalanceStrategy` to handle discrete rebalance events.
- Transition from "polling on every bar" to "reacting to a new instruction."

### 3. Pydantic Contracts
- Introduce `RebalanceEvent` and `SimulationInstruction` models to enforce data integrity at the Pillar 3 boundary (checksums, leverage limits).

## Technical Approach

### Implementation Phases

#### Phase 1: Simulator Hardening (VectorBT)
- [ ] Modify `VectorBTSimulator.simulate` to use sparse matrix creation.
- [ ] Ensure `from_orders` correctly interprets `NaN` as "maintain."
- [ ] Verify fix for Re-entry Paradox with a regression test.

#### Phase 2: Event Modeling (Pydantic)
- [ ] Create `tradingview_scraper/pipelines/allocation/events.py`.
- [ ] Define `RebalanceEvent` (Timestamp, Instructions Map, Metadata).
- [ ] Define `SimulationInstruction` (Weights, StopRules).

#### Phase 3: Nautilus Strategy Refactor
- [ ] Update `NautilusRebalanceStrategy` to implement an `on_rebalance` handler.
- [ ] Refactor the adapter to push events instead of pre-calculating a dense matrix.

#### Phase 4: Integration & Cleanup
- [ ] Update `SimulationStage` to generate the sparse matrix / event stream.
- [ ] Purge dead polling logic from simulators.

## Acceptance Criteria

### Functional Requirements
- [ ] **Paradox Resolved**: Assets hitting SL remain out of the portfolio until the next rebalance window.
- [ ] **Unified Interface**: Both VBT and Nautilus consume the same discrete instruction logic.
- [ ] **Explicit Flat**: A target weight of `0.0` explicitly flattens a position; `NaN` maintains it.

### Quality Gates
- [ ] **Type Safety**: Pydantic validation passes for all rebalance events.
- [ ] **Performance**: Sparse matrix reduces memory footprint by >50% for long-running backtests.
- [ ] **Parity**: Standard rebalance runs (no stops) yield identical results to the legacy dense mode.

## References & Research
- `docs/brainstorms/2026-02-10-unified-backtesting-events-brainstorm.md`
- `tradingview_scraper/portfolio_engines/backtest_simulators.py`
- VectorBT `from_orders` Documentation (Handling of NaNs)
