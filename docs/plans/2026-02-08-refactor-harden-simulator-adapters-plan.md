---
title: "refactor: Harden Simulator Adapters for Institutional Integrity"
type: refactor
date: 2026-02-08
---

# refactor: Harden Simulator Adapters for Institutional Integrity

## Enhancement Summary

**Deepened on:** 2026-02-08
**Sections enhanced:** 3
**Research agents used:** repo-research-analyst, spec-flow-analyzer, kieran-rails-reviewer, code-simplicity-reviewer, data-integrity-guardian

### Key Improvements
1.  **Strict Pydantic Interfaces**: Replaced loose dict/dataframe passing with `SimulationContext` and `SimulationResult` Pydantic models for the public API.
2.  **Vectorized Validation**: Rejected row-level Pydantic validation in favor of fast Pandas index intersection checks for symbols and timestamps.
3.  **Recursive Sanitization**: Added a robust `sanitize_metrics` utility to handle nested numpy types and NaNs.

### New Considerations Discovered
-   **Directional Integrity**: Explicitly testing that negative weights yield positive returns on price drops.
-   **Timestamp Alignment**: Ensuring that trading signals are not silently dropped if the corresponding market data is missing (Time-Axis Gap).

## Overview

This plan details the hardening of the `VectorBT` and `CVXPortfolio` simulator adapters. The goal is to enforce strict data contracts for input weights (prioritizing signed `Net_Weight`) and ensure output metrics are robustly sanitized for JSON serialization. This prevents silent directional errors (Long instead of Short) and runtime crashes during forensic auditing.

## Problem Statement / Motivation

1.  **Serialization Fragility**: `json.dump` crashes when simulators return `np.int64`, `np.float32`, `inf`, or `NaN` in their metrics, causing pipeline failure *after* expensive computations.
2.  **Directional Ambiguity**: Simulators currently fallback to `Weight` (absolute) if `Net_Weight` is missing. This is dangerous for Long/Short strategies, where a missing column could silently flip a Short hedge into a Long exposure.
3.  **Silent Tracking Error**: If a weighted symbol is missing from the returns matrix, simulators often silently drop it, creating unhedged risk.

## Proposed Solution

We will implement a **Strict Contract Adapter** pattern with high-level Pydantic interfaces and vectorized internal validation:

1.  **Input Guard (Vectorized)**: Enforce `Net_Weight` presence and strictly validate symbol AND timestamp alignment using Pandas index operations. Raise `DataIntegrityError` if non-zero weights exist for missing timestamps or symbols.
2.  **Interface Formalization**: Introduce `SimulationContext` and `SimulationResult` Pydantic models to strictly type the input/output containers (replacing loose dictionaries).
3.  **Output Sanitizer**: Implement a recursive `sanitize_metrics` utility that converts Numpy types (`int64`, `float32`) to native Python and handles `inf`/`NaN` (converting to `null` for JSON safety).

## Technical Approach

### Architecture

- **Data Structures**:
    - `SimulationContext`: Pydantic model holding `returns` (pd.DataFrame), `weights` (pd.DataFrame with Net_Weight). Validates columns and alignment in `model_validator`.
    - `SimulationResult`: Pydantic model holding `metrics` (Dict), `equity_curve` (Series).
- **BaseSimulator**:
    - `simulate(ctx: SimulationContext) -> SimulationResult`
    - `_validate_inputs` (called by Pydantic validator or explicitly)
    - `_sanitize_metrics` (recursive cleaner)
- **VectorBTSimulator**: Refactored to use `size_type="target_percent"` mapping directly to `Net_Weight`.
- **CVXPortfolioSimulator**: Refactored to construct `h_target` from `Net_Weight`.

### Implementation Phases

#### Phase 1: Base Hardening & Schemas
- Define `SimulationContext` and `SimulationResult` in `tradingview_scraper/portfolio_engines/types.py` (or similar).
- Implement `BaseSimulator._sanitize_metrics` with recursive type cleaning (handling `np.integer`, `np.floating`, `NaN`, `Inf`).
- Implement vectorized validation logic: `weights.index.isin(returns.index)` and `weights.columns.isin(returns.columns)`.

#### Phase 2: Adapter Refactor
- Update `VectorBTSimulator` to strictly use `Net_Weight`.
- Update `CVXPortfolioSimulator` to strictly use `Net_Weight`.
- Ensure both adapters return `SimulationResult`.

#### Phase 3: Testing & Verification
- Create `tests/test_simulator_contracts.py`.
- Test cases:
    - **Directional**: Ensure `Net_Weight=-0.5` produces positive return on price drop.
    - **Serialization**: Ensure `inf`/`NaN` metrics serialize to `null` via `json.dumps`.
    - **Orphan (Symbol)**: Ensure "Weight Orphan" raises `ValueError`.
    - **Orphan (Time)**: Ensure "Weight for missing date" raises `ValueError`.


## Acceptance Criteria

### Functional Requirements
- [ ] Simulators raise `ValueError` if `Net_Weight` is missing.
- [ ] Simulators raise `ValueError` if weighted symbols are missing from market data.
- [ ] `audit.jsonl` successfully records metrics containing `NaN` or `Infinity` (as `null`).

### Quality Gates
- [ ] `test_simulator_contracts.py` passes.
- [ ] `make flow-production` completes without JSON serialization errors.

## References & Research
- `docs/brainstorms/2026-02-08-simulator-adapter-hardening-brainstorm.md`
- `tradingview_scraper/portfolio_engines/backtest_simulators.py`
