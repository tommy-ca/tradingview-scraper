# Design: Meta Sleeve Completeness & Forensic Trace (v1)

## Objective
Prevent meta portfolios from silently degrading to partial (or single-sleeve) allocations and ensure directional integrity signals are preserved at the meta layer.

## Requirements
- Meta runs MUST abort when any configured sleeve:
  - Lacks a `run_id`.
  - Is missing required artifacts (`meta_returns`, `meta_optimized`, `portfolio_optimized_meta`, cluster tree) or produces empty returns.
  - Fails directional sign-test gating when `feat_directional_sign_test_gate` is enabled.
- Single-sleeve metas are only permitted when explicitly defined as one-sleeve profiles and documented.
- Meta reports MUST include:
  - Sleeve completeness table (exists/missing per artifact, sleeve ids + run_ids).
  - Directional sign-test findings when enabled.
  - Forensic trace pointer (audit or sign-test JSON path).
  - Explicit PASS/FAIL banner when required sections are missing or empty.

## Implementation Hooks
- `scripts/validate_meta_run.py`: enforce sleeve completeness, empty-return detection, and sign-test presence when required.
- `scripts/run_meta_pipeline.py`: fail fast before optimization if completeness or sign-test checks fail.
- Reporting stage (`meta_portfolio_report.md`): render completeness + sign-test sections; treat missing sections as errors and propagate FAIL status to the pipeline.

## TDD
- Add tests that:
  - Fail when any sleeve artifacts are missing or empty.
  - Fail when sign-test gate is required but `directional_sign_test.json` is absent or contains errors.
  - Reject single-sleeve outputs for multi-sleeve meta profiles.
  - Fail when report generation lacks completeness/sign-test sections or sleeve count <2 for multi-sleeve profiles.

## Related
- `docs/specs/requirements_v3.md`
- `docs/specs/production_workflow_v2.md`
- `docs/specs/binance_spot_ratings_atomic_pipelines_v1.md`
