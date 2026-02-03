---
status: pending
priority: p3
issue_id: "044"
tags: [refactor, backtest, orchestration]
dependencies: []
---

# Decouple simulation orchestration

Split the monolithic `_run_simulation` method in `BacktestEngine` into modular execution, sanitization, and logging components.

## Problem Statement

The `_run_simulation` method in `scripts/backtest_engine.py` is currently a monolithic function that handles multiple responsibilities:
- Initializing simulation context and building the simulator engine.
- Executing the simulation and managing holdings state.
- Sanitizing raw metrics for JSON/Audit serialization.
- Accumulating return series and recording audit outcomes.

This tight coupling makes the simulation logic difficult to unit test in isolation, especially the metrics sanitization and state transition logic.

## Findings

- `_run_simulation` (lines 634-703 of `scripts/backtest_engine.py`) spans ~70 lines of mixed logic.
- It performs manual filtering for numeric types and calculates Concentration HHI inside the main loop.
- It handles complex state lookups in `self.current_holdings` using mixed types (dict vs object).
- Audit logging is interleaved with execution logic, making it hard to follow the happy path.

## Proposed Solutions

### Option 1: Modularize within BacktestEngine (Recommended)

**Approach:** Extract logic into private helper methods:
- `_execute_simulator(...)`: Handles engine building and `simulator.simulate()`.
- `_sanitize_sim_metrics(...)`: Extracts and cleans metrics for auditing.
- `_record_sim_outcome(...)`: Handles `AuditLedger` and `results.append`.

**Pros:**
- Minimal changes to calling signatures.
- Significantly improves readability of the orchestration loop.
- Enables unit testing of sanitization logic without running full simulations.

**Cons:**
- Still keeps logic within the large `BacktestEngine` class.

**Effort:** 2-3 hours

**Risk:** Low

---

### Option 2: SimulationOrchestrator Class

**Approach:** Create a dedicated class or state machine to manage the simulation lifecycle.

**Pros:**
- Perfect decoupling.
- Reusable across different engine types.

**Cons:**
- Over-engineering for the current scope.
- Adds architectural complexity.

**Effort:** 4-6 hours

**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `scripts/backtest_engine.py`

**Related components:**
- `AuditLedger` (Outcome recording)
- `Simulator` implementations (Base and concrete engines)

## Acceptance Criteria

- [ ] `_run_simulation` is refactored into at least 3 distinct sub-methods.
- [ ] Logic for Concentration HHI calculation is extracted to a utility or helper.
- [ ] Unit tests are added for `_sanitize_sim_metrics`.
- [ ] `AuditLedger` captures identical data before and after refactoring.

## Work Log

### 2026-02-02 - Initial Discovery

**By:** Antigravity

**Actions:**
- Analyzed `_run_simulation` implementation in `scripts/backtest_engine.py`.
- Identified specific logic clusters for extraction.
- Drafted refactoring plan in todo 044.

## Notes

- Prioritize stability of the `AuditLedger` output as it is used for downstream reporting.
- Ensure state management for recursive meta-portfolios remains thread-safe during extraction.
