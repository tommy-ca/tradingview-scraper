# Plan: Grand Validation Tournament 2026

## Phase 1: Tournament Expansion & Execution
- [x] Task: Refactor `scripts/run_4d_tournament.py` for the Grand Matrix. a807397
- [~] Task: Execute Grand Tournament.
    - [ ] Sub-task: Run the full permutation matrix (150+ combinations).
    - [ ] Sub-task: Monitor system resources and numerical stability (kappa) during execution.
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Reporting & Behavioral Auditing
- [ ] Task: Generate standard reports via existing utilities.
    - [ ] Sub-task: Create `grand_validation_4d_comparison.md` using `scripts/generate_human_table.py`.
    - [ ] Sub-task: Create `selection_alpha_report.md` and `risk_profile_report.md`.
- [ ] Task: Implement and Run Outlier Detection.
    - [ ] Sub-task: Create `scripts/audit_tournament_outliers.py` to identify >2σ deviations in Sharpe and MDD.
    - [ ] Sub-task: Analyze wide gaps between `nautilus` and `custom` simulators.
    - [ ] Sub-task: Write `docs/research/outlier_analysis_report.md` documenting findings and justifications.
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Integrity & Compliance
- [ ] Task: Verify Tournament Integrity.
    - [ ] Sub-task: Run `scripts/verify_ledger.py` on the resulting `audit.jsonl`.
    - [ ] Sub-task: Confirm Data Quality and Coverage scores are 100.0/100 using `scripts/comprehensive_audit.py`.
- [ ] Task: Final Track Summary.
    - [ ] Sub-task: Document "Lessons Learned" from the Grand Audit.
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)
