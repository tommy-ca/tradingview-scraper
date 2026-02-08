---
title: "refactor: Harden Simulator Adapters for Institutional Integrity"
type: refactor
date: 2026-02-08
---

# refactor: Harden Simulator Adapters for Institutional Integrity

## Overview

This plan details the hardening of the `VectorBT` and `CVXPortfolio` simulator adapters. The goal is to enforce strict data contracts for input weights (prioritizing signed `Net_Weight`) and ensure output metrics are robustly sanitized for JSON serialization. This prevents silent directional errors (Long instead of Short) and runtime crashes during forensic auditing.

## Problem Statement / Motivation

1.  **Serialization Fragility**: `json.dump` crashes when simulators return `np.int64`, `np.float32`, `inf`, or `NaN` in their metrics, causing pipeline failure *after* expensive computations.
2.  **Directional Ambiguity**: Simulators currently fallback to `Weight` (absolute) if `Net_Weight` is missing. This is dangerous for Long/Short strategies, where a missing column could silently flip a Short hedge into a Long exposure.
3.  **Silent Tracking Error**: If a weighted symbol is missing from the returns matrix, simulators often silently drop it, creating unhedged risk.

## Proposed Solution

We will implement a **Strict Contract Adapter** pattern:

1.  **Input Guard**: Enforce `Net_Weight` presence via a Pydantic-like validation step. Raise `DataIntegrityError` if symbols are orphaned (in weights but not returns).
2.  **Explicit Alignment**: Use zero-copy reindexing to align weights to the simulator's returns index, filling missing values with `0.0` (cash).
3.  **Output Sanitizer**: Implement a recursive `sanitize_metrics` utility that converts Numpy types to native Python and handles `inf`/`NaN` gracefully.

## Technical Approach

### Architecture

- **BaseSimulator**: Enhanced with `_validate_weights(weights, returns)` and `_sanitize_metrics(metrics)` methods.
- **VectorBTSimulator**: Refactored to use `size_type="target_percent"` mapping directly to `Net_Weight`.
- **CVXPortfolioSimulator**: Refactored to construct `h_target` from `Net_Weight`.

### Implementation Phases

#### Phase 1: Base Hardening
- Implement `BaseSimulator._validate_inputs` to check for `Net_Weight` and symbol intersection.
- Implement `BaseSimulator._sanitize_metrics` with recursive type cleaning.

#### Phase 2: Adapter Refactor
- Update `VectorBTSimulator` to strictly use `Net_Weight`.
- Update `CVXPortfolioSimulator` to strictly use `Net_Weight`.

#### Phase 3: Testing & Verification
- Create `tests/test_simulator_contracts.py`.
- Test cases:
    - **Directional**: Ensure `Net_Weight=-0.5` produces positive return on price drop.
    - **Serialization**: Ensure `inf`/`NaN` metrics serialize to `null`.
    - **Orphan**: Ensure "Weight Orphan" raises `ValueError`.

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
