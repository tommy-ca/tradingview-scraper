---
title: "chore: Rerun Pipelines for DataOps Validation"
type: chore
date: 2026-02-06
---

# chore: Rerun Pipelines for DataOps Validation

## Enhancement Summary

**Deepened on:** 2026-02-07
**Sections enhanced:** 6
**Research agents used:** security-sentinel, performance-oracle, architecture-strategist, pattern-recognition-specialist, data-integrity-guardian, code-simplicity-reviewer, framework-docs-researcher, best-practices-researcher

### Key Improvements
1.  **Resilience Depth**: Expanded Phase 2 with "Chaos Engineering" data injection (NaNs, duplicate timestamps) to stress-test Pandera Tier 1/2.
2.  **Observability Gates**: Added explicit verification steps for local MLflow (SQLite) and OpenTelemetry cross-node tracing.
3.  **Concurrency Hardening**: Defined specific race-condition patterns to test `ThreadSafeConfig` against.

### New Considerations Discovered
-   **Serialization-Aware Hashing**: Need to ensure `get_df_hash` handles the small floating-point variances introduced by Parquet ZSTD compression.
-   **Context Merging Integrity**: Critical to verify that `audit_trail` from parallel Ray workers is correctly concatenated into the master context.

---

## Overview

This plan outlines the steps to verify the stability, correctness, and observability of the platform following the "DataOps Modularization" refactor. We will execute the data ingestion and alpha selection pipelines in `canary` mode, verifying that the new `Pandera` contracts, `ThreadSafeConfig`, and `MLflowTracker` are functioning as designed.

### Research Insights

**Best Practices:**
- **Local-First Verification**: Use `mlflow ui --port 5000` to visually inspect the `canary` experiment metrics.
- **Forensic Audit**: The primary success metric is the existence of a forensic `audit.jsonl` in the run directory that matches the MLflow ledger.

---

## Proposed Solution

We will execute a 3-part validation sequence:
1.  **Golden Path**: Run a standard `make flow-production` to confirm end-to-end integrity.
2.  **Resilience Test**: Inject "toxic" data (mocked) to verify the "Filter-and-Log" mechanism.
3.  **Config Isolation Test**: Run a concurrent test to verify `ThreadSafeConfig` stability.

---

## Technical Approach

### Implementation Phases

#### Phase 1: Integration Testing (The Golden Path)
- Execute `make flow-production PROFILE=canary` (using Feature Flags).
- **Deepened Action**: Audit the `Data Contract Violation Count` in `audit.jsonl`. Even in a "Golden" run, minor violations might be filtered.
- **Deepened Action**: Verify `trace_id` continuity across Ray nodes using local OTel logs.

#### Phase 2: Resilience Verification (Chaos Injection)
- Create `tests/ops/test_dataops_resilience.py`.
- **Chaos Scenarios**:
    - **Toxicity**: Returns > 500% (Should be dropped).
    - **Index Collision**: Duplicate timestamps (Should raise Pandera L0 error).
    - **Temporal Gap**: Sparse history for TradFi assets (Should trigger "No Padding" veto).
- **Implementation**:
```python
# Recommended mocking pattern
@patch("tradingview_scraper.data.loader.DataLoader.load_run_data")
def test_toxic_filter(mock_load):
    mock_load.return_value = generate_chaos_df()
    # Execute pipeline...
```

#### Phase 3: Concurrency Verification (Config Isolation)
- Create `tests/ops/test_config_isolation.py`.
- Spawn 2x Threads with differing `ContextLocal` settings.
- **Test Pattern**:
    - Thread A: `set_settings(profile="A")` -> `sleep(1)` -> `assert get_settings().profile == "A"`.
    - Thread B: `set_settings(profile="B")` -> `assert get_settings().profile == "B"`.
- This ensures that Thread B's fast execution doesn't contaminate Thread A's context.

---

## Acceptance Criteria

### Functional Requirements
- [x] `make flow-production` completes with exit code 0.
- [x] `audit.jsonl` reflects "Data Contract" validation steps for every stage.
- [x] MLflow `mlruns/` contains a run matching the orchestrator `RUN_ID`.

### Quality Gates
- [x] **Data Parity**: Cryptographic hash of the `SelectedWinners` matches historical baseline for the same window.
- [x] **Trace Integrity**: 100% of tasks in a run share the same root `trace_id`.

---

## References & Research
- https://mlflow.org/docs/latest/tracking.html#local-database (SQLite Tracking)
- https://pandera.readthedocs.io/en/stable/lazy_validation.html (Lazy Error Handling)
- `docs/solutions/architecture/dataops-core-pillar-hardening-20260207.md`
