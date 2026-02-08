---
date: 2026-02-08
topic: simulator-adapter-hardening
---

# Brainstorm: Simulator Adapter Hardening

## What We're Building
A robust hardening pass for the VectorBT and CVXPortfolio simulator adapters to ensure they handle institutional-grade data contracts (weights formats) and produce strictly serializable metrics (JSON-safe). This will eliminate runtime errors during the `flow-production` cycle when saving `audit.jsonl`.

## Why This Approach
Recent DataOps validation runs exposed fragility in how simulator results are serialized. Specifically:
1.  **JSON Serialization Error**: Simulators return `pd.Series` or `np.ndarray` in their metrics dict, which crashes `json.dump` in the audit ledger.
2.  **Weight Format Mismatch**: VectorBT and CVXPortfolio expect specific index alignments (Symbol index vs Time index) that differ from the `AllocationPipeline`'s flat "Symbol, Weight" format.
3.  **Missing "Physical Normalization"**: While `SimulationStage` flattens weights, the simulators themselves need to robustly handle the "Net_Weight" vs "Weight" ambiguity for Long/Short strategies.

## Key Decisions
-   **Decision 1: Centralized Sanitization**: While `SimulationStage` has a sanitizer, we will harden the *Output Contract* of the `BaseSimulator` interface itself. Each simulator MUST return clean types, or the base class will enforce it via a decorator or post-processing hook.
-   **Decision 2: Explicit "Net_Weight" Usage**: Standardize all simulators to use `Net_Weight` (signed) instead of `Weight` (absolute) to correctly support Long/Short portfolios natively.
-   **Decision 3: Zero-Copy Alignment**: Ensure weight alignment uses reindexing rather than iterative loops to maintain the vectorization benefits.

## Open Questions
-   **Nautilus Parity**: Can we reuse the `nautilus_adapter.py` "T-1 Priming" logic for VectorBT to ensure consistent start-of-window execution?
-   **Performance**: Will deep-cleaning serialization metrics add latency to the high-frequency loop? (Likely negligible compared to simulation time).

## Next Steps
→ `/workflows:plan` to define the tasks:
1.  Harden `BaseSimulator` output contract.
2.  Update `VectorBTSimulator` to use `Net_Weight` and align index.
3.  Update `CVXPortfolioSimulator` to sanitize internal metrics before return.
4.  Add regression test `tests/test_simulator_contracts.py`.
