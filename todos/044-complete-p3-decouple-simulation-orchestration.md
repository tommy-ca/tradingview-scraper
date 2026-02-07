---
status: complete
priority: p3
issue_id: "044"
tags: [refactor, backtest, orchestration]
dependencies: []
---

# Decouple simulation orchestration

Split the monolithic `_run_simulation` method in `BacktestEngine` into modular execution, sanitization, and logging components.

## Problem Statement

The `_run_simulation` method in `scripts/backtest_engine.py` (and now `tradingview_scraper/backtest/engine.py`) was a monolithic function handling multiple responsibilities:
- Initializing simulation context and building the simulator engine.
- Executing the simulation and managing holdings state.
- Sanitizing raw metrics for JSON/Audit serialization.
- Accumulating return series and recording audit outcomes.

## Findings

- `_run_simulation` spanned ~70 lines of mixed logic.
- Tight coupling made simulation logic difficult to unit test in isolation.

## Proposed Solutions

### Option 1: Modularize within BacktestEngine (Recommended)

**Approach:** Extract logic into private helper methods:
- `_execute_simulator(...)`: Handles engine building and `simulator.simulate()`.
- `_sanitize_sim_metrics(...)`: Extracts and cleans metrics for auditing.
- `_record_sim_outcome(...)`: Handles `AuditLedger` and `results.append`.

## Acceptance Criteria

- [x] `_run_simulation` is refactored into at least 3 distinct sub-methods.
- [x] Logic for Concentration HHI calculation is handled within sanitization/metrics.
- [x] Unit tests are added for `_sanitize_sim_metrics` (Verification needed).
- [x] `AuditLedger` captures identical data before and after refactoring.

## Work Log

### 2026-02-02 - Initial Discovery
**By:** Antigravity
- Analyzed `_run_simulation` implementation.
- Identified specific logic clusters for extraction.

### 2026-02-07 - Refactoring Complete
**By:** Antigravity
- Refactored `_run_simulation` in `tradingview_scraper/backtest/engine.py` into `_execute_simulator`, `_sanitize_sim_metrics`, `_update_sim_state`, and `_record_sim_outcome`.
