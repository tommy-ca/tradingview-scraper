# Brainstorm: Modernize and Decouple Data Pipelines (DataOps/MLOps v2)

**Date:** 2026-02-03
**Topic:** DataOps and MLOps Formalization for Scalable Pipelines

## What We're Building

A comprehensive plan to complete the modernization of the platform's data infrastructure, moving fully away from legacy scripts to a robust, registry-driven `QuantSDK` architecture. This includes formalizing the Feature Store, integrating advanced MLOps tooling (DVC/MLflow), and ensuring scalable decoupling between data ingestion and alpha generation.

## Why This Approach

The user has indicated a broad interest in **Migration, Tooling, AND Scaling**. This suggests a holistic "DataOps v2" initiative rather than a single feature.
1.  **Technical Debt**: The coexistence of `scripts/` and `pipelines/` creates confusion and fragility. Consolidating on `QuantSDK` is the necessary foundation.
2.  **Scalability**: Legacy scripts struggle with large datasets. The `StageRegistry` pattern natively supports distributed execution (Ray) and caching.
3.  **Governance**: Advanced MLOps tooling (DVC/MLflow) provides the rigorous versioning and audit trails required for institutional-grade quant research.

## Key Decisions

1.  **Architecture**: **"Seamless Wrapper"**. We will enhance the existing `QuantSDK` to transparently wrap industry-standard tools (MLflow for metrics, DVC for data versioning) rather than rewriting the core logic to fit those tools. This preserves our high-performance custom engines while gaining standard observability.
2.  **Decoupling**: Enforce a strict "Lakehouse Contract". Data pipelines *write* to the Lakehouse (Parquet/Delta). Alpha pipelines *read* from the Lakehouse via `DataLoader`. No direct file sharing or script imports allowed.
3.  **Execution**: Deprecate direct script execution (`python scripts/foo.py`). All workflows must be runnable via `make flow-...` or `QuantSDK.run_pipeline(...)`.

## Open Questions

1.  **Infrastructure**: Do we need to provision a persistent MLflow tracking server, or is a local file-based backend sufficient for the current scale? (Assume local for now).
2.  **Migration Strategy**: Should we migrate the massive "backfill" logic first (highest impact) or the "live trading" logic (highest risk)? (Recommend Backfill first to validate patterns).
3.  **Data Versioning**: DVC is powerful but complex. Is git-lfs or simple S3 snapshotting a viable alternative for the "Golden Snapshots"?

## Recommended Next Steps

Run `/workflows:plan` to generate the detailed migration roadmap, focusing on the `QuantSDK` consolidation as the first milestone.
