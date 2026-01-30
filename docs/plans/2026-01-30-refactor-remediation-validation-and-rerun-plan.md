---
title: Documentation Update & Production Rerun (Remediation Certification)
type: refactor
date: 2026-01-30
---

# Documentation Update & Production Rerun (Remediation Certification)

## Overview

Following the critical remediation of the Metadata Ingestion and Feature Backfill pipeline (PR #61), this plan outlines the necessary documentation updates and certification runs required to restore institutional confidence. We will standardize our requirements and specs with the new integrity patterns and execute high-fidelity "Certification Runs" for the Binance Spot Ratings universe.

## Problem Statement / Motivation

PR #61 addressed:
1.  **2x Performance Bottleneck**: Redundant calculations in technical ratings.
2.  **Data Integrity Gaps**: Lack of runtime schema validation at the persistence layer.
3.  **Legacy Debt**: Outdated type hints and inefficient Pandas loops.

While the code is fixed, our **Documentation Source of Truth** is now out of sync, and our **Production Artifacts** (Gold Snapshots) were generated using the unoptimized engine. We need to certify the new system end-to-end.

## Proposed Solution

1.  **Specs-Driven Update**: Sync `requirements_v3.md`, `feature_composition_v3.6.5.md`, and `plan.md` with the new "Institutional Integrity Standards".
2.  **Pipeline Certification**: Validate the "Scoped Ingestion" and "Atomic Write" patterns.
3.  **Production Rerun (`cert_v4`)**: Execute fresh runs for `all_long/short`, `ma_long/short`, and `osc_long/short` sleeves.
4.  **Deep Forensic Audit**: Inspect rebalance window ledger logs to certify the "Window Veto" and "Alpha Attribution" logic.

## Technical Considerations

### Architecture Impacts
-   **Contract Enforcement**: All future backfill operations must now pass `FeatureStoreSchema.validate()` before disk persistence.
-   **Atomic Writes**: Standardize the `tempfile -> rename` pattern across all Lakehouse writers.

### Performance Implications
-   Target: > 40% reduction in `make feature-backfill` latency.
-   Target: Zero `SchemaError` exceptions in standard production runs.

### Numerical Drift
-   Acceptable tolerance for technical ratings divergence: $1e-7$.
-   Portfolio Jaccard Similarity (vs. Phase 246): > 0.95.

## Acceptance Criteria

- [ ] **Documentation**: `requirements_v3.md` includes Section 7 (Integrity Standards).
- [ ] **Tracking**: `docs/specs/plan.md` updated with **Phase 740**.
- [ ] **Validation**: `make feature-backfill` benchmarked and certified.
- [ ] **Execution**: 6 production runs (`cert_v4`) completed successfully.
- [ ] **Forensics**: Deep Reports generated and stored in `data/artifacts/summaries/runs/cert_v4_*/reports/`.
- [ ] **Sign-off**: `docs/reports/remediation_certification_v1.md` created and populated.

## Dependencies & Risks

- **Risk**: Numerical drift from Numpy vectorization might cause "Threshold Edge" assets to flip.
- **Mitigation**: Perform a Cross-Run Consistency Check using Jaccard similarity.
- **Risk**: Atomic write rename might fail on NFS/Network drives if not handled defensively.
- **Mitigation**: Use `shutil.move` for cross-filesystem compatibility.

## References & Research

- **Remediation PR**: #61
- **Integrity Schema**: `tradingview_scraper/pipelines/contracts.py:9`
- **Backfill Service**: `scripts/services/backfill_features.py:37`
- **Metadata Script**: `scripts/build_metadata_catalog.py:20`

## MVP Implementation Suggestion

### Phase 1: Documentation Sync
- Update `docs/specs/requirements_v3.md` with "Institutional Integrity Standards".
- Update `docs/specs/plan.md` to add Phase 740 tasks.

### Phase 2: backfill_features.py Atomicity Upgrade
```python
# Refactor saving logic to use temp file
temp_out = out_p.with_suffix(".parquet.tmp")
features_df.to_parquet(temp_out)
os.replace(temp_out, out_p) 
```

### Phase 3: Certification Run Script
Create a small bash script `scripts/maintenance/run_cert_v4.sh` to execute the 6 required sleeves in order.
