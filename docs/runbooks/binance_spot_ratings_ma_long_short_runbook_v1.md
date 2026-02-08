# Runbook: Binance Spot Ratings — MA Long/Short Atomic Pipelines (v1)
**Date:** 2026-01-28  
**Profiles:** `binance_spot_rating_ma_long`, `binance_spot_rating_ma_short`

## 1. Objective
Execute the MA-based Binance Spot rating sleeves and produce audit-ready artifacts proving:
- Directional correction correctness for SHORT (sign-test gate enabled).
- Artifact completeness for meta eligibility (contract-ready run dir).
- Reproducibility via `config/resolved_manifest.json`.

## 2. Preconditions
1) Lakehouse inputs current:
```bash
make flow-data PROFILE=binance_spot_rating_ma_long RUN_ID=<scan_run>
make flow-data PROFILE=binance_spot_rating_ma_short RUN_ID=<scan_run>
```
2) Environment sanity:
```bash
make env-check
```

## 3. Manual Workflow (deterministic run ids)
```bash
RUN_LONG=binance_spot_rating_ma_long_<YYYYMMDD-HHMMSS>
RUN_SHORT=binance_spot_rating_ma_short_<YYYYMMDD-HHMMSS>

TV_RUN_ID=$RUN_LONG  make flow-production PROFILE=binance_spot_rating_ma_long
TV_RUN_ID=$RUN_SHORT make flow-production PROFILE=binance_spot_rating_ma_short

make atomic-audit RUN_ID=$RUN_LONG  PROFILE=binance_spot_rating_ma_long
make atomic-audit RUN_ID=$RUN_SHORT PROFILE=binance_spot_rating_ma_short
```

## 4. Expected Artifacts (per run)
- `config/resolved_manifest.json`
- `audit.jsonl`
- `data/returns_matrix.parquet`
- `data/synthetic_returns.parquet`
- `data/portfolio_optimized_v2.json`
- `data/directional_sign_test_pre_opt.json`
- `data/directional_sign_test.json`
- `reports/validation/atomic_validation_<PROFILE>_<RUN_ID>.{md,json}`

## 5. Acceptance Criteria
- Directional sign test PASS (`errors == 0`) for SHORT sleeve.
- Atomic validation PASS and all required artifacts present.
- `feat_directional_sign_test_gate_atomic=true` enforced for SHORT sleeve.

## 6. References
- `docs/specs/synthetic_rating_ma_spec_v1.md`
- `docs/specs/production_workflow_v2.md`
- `docs/specs/requirements_v3.md`
- `docs/specs/atomic_run_validation_v1.md`
