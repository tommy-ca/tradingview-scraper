# Plan: Quantitative Improvement Plan 2026

## Phase 1: Deep Audit & Spectral Analysis
- [ ] Task: Audit Spectral Vetoes in the 2025 Grand Matrix.
    - [ ] Sub-task: Extract list of symbols vetoed by Entropy/Efficiency in every window.
    - [ ] Sub-task: Calculate "Opportunity Cost" (Total return of vetoed assets vs selected assets).
    - [ ] Sub-task: Identify if specific asset classes (e.g. Crypto) are unfairly penalized.
- [ ] Task: Research Integration Models for Predictability.
    - [ ] Sub-task: Propose mathematical formula for "Soft-Weighting" (e.g. MPS * Efficiency).
    - [ ] Sub-task: Research "Predictability-Adjusted Returns" for the optimizer.
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Engine Stability & skfolio Audit
- [ ] Task: Isolate skfolio Outlier Windows.
    - [ ] Sub-task: Identify specific windows where skfolio deviation from group mean was >2σ.
    - [ ] Sub-task: Correlation check between outlier magnitude and covariance Condition Number (kappa).
- [ ] Task: Perform Factor Sensitivity Analysis.
    - [ ] Sub-task: Check if skfolio sensitivity is driven by the Returns Estimator vs Covariance.
    - [ ] Sub-task: Draft the "Engine Reliability Matrix" for docs.
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Strategy Evolution & Final Improvement Plan
- [ ] Task: Analyze v3.1 Alpha Success.
    - [ ] Sub-task: Perform Sector/Cluster attribution for v3.1 top-performing windows.
    - [ ] Sub-task: Evaluate adding Higher-Order Moment features (Skewness, Kurtosis) to MPS.
- [ ] Task: Finalize Improvement Plan & Prototype.
    - [ ] Sub-task: Write `docs/research/quantitative_improvement_plan_2026.md`.
    - [ ] Sub-task: TDD - Implement `SelectionEngineV3_2` prototype with soft-weighting logic.
    - [ ] Sub-task: Verify prototype logic with unit tests.
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)
