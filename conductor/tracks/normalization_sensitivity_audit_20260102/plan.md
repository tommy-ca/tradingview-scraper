# Plan: Normalization Sensitivity Audit (v2.1)

## Phase 1: Raw Feature Matrix & Multi-Method Tuner
- [x] Task: Update `scripts/cache_selection_features.py` to save raw values. (7820596)
- [x] Task: Refactor `scripts/tune_v2_alpha.py` to implement the `NormalizationEngine`. (7820596)
- [x] Task: Execute 500-trial Global study to find the "Champion Normalization." (7820596)
- [x] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Engine Implementation & Settings Update
- [x] Task: Update `tradingview_scraper/settings.py` with `normalization_protocol_global` and optimized weights. (7820596)
- [x] Task: Refactor `SelectionEngineV2_1` to support the chosen normalization protocol. (7820596)
- [x] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Final Tournament Battle
- [x] Task: Tournament: `v3.1` (Multiplicative) vs `v2.1_rank` (Old Baseline) vs `v2.1_opt` (New Champion). (7820596)
- [x] Task: Final Research Report: `docs/research/normalization_audit_2026.md`. (7820596)
- [x] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)
